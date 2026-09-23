import asyncio
import time
from typing import Dict, List, Optional, Tuple
from app.core.logging import logger
from app.schemas.documents import DocumentChunk
from app.services.providers.factory import ProviderFactory
from app.services.retrieval.bm25_store import bm25_store
from app.services.retrieval.qdrant_store import qdrant_store


class HybridSearchResult:
    def __init__(
        self,
        chunk: DocumentChunk,
        rrf_score: float,
        dense_rank: Optional[int],
        dense_score: Optional[float],
        bm25_rank: Optional[int],
        bm25_score: Optional[float],
    ):
        self.chunk = chunk
        self.rrf_score = rrf_score
        self.dense_rank = dense_rank
        self.dense_score = dense_score
        self.bm25_rank = bm25_rank
        self.bm25_score = bm25_score


class HybridRetriever:
    """
    Hybrid retriever combining Dense Vector Search (Qdrant) and
    Sparse Lexical Search (BM25) using Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    async def search(
        self,
        query: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
        candidate_multiplier: int = 3,
    ) -> Tuple[List[HybridSearchResult], float]:
        """
        Executes parallel dense and sparse retrieval, fuses rankings via RRF,
        and returns deduplicated top_k candidates with retrieval latency.
        """
        start_time = time.perf_counter()
        candidates_to_fetch = max(top_k * candidate_multiplier, 15)

        # 1. Fetch dense candidates (embedding + Qdrant)
        async def fetch_dense() -> List[Tuple[DocumentChunk, float]]:
            try:
                embed_provider = ProviderFactory.get_embedding_provider()
                query_vector = await embed_provider.embed_query(query)
                return await qdrant_store.search(
                    query_vector=query_vector,
                    document_id=document_id,
                    top_k=candidates_to_fetch,
                )
            except Exception as e:
                logger.error("Dense retrieval error in hybrid search", extra={"error": str(e)})
                return []

        # 2. Fetch BM25 candidates
        def fetch_bm25() -> List[Tuple[DocumentChunk, float]]:
            try:
                return bm25_store.search(
                    query=query,
                    document_id=document_id,
                    top_k=candidates_to_fetch,
                )
            except Exception as e:
                logger.error("BM25 retrieval error in hybrid search", extra={"error": str(e)})
                return []

        # Execute parallel retrieval
        dense_results, bm25_results = await asyncio.gather(
            fetch_dense(),
            asyncio.to_thread(fetch_bm25),
        )

        # 3. Reciprocal Rank Fusion
        fused_items: Dict[str, Dict] = {}

        # Process dense results
        for rank, (chunk, score) in enumerate(dense_results, start=1):
            cid = chunk.chunk_id
            if cid not in fused_items:
                fused_items[cid] = {
                    "chunk": chunk,
                    "dense_rank": rank,
                    "dense_score": score,
                    "bm25_rank": None,
                    "bm25_score": None,
                }
            else:
                fused_items[cid]["dense_rank"] = rank
                fused_items[cid]["dense_score"] = score

        # Process BM25 results
        for rank, (chunk, score) in enumerate(bm25_results, start=1):
            cid = chunk.chunk_id
            if cid not in fused_items:
                fused_items[cid] = {
                    "chunk": chunk,
                    "dense_rank": None,
                    "dense_score": None,
                    "bm25_rank": rank,
                    "bm25_score": score,
                }
            else:
                fused_items[cid]["bm25_rank"] = rank
                fused_items[cid]["bm25_score"] = score

        # Compute RRF score
        # RRF_score(d) = sum(1 / (k + rank))
        results: List[HybridSearchResult] = []
        for cid, data in fused_items.items():
            rrf_score = 0.0
            if data["dense_rank"] is not None:
                rrf_score += 1.0 / (self.rrf_k + data["dense_rank"])
            if data["bm25_rank"] is not None:
                rrf_score += 1.0 / (self.rrf_k + data["bm25_rank"])

            results.append(
                HybridSearchResult(
                    chunk=data["chunk"],
                    rrf_score=round(rrf_score, 6),
                    dense_rank=data["dense_rank"],
                    dense_score=data["dense_score"],
                    bm25_rank=data["bm25_rank"],
                    bm25_score=data["bm25_score"],
                )
            )

        # Sort descending by RRF score
        results.sort(key=lambda x: x.rrf_score, reverse=True)
        final_results = results[:top_k]

        duration = time.perf_counter() - start_time
        logger.info(
            "Hybrid search completed",
            extra={
                "query": query,
                "document_id": document_id,
                "dense_count": len(dense_results),
                "bm25_count": len(bm25_results),
                "fused_count": len(final_results),
                "duration_s": round(duration, 4),
            },
        )

        return final_results, duration


hybrid_retriever = HybridRetriever()
