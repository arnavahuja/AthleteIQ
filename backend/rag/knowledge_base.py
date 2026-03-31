"""
Builds the knowledge base chunks from data sources.
Four chunk types: schema, kpi, example, rule.
"""

import csv
import os

from backend.config import settings
from backend.data_pipeline.schema import SCHEMA


def build_schema_chunks() -> list[dict]:
    """One chunk per table describing its structure and usage."""
    chunks = []
    for table_name, info in SCHEMA.items():
        col_lines = []
        for col in info["columns"]:
            parts = [f"- {col['name']} ({col['type']})"]
            if col.get("pk"):
                parts.append("[PK]")
            if col.get("fk"):
                parts.append(f"[FK -> {col['fk']}]")
            parts.append(f": {col['description']}")
            col_lines.append(" ".join(parts))

        relationships = info.get("relationships", [])
        rel_text = "\n".join(f"  {r}" for r in relationships) if relationships else "  None"

        content = (
            f"Table: {table_name}\n"
            f"Columns:\n" + "\n".join(col_lines) + "\n"
            f"Relationships:\n{rel_text}\n"
            f"Use when: {info.get('use_when', 'N/A')}"
        )

        chunks.append({
            "type": "schema",
            "name": f"{table_name}_table",
            "content": content,
        })
    return chunks


def build_kpi_chunks() -> list[dict]:
    """One chunk per KPI from KPIs.csv, enriched with SQL computation hints."""
    chunks = []
    kpi_path = os.path.join(settings.data_dir, "KPIs.csv")
    if not os.path.exists(kpi_path):
        return chunks

    # SQL patterns for known KPIs (manually curated for quality)
    sql_patterns = {
        "avg_total_distance": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.name, AVG(g.total_distance) as avg_total_distance FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.name",
        },
        "avg_sprint_distance": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.name, AVG(g.sprint_distance) as avg_sprint_distance FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.name",
        },
        "total_high_intensity": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.name, SUM(g.high_intensity_efforts) as total_hi FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.name",
        },
        "distance_per_minute": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.name, ROUND(1.0 * g.total_distance / s.duration_minutes, 2) as dist_per_min FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id",
        },
        "fatigue_trend": {
            "tables": "wellness, athletes",
            "sql": "SELECT a.name, w.date, w.fatigue_score FROM wellness w JOIN athletes a ON w.athlete_id = a.athlete_id ORDER BY a.name, w.date",
        },
        "sleep_quality_avg": {
            "tables": "wellness, athletes",
            "sql": "SELECT a.name, AVG(w.sleep_score) as avg_sleep FROM wellness w JOIN athletes a ON w.athlete_id = a.athlete_id GROUP BY a.name",
        },
        "match_vs_training_distance": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.name, s.session_type, AVG(g.total_distance) as avg_dist FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.name, s.session_type",
        },
        "position_sprint_profile": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.position, AVG(g.sprint_distance) as avg_sprint FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.position",
        },
        "team_total_load": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.team, SUM(g.total_distance) as team_load FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.team",
        },
        "high_intensity_rate": {
            "tables": "sessions, gps_metrics, athletes",
            "sql": "SELECT a.name, ROUND(1.0 * g.high_intensity_efforts / s.duration_minutes, 2) as hi_rate FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id",
        },
    }

    with open(kpi_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kpi_name = row["kpi_name"].strip()
            description = row["description"].strip()

            pattern = sql_patterns.get(kpi_name, {})
            tables = pattern.get("tables", "varies")
            sql = pattern.get("sql", "N/A")

            content = (
                f"KPI: {kpi_name}\n"
                f"Description: {description}\n"
                f"Relevant tables: {tables}\n"
                f"SQL pattern: {sql}"
            )

            chunks.append({
                "type": "kpi",
                "name": kpi_name,
                "content": content,
            })

    return chunks


def build_example_chunks() -> list[dict]:
    """Curated query-SQL pairs that serve as retrievable few-shot examples."""
    examples = [
        {
            "name": "highest_workload",
            "question": "Which athletes had the highest workload last week?",
            "sql": "SELECT a.name, SUM(g.total_distance) as total_workload FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.name ORDER BY total_workload DESC",
            "pattern": "Ranking query. SUM aggregation on total_distance, joins athletes->sessions->gps_metrics, ORDER BY DESC.",
        },
        {
            "name": "avg_sprint_by_position",
            "question": "Show average sprint distance by position over the last 30 days.",
            "sql": "SELECT a.position, AVG(g.sprint_distance) as avg_sprint FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.position",
            "pattern": "Comparison/grouping query. AVG aggregation, GROUP BY position.",
        },
        {
            "name": "below_baseline",
            "question": "Who is trending below their baseline performance?",
            "sql": "SELECT a.name, w.date, w.fatigue_score, w.sleep_score FROM wellness w JOIN athletes a ON w.athlete_id = a.athlete_id WHERE w.fatigue_score > 45 OR w.sleep_score < 75 ORDER BY w.fatigue_score DESC",
            "pattern": "Filter query. Identifies athletes with high fatigue or low sleep relative to baseline thresholds.",
        },
        {
            "name": "weekly_distance_trend",
            "question": "Show the weekly distance trend for all athletes.",
            "sql": "SELECT athlete, week, total_distance FROM viz_dataset ORDER BY athlete, week",
            "pattern": "Trend query. Uses viz_dataset (pre-aggregated weekly data). ORDER BY week for time series.",
        },
        {
            "name": "fatigue_over_time",
            "question": "How has fatigue changed over time for James Smith?",
            "sql": "SELECT week, fatigue FROM viz_dataset WHERE athlete = 'James Smith' ORDER BY week",
            "pattern": "Trend query for specific athlete. Filters viz_dataset by name, orders by week.",
        },
        {
            "name": "match_vs_training",
            "question": "Compare match vs training distances for all athletes.",
            "sql": "SELECT a.name, s.session_type, AVG(g.total_distance) as avg_distance FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.name, s.session_type ORDER BY a.name",
            "pattern": "Comparison query. GROUP BY session_type to compare match vs training.",
        },
        {
            "name": "team_comparison",
            "question": "Compare total workload between Team A and Team B.",
            "sql": "SELECT a.team, SUM(g.total_distance) as total_load FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.team",
            "pattern": "Team-level aggregation. GROUP BY team.",
        },
        {
            "name": "top_sprinters",
            "question": "Who are the top sprinters on the team?",
            "sql": "SELECT a.name, a.position, SUM(g.sprint_distance) as total_sprint FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY a.name, a.position ORDER BY total_sprint DESC",
            "pattern": "Ranking query on sprint_distance. Includes position for context.",
        },
        {
            "name": "sleep_quality_ranking",
            "question": "Which athletes have the best sleep quality?",
            "sql": "SELECT a.name, AVG(w.sleep_score) as avg_sleep FROM wellness w JOIN athletes a ON w.athlete_id = a.athlete_id GROUP BY a.name ORDER BY avg_sleep DESC",
            "pattern": "Ranking query on wellness data. AVG sleep_score, ORDER BY DESC.",
        },
        {
            "name": "high_intensity_by_session_type",
            "question": "How do high intensity efforts differ between matches and training?",
            "sql": "SELECT s.session_type, AVG(g.high_intensity_efforts) as avg_hi FROM sessions s JOIN gps_metrics g ON s.session_id = g.session_id GROUP BY s.session_type",
            "pattern": "Comparison query. GROUP BY session_type, AVG on high_intensity_efforts.",
        },
        {
            "name": "most_fatigued_athletes",
            "question": "Which athletes are most fatigued right now?",
            "sql": "SELECT a.name, w.fatigue_score, w.sleep_score FROM wellness w JOIN athletes a ON w.athlete_id = a.athlete_id ORDER BY w.fatigue_score DESC LIMIT 5",
            "pattern": "Ranking query on fatigue. ORDER BY fatigue_score DESC, LIMIT for top N.",
        },
        {
            "name": "distance_per_minute_efficiency",
            "question": "Which athletes cover the most distance per minute?",
            "sql": "SELECT a.name, ROUND(1.0 * g.total_distance / s.duration_minutes, 2) as dist_per_min FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id ORDER BY dist_per_min DESC",
            "pattern": "Efficiency metric. Computed column: total_distance / duration_minutes.",
        },
        {
            "name": "weekly_sprint_comparison",
            "question": "Compare sprint distances across weeks for all athletes.",
            "sql": "SELECT athlete, week, sprint_distance FROM viz_dataset ORDER BY athlete, week",
            "pattern": "Trend/comparison query. Uses viz_dataset for weekly granularity.",
        },
        {
            "name": "defender_vs_forward_workload",
            "question": "How does workload compare between defenders and forwards?",
            "sql": "SELECT a.position, AVG(g.total_distance) as avg_distance, AVG(g.sprint_distance) as avg_sprint FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id JOIN gps_metrics g ON s.session_id = g.session_id WHERE a.position IN ('Defender', 'Forward') GROUP BY a.position",
            "pattern": "Position comparison query. WHERE filter + GROUP BY position.",
        },
        {
            "name": "athlete_session_count",
            "question": "How many sessions has each athlete completed?",
            "sql": "SELECT a.name, COUNT(s.session_id) as session_count FROM athletes a JOIN sessions s ON a.athlete_id = s.athlete_id GROUP BY a.name ORDER BY session_count DESC",
            "pattern": "COUNT aggregation. Simple join athletes->sessions.",
        },
    ]

    chunks = []
    for ex in examples:
        content = (
            f"Question: {ex['question']}\n"
            f"SQL: {ex['sql']}\n"
            f"Pattern: {ex['pattern']}"
        )
        chunks.append({
            "type": "example",
            "name": ex["name"],
            "content": content,
        })
    return chunks


def build_rule_chunks() -> list[dict]:
    """Business rules and domain knowledge for the sports analytics context."""
    rules = [
        {
            "name": "fatigue_thresholds",
            "content": "Business Rule: Fatigue scores above 50 are considered HIGH risk. Scores 35-50 are MODERATE. Below 35 is LOW. When users ask about 'at-risk', 'tired', or 'fatigued' athletes, filter for fatigue_score > 50 (or > 45 for a broader view).",
        },
        {
            "name": "sleep_thresholds",
            "content": "Business Rule: Sleep scores below 70 indicate POOR sleep quality. Scores 70-80 are ADEQUATE. Above 80 is GOOD. When users ask about sleep issues or recovery, filter for sleep_score < 75.",
        },
        {
            "name": "workload_definition",
            "content": "Business Rule: 'Workload' in this context means total_distance covered. Higher total_distance = higher workload. Sprint distance and high-intensity efforts are separate metrics measuring intensity, not overall workload volume.",
        },
        {
            "name": "session_types",
            "content": "Business Rule: There are two session types: 'Training' and 'Match'. Match sessions typically have higher intensity and distance than training sessions. When comparing, always GROUP BY session_type.",
        },
        {
            "name": "position_characteristics",
            "content": "Business Rule: Forwards typically have the highest sprint distances. Midfielders cover the most total distance. Defenders have moderate distances. When analyzing by position, this context helps interpret results.",
        },
        {
            "name": "viz_dataset_usage",
            "content": "Business Rule: The viz_dataset table contains pre-aggregated WEEKLY data (Week1, Week2, Week3) for 6 athletes. Use it for weekly trends and week-over-week comparisons. For session-level analysis, use sessions + gps_metrics instead.",
        },
        {
            "name": "join_path_gps",
            "content": "Technical Rule: To connect athletes to their GPS metrics, you MUST join through sessions: athletes.athlete_id -> sessions.athlete_id, then sessions.session_id -> gps_metrics.session_id. There is no direct link between athletes and gps_metrics.",
        },
        {
            "name": "date_format",
            "content": "Technical Rule: Dates in sessions and wellness tables use M/D/YYYY format (e.g., '1/1/2026', '1/5/2026'). When filtering by date ranges, use string comparison or strftime() for proper date handling in SQLite.",
        },
        {
            "name": "baseline_performance",
            "content": "Business Rule: 'Baseline performance' refers to an athlete's average metrics across all their sessions. An athlete is 'below baseline' when their recent metrics (fatigue, distance, sleep) are worse than their personal average. Compare recent values to AVG across all records.",
        },
    ]

    return [{"type": "rule", **r} for r in rules]


def build_all_chunks() -> list[dict]:
    """Build all knowledge base chunks from all sources."""
    all_chunks = []
    all_chunks.extend(build_schema_chunks())
    all_chunks.extend(build_kpi_chunks())
    all_chunks.extend(build_example_chunks())
    all_chunks.extend(build_rule_chunks())
    print(f"Knowledge base: {len(all_chunks)} chunks "
          f"(schema={len(build_schema_chunks())}, "
          f"kpi={len(build_kpi_chunks())}, "
          f"example={len(build_example_chunks())}, "
          f"rule={len(build_rule_chunks())})")
    return all_chunks
