import re
import asyncio

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from backend.data_pipeline.schema import SCHEMA, get_schema_summary
from backend.data_pipeline.db import get_connection
from backend.rag.retriever import retrieve_context, get_chunk_count
from backend.sql_generator.generator import generate_sql
from backend.query_executor.executor import execute_query
from backend.response.formatter import format_response
from backend.response.viz_recommender import recommend_viz
from backend.speech.transcribe import transcribe_audio, TranscriptionError

router = APIRouter(prefix="/api")

MAX_RETRIES = 2
RETRY_BASE_DELAY = 5  # seconds


class QueryRequest(BaseModel):
    query: str
    conversation_history: list[dict] | None = None


def _parse_rate_limit_error(e: Exception) -> dict | None:
    """Detect rate-limit (429) errors from Anthropic or other APIs."""
    msg = str(e)
    # Check for Anthropic RateLimitError or generic 429
    is_rate_limit = (
        "429" in msg
        or "rate" in msg.lower()
        or "quota" in msg.lower()
        or "RateLimitError" in type(e).__name__
    )
    if not is_rate_limit:
        return None
    match = re.search(r"retry.{0,10}?(\d+\.?\d*)\s*s", msg, re.IGNORECASE)
    retry_after = float(match.group(1)) if match else 30.0
    return {
        "error_type": "rate_limit",
        "retry_after": round(retry_after),
        "message": f"API rate limit reached. Please wait ~{round(retry_after)}s and try again.",
    }


def _friendly_error(e: Exception, step: str) -> str:
    """Convert raw exceptions into user-friendly error messages."""
    rate_info = _parse_rate_limit_error(e)
    if rate_info:
        return rate_info["message"]
    msg = str(e)
    if "not found" in msg.lower() and "model" in msg.lower():
        return f"{step}: The AI model is temporarily unavailable. Please try again shortly."
    if "permission" in msg.lower() or "api key" in msg.lower():
        return f"{step}: API authentication error. Please check the API key configuration."
    # Include the actual error for debugging
    return f"{step}: {type(e).__name__}: {msg}"


async def _call_with_retry(func, *args, step_name="Operation"):
    """Call an async function with retry logic for rate-limit errors."""
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await func(*args)
        except Exception as e:
            last_error = e
            rate_info = _parse_rate_limit_error(e)
            if rate_info and attempt < MAX_RETRIES:
                delay = min(rate_info["retry_after"], RETRY_BASE_DELAY * (attempt + 1))
                await asyncio.sleep(delay)
                continue
            raise
    raise last_error


async def _process_query(query: str, conversation_history: list[dict] | None = None) -> dict:
    """Full pipeline: RAG -> single LLM call (intent+SQL) -> execute -> format -> viz."""
    # Step 1: RAG retrieval (embedding call only, no generateContent)
    intent_stub = {"intent_type": "metric", "entities": {}, "visualization_hint": "table"}
    try:
        rag_context = retrieve_context(query, intent_stub)
    except Exception:
        rag_context = {"schema": [], "kpi": [], "example": [], "rule": []}

    # Step 2: Combined intent classification + SQL generation (SINGLE LLM call)
    try:
        sql_result = await _call_with_retry(generate_sql, query, intent_stub, rag_context, conversation_history, step_name="SQL generation")
    except Exception as e:
        return {
            "error": _friendly_error(e, "SQL generation"),
            "error_type": "rate_limit" if _parse_rate_limit_error(e) else "generation_error",
            "retry_after": (_parse_rate_limit_error(e) or {}).get("retry_after"),
            "retrieved_context": _summarize_context(rag_context),
        }

    # Build intent from the combined response
    intent = {
        "intent_type": sql_result.get("intent_type", "metric"),
        "entities": {},
        "visualization_hint": sql_result.get("visualization_hint", "table"),
    }

    if not sql_result["valid"]:
        return {
            "error": f"Generated SQL failed validation: {sql_result['error']}",
            "error_type": "validation_error",
            "sql": sql_result["sql"],
            "intent": intent,
            "retrieved_context": _summarize_context(rag_context),
        }

    # Step 3: Execute query — retry up to 2 times via Claude if SQL has runtime errors
    from backend.sql_generator.prompt_builder import build_prompt as _build_prompt, build_retry_prompt
    from backend.sql_generator.generator import _call_claude, _parse_response, MAX_SQL_RETRIES
    from backend.sql_generator.validator import validate_sql

    current_sql = sql_result["sql"]
    exec_result = execute_query(current_sql)
    original_prompt = _build_prompt(query, intent_stub, rag_context, conversation_history)

    for _exec_attempt in range(MAX_SQL_RETRIES):
        if not exec_result.get("error"):
            break
        try:
            retry_prompt = build_retry_prompt(
                original_prompt,
                current_sql,
                f"SQL execution error: {exec_result['error']}",
            )
            retry_text = _call_claude(retry_prompt)
            retry_parsed = _parse_response(retry_text)
            retry_sql = retry_parsed.get("sql", "").rstrip(";").strip()

            is_valid, val_err = validate_sql(retry_sql)
            if not is_valid:
                continue
            exec_result = execute_query(retry_sql)
            if not exec_result.get("error"):
                sql_result["sql"] = retry_sql
                current_sql = retry_sql
        except Exception:
            break  # Stop retrying on unexpected errors

    if exec_result.get("error"):
        return {
            "error": f"Query execution failed: {exec_result['error']}",
            "error_type": "execution_error",
            "sql": sql_result["sql"],
            "intent": intent,
            "retrieved_context": _summarize_context(rag_context),
        }

    # Step 4: Format response using Claude for a well-written summary
    summary = await format_response(query, exec_result, use_llm=True)

    # Step 5: Recommend visualization (deterministic)
    viz = recommend_viz(intent, exec_result["columns"], exec_result["row_count"])

    return {
        "summary": summary,
        "table": {
            "columns": exec_result["columns"],
            "rows": exec_result["rows"],
        },
        "visualization": viz,
        "sql": sql_result["sql"],
        "intent": intent,
        "retrieved_context": _summarize_context(rag_context),
    }


@router.post("/query")
async def query_endpoint(request: QueryRequest):
    """Process a text query through the full RAG pipeline."""
    return await _process_query(request.query, request.conversation_history)


@router.post("/voice")
async def voice_endpoint(audio: UploadFile = File(...)):
    """Process a voice query: transcribe then run through the full pipeline."""
    try:
        audio_bytes = await audio.read()
        mime_type = audio.content_type or "audio/webm"
        transcription = await _call_with_retry(
            transcribe_audio, audio_bytes, mime_type, step_name="Transcription"
        )
    except TranscriptionError as e:
        return {"error": f"Transcription failed: {str(e)}", "error_type": "transcription_error"}
    except Exception as e:
        return {"error": _friendly_error(e, "Transcription"), "error_type": "rate_limit" if _parse_rate_limit_error(e) else "transcription_error"}

    result = await _process_query(transcription)
    result["transcription"] = transcription
    return result


@router.get("/health")
async def health():
    """Check system status."""
    from backend.config import settings as _settings

    try:
        conn = get_connection(read_only=True)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        return {"status": "error", "error": str(e)}

    # Show whether key is configured (masked for security)
    key = _settings.anthropic_api_key
    key_status = f"set ({key[:8]}...{key[-4:]})" if len(key) > 12 else ("empty" if not key else "too_short")

    return {
        "status": "ok",
        "tables": tables,
        "chunk_count": get_chunk_count(),
        "api_key_status": key_status,
        "model": _settings.claude_model,
        "db_path": _settings.db_path,
    }


@router.get("/schema")
async def schema_info():
    """Return annotated schema metadata."""
    return {
        "summary": get_schema_summary(),
        "tables": {
            name: {
                "columns": info["columns"],
                "relationships": info.get("relationships", []),
                "use_when": info.get("use_when", ""),
            }
            for name, info in SCHEMA.items()
        },
    }


def _summarize_context(rag_context: dict) -> dict:
    """Create a lightweight summary of retrieved context for the response."""
    return {
        "kpis": [{"name": c["name"], "score": c.get("score", 0)} for c in rag_context.get("kpi", [])],
        "examples_used": [c["name"] for c in rag_context.get("example", [])],
        "rules_applied": [c["name"] for c in rag_context.get("rule", [])],
        "schema_tables": [c["name"] for c in rag_context.get("schema", [])],
    }
