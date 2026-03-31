# AthleteIQ

RAG-powered sports analytics platform that lets coaches query athlete performance data using natural language (text or voice) and get back structured answers with interactive visualizations.

Ask questions like *"Which athletes had the highest workload?"* or *"Compare Oliver and Elijah's performance"* and get instant insights backed by real data.

## What It Does

- **Natural language queries** — ask questions in plain English, get SQL-backed answers
- **Voice input** — speak your question using the browser's Web Speech API
- **Conversational context** — follow-up queries understand prior context ("who's next best after Oliver?")
- **Interactive charts** — automatic bar, line, and grouped bar charts via Recharts
- **Smart summaries** — Claude generates coach-oriented analysis, not raw data dumps
- **Self-correcting SQL** — validates column/table references against schema and retries on errors

## Architecture

```
                         +------------------+
                         |    Frontend      |
                         |  React + Vite    |
                         |  + Recharts      |
                         +--------+---------+
                                  |
                         POST /api/query  (text + conversation history)
                         POST /api/voice  (audio blob)
                                  |
                         +--------v---------+
                         |    FastAPI        |
                         |    Backend        |
                         +--------+---------+
                                  |
              +-------------------+-------------------+
              |                                       |
     +--------v---------+                    +--------v---------+
     |  RAG Retrieval    |                    |  Speech Module   |
     |  Engine           |                    |  (Web Speech API |
     |                   |                    |   in browser)    |
     +--------+---------+                    +------------------+
              |
              |  Embed query (local sentence-transformers)
              |  Search vector store by chunk type
              |
     +--------v-----------------------------------------+
     |           Unified Vector Store (numpy)            |
     |                                                   |
     |  +----------+ +------+ +---------+ +----------+  |
     |  | Schema   | | KPI  | | Example | | Business |  |
     |  | Chunks   | | Defs | | Q&A     | | Rules    |  |
     |  | (5)      | | (10) | | (15)    | | (9)      |  |
     |  +----------+ +------+ +---------+ +----------+  |
     +---------------------------------------------------+
              |
              |  Retrieved context (top-k per type)
              |
     +--------v---------+
     |  SQL Generator    |
     |                   |
     |  1. Build prompt  |  <-- RAG context + conversation history
     |     from context  |
     |  2. Claude API    |  <-- Single LLM call (intent + SQL)
     |     (temp=0)      |
     |  3. Validate SQL  |  <-- Column-level schema validation
     |  4. Retry (max 3) |  <-- Feed errors back to Claude
     +--------+---------+
              |
     +--------v---------+
     |  Query Executor   |
     |  Read-only SQLite |
     |  5s timeout       |
     +--------+---------+
              |
     +--------v---------+        +--------------------+
     |  Response         |        |  Viz Recommender   |
     |  Formatter        |        |  (deterministic    |
     |  (Claude summary) |        |   rules, no LLM)   |
     +--------+---------+        +--------+-----------+
              |                            |
              +----------------------------+
              |
     +--------v---------+
     |  JSON Response    |
     |  {summary, table, |
     |   visualization,  |
     |   sql, context}   |
     +------------------+
```

### Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Embeddings | Local `all-MiniLM-L6-v2` (384-dim) | Zero API calls for embeddings, no rate limits |
| LLM | Claude Sonnet via Anthropic API | Reliable SQL generation, good at structured output |
| Vector store | In-memory numpy | ~39 chunks total, no external DB needed |
| RAG strategy | Type-aware retrieval (top-k per chunk type) | Ensures prompt always has schema + KPIs + examples + rules |
| SQL validation | Column-level schema checks + retry loop | Catches hallucinated columns before they hit SQLite |
| Chart selection | Deterministic rules | Faster and more predictable than LLM |
| Voice input | Browser Web Speech API | No server-side transcription costs |

## Project Structure

```
athleteiq/
├── backend/
│   ├── main.py                       # FastAPI app, lifespan startup, static file serving
│   ├── config.py                     # Settings from .env (API keys, paths)
│   ├── requirements.txt
│   ├── data_pipeline/
│   │   ├── schema.py                 # Table definitions + column metadata
│   │   ├── db.py                     # SQLite connection helper (read-only mode)
│   │   └── ingest.py                 # CSV -> SQLite loader (idempotent)
│   ├── rag/
│   │   ├── embedder.py               # Local sentence-transformers embeddings
│   │   ├── store.py                  # In-memory vector store (cosine similarity)
│   │   ├── knowledge_base.py         # Builds 39 chunks (schema, KPI, example, rule)
│   │   └── retriever.py              # Type-aware retrieval (top-k per chunk type)
│   ├── sql_generator/
│   │   ├── prompt_builder.py         # Assembles prompt from RAG context + history
│   │   ├── generator.py              # Claude API call + retry loop (max 3)
│   │   └── validator.py              # Column-level schema validation
│   ├── query_executor/
│   │   └── executor.py               # Read-only SQLite execution, 5s timeout
│   ├── response/
│   │   ├── formatter.py              # Claude-powered natural language summaries
│   │   └── viz_recommender.py        # Deterministic chart type selection
│   ├── speech/
│   │   └── transcribe.py             # Placeholder (transcription is browser-side)
│   └── api/
│       └── routes.py                 # POST /query, POST /voice, GET /health, GET /schema
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                   # Root layout
│       ├── main.jsx                  # Entry point
│       ├── api/client.js             # API client (relative URLs in prod)
│       ├── components/
│       │   ├── ChatInterface.jsx     # Chat UI, conversation history, retry logic
│       │   ├── VoiceRecorder.jsx     # Web Speech API integration
│       │   ├── ResultsTable.jsx      # Sortable data table
│       │   └── Visualization.jsx     # Recharts: bar, line, grouped bar
│       └── styles/index.css          # White & blue theme
├── data/                             # CSV source files + generated DB
│   ├── athletes.csv
│   ├── sessions.csv
│   ├── gps_metrics.csv
│   ├── wellness.csv
│   ├── KPIs.csv
│   └── viz_dataset.csv
├── written/
│   ├── task5_system_design.md
│   └── task6_evaluation.md
├── Dockerfile                        # Multi-stage build (Node + Python)
├── railway.json                      # Railway deployment config
└── .env                              # ANTHROPIC_API_KEY (not committed)
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd athleteiq
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your_api_key_here
```

### 2. Backend

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Start the server
uvicorn backend.main:app --reload
```

On first start, the server will:
- Ingest CSVs into SQLite (`data/athleteiq.db`)
- Load the sentence-transformers embedding model (~90MB download, once)
- Build and embed 39 RAG knowledge base chunks

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Docker (optional)

```bash
docker build -t athleteiq .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your_key athleteiq
```

The container serves both the API and the frontend at [http://localhost:8000](http://localhost:8000).

## Deploying to Railway

1. Push to a GitHub repository
2. Go to [railway.app](https://railway.app) and create a new project from your repo
3. Add the environment variable `ANTHROPIC_API_KEY` in the Railway dashboard
4. Railway auto-detects the `Dockerfile` and deploys

The `railway.json` configures the health check endpoint and restart policy.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query` | Text query with optional conversation history |
| `POST` | `/api/voice` | Audio file transcription + query pipeline |
| `GET`  | `/api/health` | System status, loaded tables, RAG chunk count |
| `GET`  | `/api/schema` | Annotated database schema metadata |

### Example query

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Which athletes had the highest workload?"}'
```

## Data Model

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `athletes` | Athlete profiles | name, position, team |
| `sessions` | Training/match sessions | session_date, duration_minutes, session_type |
| `gps_metrics` | Per-session performance | total_distance, sprint_distance, high_intensity_efforts |
| `wellness` | Daily wellness scores | sleep_score, fatigue_score |
| `viz_dataset` | Pre-aggregated weekly view | total_distance, sprint_distance, fatigue |
