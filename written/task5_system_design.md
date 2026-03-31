# Task 5: Designing a Reliable Natural Language Query System

## The Challenge

In a real sports analytics environment, the SQL databases are large and complex, tables are layered on top of each other, and metrics are defined across multiple joins and transformations. A naive "send the question to an LLM and hope for good SQL" approach fails quickly. Here's how I would design for reliability.

---

## 1. Schema Abstraction Layer

**Problem**: LLMs hallucinate column names, confuse table relationships, and generate syntactically correct but semantically wrong SQL when given raw DDL or no schema context.

**Solution**: Maintain a curated **semantic schema registry** — a structured metadata layer that sits between the raw database and the LLM. For each table, this includes:

- Human-readable column descriptions (not just types)
- Valid value enumerations (e.g., `position IN ('Forward', 'Midfielder', 'Defender')`)
- Relationship annotations with directionality (e.g., "to get GPS metrics for an athlete, you MUST join through sessions")
- Usage hints (e.g., "use viz_dataset for weekly trends, use sessions+gps_metrics for session-level analysis")

This registry is what gets embedded and retrieved via RAG — the LLM never sees raw DDL. The abstraction constrains the LLM's output space to known, valid entities.

**Why this works**: In testing, providing annotated column descriptions (e.g., "fatigue_score: 0-100, higher means MORE fatigued") eliminates the most common failure mode: the LLM inverting the meaning of a metric (e.g., ranking by fatigue DESC when it should be ASC, or vice versa).

---

## 2. Metric Definitions as First-Class Objects

**Problem**: "Average sprint distance" is ambiguous — it could mean per-session, per-athlete, per-week, or a rolling window. Without explicit definitions, the LLM guesses, and guesses differently each time.

**Solution**: Define every metric (KPI) as a structured object:

```
KPI: avg_sprint_distance
Description: Average sprint distance per session
Relevant tables: sessions, gps_metrics, athletes
SQL pattern: SELECT a.name, AVG(g.sprint_distance) FROM athletes a
             JOIN sessions s ON ... JOIN gps_metrics g ON ...
             GROUP BY a.name
```

These definitions are embedded and retrieved via RAG. When a user asks "how fast are the forwards sprinting?", the retriever matches this to `position_sprint_profile`, and the SQL generator gets an unambiguous computation specification.

**Key insight**: The KPI definition includes a SQL pattern, not just a description. This gives the LLM a concrete template to follow rather than generating the aggregation logic from scratch. For complex metrics involving window functions or multi-table joins, this dramatically reduces errors.

---

## 3. Precomputation

**Problem**: Complex KPIs involving window functions, CTEs, or 4+ table joins are where LLMs fail most often. The more complex the SQL, the higher the error rate.

**Solution**: Precompute frequently-used metrics into materialized summary tables. For example:

- `weekly_athlete_summary`: Pre-joined athlete + session + GPS data, aggregated per week
- `athlete_baselines`: Per-athlete averages for all key metrics
- `daily_wellness_trends`: Wellness data with rolling averages

The `viz_dataset` table in our assessment is exactly this pattern — pre-aggregated weekly data that eliminates the need for complex multi-table joins.

**Trade-off**: Precomputation adds a data pipeline maintenance burden and introduces staleness (summaries are only as fresh as the last pipeline run). The mitigation is clear freshness metadata: each summary table records when it was last refreshed, and the system can fall back to raw-table queries if summaries are stale.

---

## 4. Multi-Layer Validation Pipeline

A single point of validation is insufficient. I use 5 layers:

| Layer | Type | What it catches |
|-------|------|-----------------|
| **1. Syntax/Safety** | Regex + AST | DROP, DELETE, multi-statement injection, comments |
| **2. Schema validation** | Deterministic | Hallucinated table/column names, invalid table references |
| **3. Read-only connection** | Database-level | Any mutation that slipped past layers 1-2 |
| **4. Result sanity check** | Heuristic | 0 rows returned (likely wrong query), all-NULL columns |
| **5. User confirmation** | Human-in-loop | Ambiguous queries get a clarification prompt ("Did you mean Team A or Team B?") |

Layers 1-3 are hard gates (fail = reject). Layers 4-5 are soft signals that trigger warnings or follow-up questions.

---

## 5. RAG-Driven Dynamic Context Assembly

**Problem**: Large schemas with 100+ tables can't fit in a single prompt. Static few-shot examples may not be relevant to the current query.

**Solution**: Embed ALL schema knowledge, KPI definitions, example queries, and business rules into a unified vector store. At query time:

1. Embed the user's question
2. Retrieve only the relevant chunks (top-k per type)
3. Assemble a prompt that is **tailored to this specific query**

A query about "fatigue trends" gets wellness schema + fatigue KPIs + trend examples + fatigue threshold rules. A query about "sprint by position" gets GPS schema + sprint KPIs + comparison examples + position rules.

This approach scales because the prompt size stays constant regardless of total schema size — only relevant context is included.

---

## 6. Additional Considerations

**Disambiguation**: When the intent classifier detects ambiguity (e.g., "last week" with no date anchor), the system should ask for clarification rather than guess. This is cheaper than generating wrong SQL and losing user trust.

**Query templates**: For the 20-30 most common query patterns, maintain verified SQL templates that the system can select via classification rather than generation. Template-based queries are 100% reliable; generative queries are the fallback.

**Audit trail**: Every query logs: user question → intent → retrieved context → generated SQL → execution result → user feedback. This enables systematic improvement (see Task 6).
