SCHEMA = {
    "athletes": {
        "ddl": """CREATE TABLE IF NOT EXISTS athletes (
            athlete_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            team TEXT NOT NULL
        )""",
        "columns": [
            {"name": "athlete_id", "type": "INTEGER", "pk": True, "description": "Unique athlete identifier"},
            {"name": "name", "type": "TEXT", "description": "Full name (e.g. 'James Smith')"},
            {"name": "position", "type": "TEXT", "description": "Player position: Forward, Midfielder, or Defender"},
            {"name": "team", "type": "TEXT", "description": "Team assignment: A or B"},
        ],
        "relationships": [],
        "use_when": "Looking up athlete details, filtering by position or team, joining to other tables via athlete_id.",
    },
    "sessions": {
        "ddl": """CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY,
            athlete_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            session_type TEXT NOT NULL
        )""",
        "columns": [
            {"name": "session_id", "type": "INTEGER", "pk": True, "description": "Unique session identifier, FK to gps_metrics"},
            {"name": "athlete_id", "type": "INTEGER", "fk": "athletes.athlete_id", "description": "Foreign key to athletes table"},
            {"name": "session_date", "type": "TEXT", "description": "Date in M/D/YYYY format (e.g. '1/1/2026')"},
            {"name": "duration_minutes", "type": "INTEGER", "description": "Session length in minutes"},
            {"name": "session_type", "type": "TEXT", "description": "Either 'Training' or 'Match'"},
        ],
        "relationships": ["sessions.athlete_id -> athletes.athlete_id"],
        "use_when": "Querying session details, filtering by date or session type, joining athlete info to GPS metrics.",
    },
    "gps_metrics": {
        "ddl": """CREATE TABLE IF NOT EXISTS gps_metrics (
            session_id INTEGER PRIMARY KEY,
            total_distance INTEGER NOT NULL,
            sprint_distance INTEGER NOT NULL,
            high_intensity_efforts INTEGER NOT NULL
        )""",
        "columns": [
            {"name": "session_id", "type": "INTEGER", "pk": True, "fk": "sessions.session_id", "description": "Foreign key to sessions table"},
            {"name": "total_distance", "type": "INTEGER", "description": "Total distance covered in meters"},
            {"name": "sprint_distance", "type": "INTEGER", "description": "Distance covered at sprint speed in meters"},
            {"name": "high_intensity_efforts", "type": "INTEGER", "description": "Count of high-intensity efforts during session"},
        ],
        "relationships": ["gps_metrics.session_id -> sessions.session_id"],
        "use_when": "Querying performance metrics (distance, sprints, intensity). Must JOIN through sessions to reach athletes.",
    },
    "wellness": {
        "ddl": """CREATE TABLE IF NOT EXISTS wellness (
            athlete_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            sleep_score INTEGER NOT NULL,
            fatigue_score INTEGER NOT NULL,
            PRIMARY KEY (athlete_id, date)
        )""",
        "columns": [
            {"name": "athlete_id", "type": "INTEGER", "fk": "athletes.athlete_id", "description": "Foreign key to athletes table"},
            {"name": "date", "type": "TEXT", "description": "Date in M/D/YYYY format (e.g. '1/1/2026')"},
            {"name": "sleep_score", "type": "INTEGER", "description": "Sleep quality score 0-100, higher is better"},
            {"name": "fatigue_score", "type": "INTEGER", "description": "Fatigue level 0-100, higher means MORE fatigued"},
        ],
        "relationships": ["wellness.athlete_id -> athletes.athlete_id"],
        "use_when": "Querying wellness data (sleep, fatigue). Join to athletes for names/positions.",
    },
    "viz_dataset": {
        "ddl": """CREATE TABLE IF NOT EXISTS viz_dataset (
            athlete TEXT NOT NULL,
            week TEXT NOT NULL,
            total_distance INTEGER NOT NULL,
            sprint_distance INTEGER NOT NULL,
            fatigue INTEGER NOT NULL,
            PRIMARY KEY (athlete, week)
        )""",
        "columns": [
            {"name": "athlete", "type": "TEXT", "description": "Athlete full name (matches athletes.name)"},
            {"name": "week", "type": "TEXT", "description": "Week label: Week1, Week2, or Week3"},
            {"name": "total_distance", "type": "INTEGER", "description": "Weekly total distance in meters"},
            {"name": "sprint_distance", "type": "INTEGER", "description": "Weekly sprint distance in meters"},
            {"name": "fatigue", "type": "INTEGER", "description": "Fatigue score for that week (0-100)"},
        ],
        "relationships": [],
        "use_when": "Pre-aggregated weekly summary. Use for weekly trends, week-over-week comparisons, multi-week athlete analysis. Prefer this over manual aggregation from sessions+gps_metrics when weekly granularity is sufficient.",
    },
}


def get_schema_summary() -> str:
    """Return a compact text summary of the full schema for debugging/API."""
    lines = []
    for table_name, info in SCHEMA.items():
        cols = ", ".join(
            f"{c['name']} {c['type']}" for c in info["columns"]
        )
        lines.append(f"{table_name}({cols})")
        for rel in info.get("relationships", []):
            lines.append(f"  Relationship: {rel}")
    return "\n".join(lines)
