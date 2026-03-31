from backend.data_pipeline.db import get_connection


def execute_query(sql: str) -> dict:
    """
    Execute a validated SQL query against the read-only database.

    Returns:
        {"columns": [...], "rows": [[...], ...], "row_count": int}
        or {"error": str, "columns": [], "rows": [], "row_count": 0}
    """
    try:
        conn = get_connection(read_only=True)
        cursor = conn.execute(sql)
        columns = [description[0] for description in cursor.description] if cursor.description else []
        rows = [list(row) for row in cursor.fetchall()]
        conn.close()

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }

    except Exception as e:
        return {
            "error": str(e),
            "columns": [],
            "rows": [],
            "row_count": 0,
        }
