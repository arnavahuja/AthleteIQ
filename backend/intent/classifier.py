import json
import anthropic
from backend.config import settings

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


CLASSIFICATION_PROMPT = """You are a query intent classifier for a sports analytics system.
Analyze the user's question and extract a structured intent.

Respond with ONLY valid JSON (no markdown fences, no explanation) matching this schema:
{
    "intent_type": "metric" | "comparison" | "trend" | "ranking" | "filter",
    "entities": {
        "athletes": ["athlete names"] or null,
        "teams": ["A", "B"] or null,
        "positions": ["Forward", "Midfielder", "Defender"] or null,
        "time_range": "description of time range" or null,
        "session_type": "Training" or "Match" or null,
        "metric": "the primary metric being asked about" or null
    },
    "visualization_hint": "bar_chart" | "line_chart" | "table" | "single_value" | "grouped_bar"
}

Intent type guide:
- "metric": asking for a single number or simple stat
- "comparison": comparing groups/categories
- "trend": looking at changes over time
- "ranking": asking for top/bottom/best/worst
- "filter": looking for items matching criteria

Visualization guide:
- "line_chart": for trends over time
- "bar_chart": for comparisons between categories
- "grouped_bar": for comparing multiple metrics across categories
- "single_value": when result is one number
- "table": for detailed multi-column results

User query: {query}
"""


async def classify_intent(query: str) -> dict:
    """Classify a natural language query into structured intent."""
    client = _get_client()
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=500,
        temperature=0,
        messages=[{"role": "user", "content": CLASSIFICATION_PROMPT.format(query=query)}],
    )

    text = message.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "intent_type": "metric",
            "entities": {},
            "visualization_hint": "table",
        }
