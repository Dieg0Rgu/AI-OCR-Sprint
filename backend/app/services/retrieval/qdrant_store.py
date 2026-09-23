import uuid
from typing import List, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.core.config import settings
from app.core.logging import logger
from app.schemas.documents import DocumentChunk


class QdrantVectorStore:
    """
    Production Qdrant client with automatic failover to embedded in-memory mode
    if the external Qdrant daemon is offline.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_name: Optional[str] = None,
    ):
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.client = self._init_client()

    def _init_client(self) -> QdrantClient:
        # First attempt remote Qdrant connection
        try:
            client = QdrantClient(
                host=self.host,
                port=self.port,
                timeout=5.0,
            )
            # Ping to confirm reachability
            client.get_collections()
            logger.info("Connected to remote Qdrant service", extra={"host": self.host, "port": self.port})
            return client
        except Exception as e:
            logger.warning(
                "Remote Qdrant unavailable. Falling back to embedded local Qdrant engine.",
                extra={"host": self.host, "port": self.port, "error": str(e)},
            )
            # In-memory Qdrant instance
            return QdrantClient(":memory:")

    def ensure_collection(self, dimension: int) -> None:
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=dimension,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
                logger.info(
                    "Created Qdrant collection",
                    extra={"collection": self.collection_name, "dimension": dimension},
                )
        except Exception as e:
            logger.error("Failed to verify/create Qdrant collection", extra={"error": str(e)})
            raise

    async def upsert_chunks(
        self, chunks: List[DocumentChunk], embeddings: List[List[float]]
    ) -> None:
        if not chunks or not embeddings:
            return

        dimension = len(embeddings[0])
        self.ensure_collection(dimension)

        points = []
        for chunk, emb in zip(chunks, embeddings):
            # Deterministic UUID based on chunk_id
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "page_number": chunk.page_number,
                "text": chunk.text,
                "bbox": chunk.bbox,
                "associated_image_ids": chunk.associated_image_ids,
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=emb,
                    payload=payload,
                )
            )

        # Batch upsert
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )
        logger.info(
            "Upserted chunks into Qdrant",
            extra={"collection": self.collection_name, "count": len(points)},
        )

    async def search(
        self,
        query_vector: List[float],
        document_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Tuple[DocumentChunk, float]]:
        filter_condition = None
        if document_id:
            filter_condition = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            )

        try:
            results = None
            if hasattr(self.client, "query_points"):
                try:
                    results = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=filter_condition,
                        limit=top_k,
                    ).points
                except Exception as qp_err:
                    logger.debug("query_points failed, attempting REST search fallback", extra={"error": str(qp_err)})
                    results = None

            if results is None:
                # Direct REST fallback to /points/search compatible with older Qdrant servers (< 1.10)
                import httpx
                body = {
                    "vector": query_vector,
                    "limit": top_k,
                    "with_payload": True,
                }
                if document_id:
                    body["filter"] = {
                        "must": [{"key": "document_id", "match": {"value": document_id}}]
                    }
                resp = httpx.post(
                    f"http://{self.host}:{self.port}/collections/{self.collection_name}/points/search",
                    json=body,
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()

                class MockPoint:
                    def __init__(self, p):
                        self.score = p.get("score", 0.0)
                        self.payload = p.get("payload", {})

                results = [MockPoint(p) for p in data.get("result", [])]

            matched_chunks: List[Tuple[DocumentChunk, float]] = []
            for r in results:
                payload = r.payload or {}
                chunk = DocumentChunk(
                    chunk_id=payload.get("chunk_id", ""),
                    document_id=payload.get("document_id", ""),
                    page_number=payload.get("page_number", 1),
                    text=payload.get("text", ""),
                    bbox=payload.get("bbox"),
                    associated_image_ids=payload.get("associated_image_ids", []),
                )
                score = float(r.score)
                matched_chunks.append((chunk, score))

            return matched_chunks
        except Exception as e:
            logger.error("Qdrant search error", extra={"error": str(e)})
            return []


# Global singleton
qdrant_store = QdrantVectorStore()
