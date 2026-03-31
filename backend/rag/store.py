import warnings
import numpy as np


class VectorStore:
    """In-memory vector store with cosine similarity search."""

    def __init__(self):
        self.chunks: list[dict] = []
        self._embeddings: np.ndarray | None = None

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """Safely normalize vectors, replacing any bad values."""
        vectors = np.nan_to_num(vectors, nan=0.0, posinf=0.0, neginf=0.0)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        return vectors / norms

    def add_chunks(self, chunks: list[dict]) -> None:
        """Add chunks with pre-computed embeddings."""
        self.chunks.extend(chunks)
        vectors = np.array([c["embedding"] for c in self.chunks], dtype=np.float64)
        self._embeddings = self._normalize(vectors)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        type_filter: str | None = None,
        threshold: float = 0.0,
    ) -> list[dict]:
        """Search for most similar chunks."""
        if self._embeddings is None or len(self.chunks) == 0:
            return []

        query_vec = np.nan_to_num(
            np.array(query_embedding, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0
        )
        norm = np.linalg.norm(query_vec)
        if norm > 1e-10:
            query_vec = query_vec / norm
        else:
            return []

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            scores = self._embeddings @ query_vec
            scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

        if type_filter:
            mask = np.array([c["type"] == type_filter for c in self.chunks])
            scores = scores * mask

        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < threshold:
                break
            chunk = {**self.chunks[idx], "score": score}
            chunk.pop("embedding", None)
            results.append(chunk)

        return results

    def search_by_types(
        self,
        query_embedding: list[float],
        type_limits: dict[str, int],
        threshold: float = 0.1,
    ) -> dict[str, list[dict]]:
        """Retrieve top-k per chunk type."""
        results = {}
        for chunk_type, limit in type_limits.items():
            results[chunk_type] = self.search(
                query_embedding,
                top_k=limit,
                type_filter=chunk_type,
                threshold=threshold,
            )
        return results

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)
