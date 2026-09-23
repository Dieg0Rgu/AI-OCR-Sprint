import pytest
from app.schemas.documents import DocumentChunk
from app.services.retrieval.bm25_store import bm25_store
from app.services.retrieval.hybrid_search import hybrid_retriever
from app.services.retrieval.qdrant_store import qdrant_store
from app.services.providers.local_provider import FastEmbedEmbeddingProvider


@pytest.mark.asyncio
async def test_bm25_and_qdrant_and_rrf_flow():
    doc_id = "test_doc_rag"
    chunks = [
        DocumentChunk(
            chunk_id=f"{doc_id}_p1_c0",
            document_id=doc_id,
            page_number=1,
            text="La arquitectura RAG multimodal utiliza Qdrant para almacenar embeddings densos.",
        ),
        DocumentChunk(
            chunk_id=f"{doc_id}_p2_c0",
            document_id=doc_id,
            page_number=2,
            text="El modelo Moondream procesa las imágenes y diagramas para responder preguntas visuales.",
        ),
        DocumentChunk(
            chunk_id=f"{doc_id}_p3_c0",
            document_id=doc_id,
            page_number=3,
            text="El algoritmo BM25 realiza una búsqueda léxica basada en frecuencia de términos.",
        ),
    ]

    # 1. Index BM25
    bm25_store.index_document(doc_id, chunks)
    bm25_results = bm25_store.search("búsqueda léxica términos", document_id=doc_id, top_k=2)
    assert len(bm25_results) > 0
    assert bm25_results[0][0].page_number == 3

    # 2. Index Qdrant
    embed_provider = FastEmbedEmbeddingProvider()
    texts = [c.text for c in chunks]
    embeddings = await embed_provider.embed_texts(texts)
    await qdrant_store.upsert_chunks(chunks, embeddings)

    # 3. Hybrid search with RRF
    query = "embeddings densos en vector database"
    fused, duration = await hybrid_retriever.search(query, document_id=doc_id, top_k=2)
    assert len(fused) > 0
    assert duration > 0.0
    # The first chunk explicitly discusses dense embeddings
    assert fused[0].chunk.page_number == 1
    assert fused[0].rrf_score > 0.0
