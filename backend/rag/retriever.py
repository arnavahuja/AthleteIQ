"""
Main RAG retriever: embeds query, searches vector store, returns typed context.
"""

from backend.rag.embedder import embed_batch, embed_query
from backend.rag.store import VectorStore
from backend.rag.knowledge_base import build_all_chunks

# Module-level singleton
_store = VectorStore()
_initialized = False

# Default retrieval limits per chunk type
DEFAULT_TYPE_LIMITS = {
    "schema": 3,
    "kpi": 2,
    "example": 3,
    "rule": 2,
}


async def initialize_rag() -> None:
    """Build knowledge base and embed all chunks. Called once at startup."""
    global _initialized

    chunks = build_all_chunks()

    # Batch-embed all chunk contents (39 chunks -> ~2 API calls instead of 39)
    texts = [chunk["content"] for chunk in chunks]
    print(f"Embedding {len(chunks)} chunks in batches...")
    embeddings = embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")

    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding

    _store.add_chunks(chunks)
    _initialized = True
    print(f"RAG store initialized with {_store.chunk_count} chunks.")


def retrieve_context(
    query: str,
    intent: dict | None = None,
    type_limits: dict[str, int] | None = None,
) -> dict[str, list[dict]]:
    """
    Main retrieval function.

    1. Embed the user query
    2. Retrieve top-k per chunk type
    3. Return {schema: [...], kpi: [...], example: [...], rule: [...]}
    """
    if not _initialized:
        return {t: [] for t in DEFAULT_TYPE_LIMITS}

    limits = type_limits or DEFAULT_TYPE_LIMITS.copy()

    # Boost schema retrieval if intent mentions specific entities
    if intent and intent.get("entities"):
        entities = intent["entities"]
        if entities.get("athletes") or entities.get("teams") or entities.get("positions"):
            limits["schema"] = max(limits.get("schema", 3), 4)

    query_embedding = embed_query(query)
    results = _store.search_by_types(query_embedding, limits, threshold=0.1)
    return results


def get_chunk_count() -> int:
    """Return the total number of chunks in the store."""
    return _store.chunk_count
