import sqlite3
from backend.config import settings


def get_connection(read_only: bool = False) -> sqlite3.Connection:
    """Get a SQLite connection. Use read_only=True for query execution."""
    if read_only:
        uri = f"file:{settings.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
    else:
        conn = sqlite3.connect(settings.db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
