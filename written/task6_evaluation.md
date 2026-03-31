# Task 6: Evaluating and Improving the System

## 1. Measuring Correctness and Usefulness

### 1a. SQL Correctness

**Approach**: Build a **golden test suite** of 30-50 (question, expected_result) pairs. Critically, we compare **results**, not SQL text — multiple valid SQL queries can produce the same correct answer.

```
Test case:
  Question: "Which athlete has the highest total distance?"
  Expected result: Contains "James Smith" or "Oliver Brown" in first row
  Expected columns: includes "name" and a distance-related column
  Expected row count: >= 1
```

**Metrics**:
- **Execution success rate**: % of generated queries that execute without errors
- **Result accuracy**: % of queries where results match the golden set (exact match for numeric values, semantic match for structures)
- **Schema compliance**: % of queries that only reference valid tables and columns (caught by validator before execution)

**Automation**: Run the test suite on every prompt template change. Track accuracy over time. If accuracy drops below 80%, block the change.

### 1b. Usefulness of Responses

**Metrics**:
- **Relevance**: Does the response answer the actual question asked? (Human evaluation rubric: 0 = irrelevant, 1 = partially relevant, 2 = fully relevant)
- **Completeness**: Does it include all requested information? (e.g., if the user asked about "all athletes," does it actually include all 15?)
- **Visualization appropriateness**: Was the right chart type selected? Did it highlight the insight the user was looking for?

**Automated proxy**: Track **follow-up rate** — if a user immediately asks a similar question, the first response was likely insufficient. Low follow-up rate correlates with high usefulness.

---

## 2. Most Likely Failure Modes

### 2a. Wrong Table Selection
**What happens**: LLM uses `viz_dataset` when it should use `sessions + gps_metrics`, or vice versa.
**Why**: Both tables contain distance data, but at different granularities (weekly vs. session-level).
**Frequency**: High — this is the #1 failure mode in text-to-SQL systems with overlapping tables.

### 2b. Ambiguous Time References
**What happens**: User says "last week" but the data doesn't have a concept of "current date." The LLM either ignores the time filter or generates an incorrect date comparison.
**Why**: Natural language time references are inherently relative; the system needs an anchor.
**Frequency**: Medium — depends on how often users include time references.

### 2c. Hallucinated Columns or Values
**What happens**: LLM invents a column name (e.g., `athlete_name` instead of `name`) or a value (e.g., `position = 'Striker'` when only Forward/Midfielder/Defender exist).
**Why**: The LLM's training data includes many different schemas; it may import conventions from other datasets.
**Frequency**: Medium — reduced significantly by schema injection in the prompt, but not eliminated.

### 2d. Aggregation Errors
**What happens**: Wrong GROUP BY (aggregating at wrong granularity), missing aggregation (selecting non-aggregated columns alongside aggregates), or wrong aggregation function (SUM instead of AVG).
**Why**: Aggregation requires understanding the user's intended level of detail, which is often implicit.
**Frequency**: Medium.

### 2e. Join Path Errors
**What happens**: LLM joins tables incorrectly (e.g., joining athletes directly to gps_metrics, skipping the sessions table in the middle).
**Why**: The relationship athletes → sessions → gps_metrics is indirect; the LLM may try to shortcut.
**Frequency**: Medium — mitigated by relationship annotations in schema chunks.

### 2f. Speech Transcription Errors
**What happens**: Athlete name misheard (e.g., "James myth" instead of "James Smith").
**Why**: Domain-specific names may not be in the speech model's vocabulary.
**Frequency**: Low (voice path only) but high impact when it occurs.

---

## 3. Detection and Mitigation

### 3a. Automated Detection

| Signal | What it detects | Action |
|--------|----------------|--------|
| 0 rows returned | Wrong WHERE clause, wrong table, wrong join | Log as potential failure; suggest broader query |
| SQL execution error | Syntax errors, invalid references | Retry with error feedback; log for prompt improvement |
| All values NULL | Wrong column selection | Flag to user; suggest rephrasing |
| User re-asks similar question | First response was unsatisfactory | Log the pair for training data |
| Validator rejection | Unsafe or invalid SQL | Block execution; retry once; if still failing, return error |
| Anomalous result size | Returns entire table (missing WHERE) or single row (missing GROUP BY) | Sanity check: warn if result seems too large or too small for the question |

### 3b. Mitigation Strategies

**For wrong table selection**: Include explicit "Use when" annotations in schema chunks. Add negative examples: "Do NOT use viz_dataset for session-level queries."

**For ambiguous time references**: Inject current date into the prompt context. Maintain a date-parsing module that converts "last week" to a concrete date range before SQL generation.

**For hallucinated columns**: The schema validator (Layer 2) catches this before execution. On failure, the retry prompt explicitly lists the correct columns.

**For aggregation errors**: Include aggregation patterns in the few-shot examples. Cover every GROUP BY pattern the system should know.

**For join path errors**: The "Technical Rule" business chunks explicitly document required join paths: "To get athlete GPS data, join athletes → sessions → gps_metrics."

**For speech errors**: The transcription confirmation step (showing "I heard: '...'" with edit option) catches most errors. Additionally, fuzzy-match extracted entity names against known athletes (e.g., Levenshtein distance < 3 → suggest correction).

### 3c. Continuous Improvement Loop

1. **Log everything**: question → intent → retrieved context → SQL → result → user feedback
2. **Weekly review**: Analyze failed queries. Identify patterns.
3. **Improve knowledge base**: Add new example chunks for failure patterns. Refine business rules.
4. **Re-embed and test**: Update embeddings, run the golden test suite.
5. **Canary queries**: A set of 10 known-good queries that run on schedule. If any fail, alert immediately — this catches prompt regression.

### 3d. Evaluation Metrics Dashboard

Track over time:
- SQL execution success rate (target: >95%)
- Result accuracy against golden set (target: >85%)
- Average response latency (target: <5s)
- RAG retrieval relevance (target: top-1 chunk is relevant >90% of the time)
- User satisfaction proxy: re-ask rate (target: <15%)
