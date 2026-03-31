import anthropic
from backend.config import settings

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


SUMMARY_PROMPT = """You are a sports analytics assistant briefing a coach. Given the user's question and the query results, provide a clear, insightful answer.

Guidelines:
- Directly answer the question with specific numbers and athlete names
- Highlight key insights: who stands out, notable patterns, comparisons worth attention
- If there are trends (increasing/decreasing), call them out
- If values are concerning (high fatigue, low sleep), flag it
- Use plain language, no jargon. Do not mention SQL, databases, or queries
- Format your answer in 2-4 sentences. Be concise but thorough

User question: {query}

Results ({row_count} rows):
Columns: {columns}
Data:
{data_preview}

Your analysis:"""


def _generate_simple_summary(columns: list, rows: list, row_count: int) -> str:
    """Generate a basic summary without an LLM call. Used as fallback."""
    if row_count == 1 and len(columns) <= 3:
        parts = [f"{col}: {val}" for col, val in zip(columns, rows[0])]
        return "Result: " + ", ".join(parts) + "."

    if row_count <= 5:
        first_col = columns[0] if columns else "Item"
        items = [str(row[0]) for row in rows[:5]]
        return f"Found {row_count} results. {first_col}s: {', '.join(items)}."

    return f"Found {row_count} results across {len(columns)} columns."


async def format_response(query: str, sql_result: dict, use_llm: bool = True) -> str:
    """Generate a natural language summary of SQL results."""
    columns = sql_result.get("columns", [])
    rows = sql_result.get("rows", [])
    row_count = sql_result.get("row_count", 0)

    if row_count == 0:
        return "No data found matching your query. Try rephrasing or broadening your question."

    if not use_llm:
        return _generate_simple_summary(columns, rows, row_count)

    # Format all data (up to 20 rows for context)
    preview_rows = rows[:20]
    header = " | ".join(columns)
    data_lines = [header, "-" * len(header)]
    for row in preview_rows:
        data_lines.append(" | ".join(str(v) for v in row))
    if row_count > 20:
        data_lines.append(f"... and {row_count - 20} more rows")
    data_preview = "\n".join(data_lines)

    prompt = SUMMARY_PROMPT.format(
        query=query,
        row_count=row_count,
        columns=", ".join(columns),
        data_preview=data_preview,
    )

    try:
        client = _get_client()
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=500,
            temperature=0.5,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception:
        return _generate_simple_summary(columns, rows, row_count)
