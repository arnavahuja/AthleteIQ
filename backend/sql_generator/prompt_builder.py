"""
Assembles the LLM prompt entirely from RAG-retrieved context.
Combined intent classification + SQL generation in a single prompt to minimize API calls.
"""

SYSTEM_RULES = """You are a SQL expert for a SQLite sports analytics database.
Your job: analyze the user's question, then generate a single SELECT query.

Respond with ONLY valid JSON (no markdown fences) in this exact format:
{
    "intent_type": "metric|comparison|trend|ranking|filter",
    "visualization_hint": "bar_chart|line_chart|table|single_value|grouped_bar",
    "sql": "SELECT ..."
}

Intent types:
- "metric": single number or stat
- "comparison": comparing groups/categories
- "trend": changes over time
- "ranking": top/bottom/best/worst
- "filter": items matching criteria

Visualization: "line_chart" for trends, "bar_chart" for comparisons, "grouped_bar" for multiple metrics across categories, "single_value" for one number, "table" for detailed results.

SQL RULES:
- Generate ONLY a SELECT statement. Never DROP, DELETE, UPDATE, INSERT, ALTER, CREATE.
- Use ONLY the tables and columns listed in the schema below.
- Use explicit JOIN syntax (never implicit comma joins).
- For aggregations, always include appropriate GROUP BY.
- Use aliases for computed columns (e.g., AVG(x) as avg_x).
"""


def build_prompt(query: str, intent: dict, rag_context: dict, conversation_history: list[dict] | None = None) -> str:
    """
    Assemble the prompt from RAG-retrieved context.
    Returns a single prompt that does BOTH intent classification and SQL generation.
    Includes recent conversation history for follow-up query understanding.
    """
    sections = [SYSTEM_RULES]

    # Conversation history for follow-up queries
    if conversation_history:
        # Keep last 3 exchanges max to stay efficient
        recent = conversation_history[-6:]
        history_lines = []
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            sql = msg.get("sql", "")
            if role == "user":
                history_lines.append(f"User: {content}")
            elif role == "assistant" and sql:
                history_lines.append(f"Assistant answered with SQL: {sql}")
                summary = msg.get("summary", "")
                if summary:
                    history_lines.append(f"Result summary: {summary}")
        if history_lines:
            sections.append(
                "CONVERSATION HISTORY (use this to understand follow-up questions):\n"
                + "\n".join(history_lines)
            )

    # Schema context
    schema_chunks = rag_context.get("schema", [])
    if schema_chunks:
        schema_text = "\n\n".join(c["content"] for c in schema_chunks)
        sections.append(f"RELEVANT DATABASE SCHEMA:\n{schema_text}")

    # KPI definitions
    kpi_chunks = rag_context.get("kpi", [])
    if kpi_chunks:
        kpi_text = "\n\n".join(c["content"] for c in kpi_chunks)
        sections.append(f"RELEVANT METRIC DEFINITIONS:\n{kpi_text}")

    # Similar examples
    example_chunks = rag_context.get("example", [])
    if example_chunks:
        example_text = "\n\n".join(c["content"] for c in example_chunks)
        sections.append(f"SIMILAR QUERIES AND THEIR SQL:\n{example_text}")

    # Business rules
    rule_chunks = rag_context.get("rule", [])
    if rule_chunks:
        rule_text = "\n\n".join(c["content"] for c in rule_chunks)
        sections.append(f"BUSINESS RULES TO CONSIDER:\n{rule_text}")

    # User query
    sections.append(f"USER QUERY: {query}\n\nRespond with the JSON:")

    return "\n\n---\n\n".join(sections)


def build_retry_prompt(original_prompt: str, sql: str, error: str) -> str:
    """Build a retry prompt that includes the previous error."""
    return (
        f"{original_prompt}\n\n"
        f"YOUR PREVIOUS ATTEMPT:\n{sql}\n\n"
        f"ERROR: {error}\n\n"
        f"Fix the error and generate a corrected JSON response:"
    )
