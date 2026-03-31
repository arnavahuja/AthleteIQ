import re
import sqlparse

FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "TRUNCATE",
}

ALLOWED_TABLES = {"athletes", "sessions", "gps_metrics", "wellness", "viz_dataset"}

# Map of table -> set of valid column names (built from schema)
ALLOWED_COLUMNS = {
    "athletes": {"athlete_id", "name", "position", "team"},
    "sessions": {"session_id", "athlete_id", "session_date", "duration_minutes", "session_type"},
    "gps_metrics": {"session_id", "total_distance", "sprint_distance", "high_intensity_efforts"},
    "wellness": {"athlete_id", "date", "sleep_score", "fatigue_score"},
    "viz_dataset": {"athlete", "week", "total_distance", "sprint_distance", "fatigue"},
}

# Flat set of all valid column names across all tables
ALL_COLUMNS = set()
for cols in ALLOWED_COLUMNS.values():
    ALL_COLUMNS.update(cols)


def _extract_column_references(sql: str) -> list[str]:
    """Extract column references from SQL, handling table.column and bare column names."""
    # Remove string literals
    cleaned = re.sub(r"'[^']*'", "''", sql)
    cleaned = re.sub(r'"[^"]*"', '""', cleaned)

    # Find table.column references
    qualified_refs = re.findall(r'(\w+)\.(\w+)', cleaned)

    # Find bare column names in SELECT, WHERE, ON, ORDER BY, GROUP BY, HAVING
    # We check these against the flat set of all columns
    bare_candidates = re.findall(r'\b(\w+)\b', cleaned)

    return qualified_refs, bare_candidates


def _extract_table_aliases(sql: str) -> dict[str, str]:
    """Extract table aliases from FROM and JOIN clauses. Returns alias -> table_name."""
    cleaned = re.sub(r"'[^']*'", "''", sql)
    cleaned = re.sub(r'"[^"]*"', '""', cleaned)

    aliases = {}
    # Match: FROM/JOIN table_name alias  or  FROM/JOIN table_name AS alias
    pattern = r'(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
    for match in re.finditer(pattern, cleaned, re.IGNORECASE):
        table = match.group(1).lower()
        alias = match.group(2)
        if table in ALLOWED_TABLES:
            aliases[table] = table  # table name maps to itself
            if alias and alias.lower() not in (
                'on', 'where', 'join', 'inner', 'left', 'right', 'outer',
                'cross', 'natural', 'group', 'order', 'having', 'limit',
                'union', 'set', 'and', 'or',
            ):
                aliases[alias.lower()] = table
    return aliases


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validate generated SQL for safety and correctness.

    Returns (is_valid, error_message).
    """
    sql = sql.strip()

    # Check 1: Non-empty
    if not sql:
        return False, "Empty SQL query"

    # Check 2: Single statement
    statements = sqlparse.split(sql)
    if len(statements) > 1:
        return False, "Multiple SQL statements detected. Only single SELECT allowed."

    # Check 3: Starts with SELECT
    parsed = sqlparse.parse(sql)
    if not parsed:
        return False, "Failed to parse SQL"

    first_token = None
    for token in parsed[0].tokens:
        if not token.is_whitespace:
            first_token = token
            break

    if first_token is None or first_token.ttype not in (sqlparse.tokens.Keyword.DML, sqlparse.tokens.Keyword):
        return False, "SQL must start with SELECT"

    if first_token.value.upper() != "SELECT":
        return False, f"SQL must start with SELECT, got '{first_token.value}'"

    # Check 4: No forbidden keywords (outside string literals)
    sql_no_strings = re.sub(r"'[^']*'", "''", sql)
    sql_no_strings = re.sub(r'"[^"]*"', '""', sql_no_strings)
    tokens_upper = sql_no_strings.upper().split()
    for token in tokens_upper:
        clean = re.sub(r"[^A-Z]", "", token)
        if clean in FORBIDDEN_KEYWORDS:
            return False, f"Forbidden keyword detected: {clean}"

    # Check 5: Verify table references are allowed
    table_pattern = r'(?:FROM|JOIN)\s+(\w+)'
    referenced_tables = re.findall(table_pattern, sql_no_strings, re.IGNORECASE)
    for table in referenced_tables:
        if table.lower() not in ALLOWED_TABLES:
            return False, f"Unknown table referenced: '{table}'. Allowed: {ALLOWED_TABLES}"

    # Check 6: Check for comment injection
    if "--" in sql_no_strings or "/*" in sql_no_strings:
        return False, "SQL comments not allowed"

    # Check 7: Validate column references against schema
    aliases = _extract_table_aliases(sql)
    qualified_refs, _ = _extract_column_references(sql)

    invalid_cols = []
    for table_or_alias, col in qualified_refs:
        table_or_alias_lower = table_or_alias.lower()
        col_lower = col.lower()
        # Resolve alias to table name
        actual_table = aliases.get(table_or_alias_lower)
        if actual_table and actual_table in ALLOWED_COLUMNS:
            if col_lower not in ALLOWED_COLUMNS[actual_table]:
                valid_cols = ", ".join(sorted(ALLOWED_COLUMNS[actual_table]))
                invalid_cols.append(
                    f"Column '{col}' does not exist in table '{actual_table}'. "
                    f"Valid columns: {valid_cols}"
                )

    if invalid_cols:
        return False, "; ".join(invalid_cols)

    return True, ""
