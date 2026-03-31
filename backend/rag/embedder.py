"""
Local embedding using sentence-transformers. No API calls needed.
Model: all-MiniLM-L6-v2 (80MB, 384-dim, very fast on CPU).
"""

from sentence_transformers import SentenceTransformer

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("Loading local embedding model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("Embedding model loaded.")
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single text string."""
    model = _get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_query(text: str) -> list[float]:
    """Embed a query string. Same model, same function for local embeddings."""
    return embed_text(text)


def embed_batch(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed multiple texts in one shot. Runs locally, no rate limits."""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    return [e.tolist() for e in embeddings]
