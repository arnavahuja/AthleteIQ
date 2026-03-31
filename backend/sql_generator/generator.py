import json
import re
import anthropic
from backend.config import settings
from .prompt_builder import build_prompt, build_retry_prompt
from .validator import validate_sql

_client = None

MAX_SQL_RETRIES = 3


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _parse_response(text: str) -> dict:
    """Parse the combined intent+SQL JSON response from the LLM."""
    text = text.strip()
    # Remove markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON block from text
    json_match = re.search(r'\{[\s\S]*"sql"\s*:[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Last resort: find raw SQL
    sql_match = re.search(r'SELECT\s.+', text, re.IGNORECASE | re.DOTALL)
    if sql_match:
        return {
            "intent_type": "metric",
            "visualization_hint": "table",
            "sql": sql_match.group().rstrip(";").strip(),
        }

    return {"sql": text, "intent_type": "metric", "visualization_hint": "table"}


def _call_claude(prompt: str) -> str:
    """Make a single Claude API call and return the text response."""
    client = _get_client()
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def generate_sql(query: str, intent: dict, rag_context: dict, conversation_history: list[dict] | None = None) -> dict:
    """
    Generate SQL from natural language using Claude.
    Retries up to MAX_SQL_RETRIES times if validation fails,
    feeding each error back to Claude so it can self-correct.
    """
    prompt = build_prompt(query, intent, rag_context, conversation_history)
    current_prompt = prompt
    last_parsed = None

    for attempt in range(MAX_SQL_RETRIES + 1):
        response_text = _call_claude(current_prompt)
        parsed = _parse_response(response_text)
        last_parsed = parsed
        sql = parsed.get("sql", "").rstrip(";").strip()
        is_valid, error = validate_sql(sql)

        if is_valid:
            return {
                "sql": sql,
                "valid": True,
                "error": None,
                "intent_type": parsed.get("intent_type", "metric"),
                "visualization_hint": parsed.get("visualization_hint", "table"),
            }

        # If we have retries left, feed the error back
        if attempt < MAX_SQL_RETRIES:
            current_prompt = build_retry_prompt(prompt, sql, error)
        # Otherwise fall through and return the invalid result

    # Exhausted retries
    sql = last_parsed.get("sql", "").rstrip(";").strip()
    _, error = validate_sql(sql)
    return {
        "sql": sql,
        "valid": False,
        "error": error,
        "intent_type": last_parsed.get("intent_type", "metric"),
        "visualization_hint": last_parsed.get("visualization_hint", "table"),
    }
