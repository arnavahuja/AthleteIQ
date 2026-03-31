import csv
import os
import sqlite3

from backend.config import settings
from .schema import SCHEMA

CSV_TABLE_MAP = {
    "athletes.csv": "athletes",
    "sessions.csv": "sessions",
    "gps_metrics.csv": "gps_metrics",
    "wellness.csv": "wellness",
    "viz_dataset.csv": "viz_dataset",
}

# Order matters for foreign key constraints
LOAD_ORDER = ["athletes", "sessions", "gps_metrics", "wellness", "viz_dataset"]


def ingest_all() -> None:
    """Create tables and load all CSVs into SQLite. Idempotent."""
    conn = sqlite3.connect(settings.db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Create tables in dependency order
    for table_name in LOAD_ORDER:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute(SCHEMA[table_name]["ddl"])

    # Load CSVs
    csv_to_table = {v: k for k, v in CSV_TABLE_MAP.items()}
    for table_name in LOAD_ORDER:
        csv_file = csv_to_table[table_name]
        filepath = os.path.join(settings.data_dir, csv_file)
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found, skipping {table_name}")
            continue

        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
            if not cols:
                continue
            placeholders = ",".join(["?"] * len(cols))
            col_names = ",".join(cols)
            for row in reader:
                conn.execute(
                    f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                    [row[c].strip() for c in cols],
                )

    conn.commit()
    conn.close()
    print(f"Data ingestion complete. DB at: {settings.db_path}")
