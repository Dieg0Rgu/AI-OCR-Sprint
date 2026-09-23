import hashlib
import time
from typing import Any, Dict, Optional, Tuple


class RetrievalCache:
    """
    Thread-safe in-memory LRU/TTL cache for retrieval results and embeddings.
    Prevents repeated expensive Qdrant / BM25 / FastEmbed computations for identical queries.
    """

    def __init__(self, max_size: int = 256, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[float, Any]] = {}

    def _make_key(self, doc_id: str, query: str, top_k: int) -> str:
        normalized = f"{doc_id}:{query.strip().lower()}:{top_k}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, doc_id: str, query: str, top_k: int) -> Optional[Any]:
        key = self._make_key(doc_id, query, top_k)
        if key in self._cache:
            created_at, val = self._cache[key]
            if time.time() - created_at < self.ttl_seconds:
                return val
            del self._cache[key]
        return None

    def set(self, doc_id: str, query: str, top_k: int, value: Any) -> None:
        if len(self._cache) >= self.max_size:
            # Evict oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
        key = self._make_key(doc_id, query, top_k)
        self._cache[key] = (time.time(), value)

    def clear(self) -> None:
        self._cache.clear()


retrieval_cache = RetrievalCache()
