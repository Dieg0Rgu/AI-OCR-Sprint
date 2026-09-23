import pytest
import io
from httpx import AsyncClient, ASGITransport
from main import app
from app.models.document_state import document_state_manager
from app.schemas.documents import DocumentStatus, DocumentChunk


@pytest.mark.asyncio
async def test_search_document_keywords():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register a mock document
        doc_id = "test-search-doc-123"
        await document_state_manager.register_document(
            document_id=doc_id,
            filename="sample_architecture.pdf",
            file_path="storage/sample.pdf",
            file_size_bytes=1024,
        )
        record = await document_state_manager.get_document(doc_id)
        record.status = DocumentStatus.READY
        record.page_count = 2
        record.chunks = [
            DocumentChunk(
                chunk_id="chunk_1",
                document_id=doc_id,
                page_number=1,
                text="Swiss Style (International Typographic Style) originated in Switzerland in the 1950s.",
                bbox=[50.0, 100.0, 400.0, 120.0],
            ),
            DocumentChunk(
                chunk_id="chunk_2",
                document_id=doc_id,
                page_number=2,
                text="The grid system is fundamental to Swiss graphic design. Precision and legibility are key.",
                bbox=[50.0, 200.0, 450.0, 230.0],
            ),
        ]

        # 1. Search insensitive
        res = await client.get(f"/api/v1/documents/{doc_id}/search?q=swiss")
        assert res.status_code == 200
        data = res.json()
        assert data["total_matches"] == 2
        assert data["matches"][0]["page_number"] == 1
        assert data["matches"][1]["page_number"] == 2
        assert "**Swiss**" in data["matches"][0]["snippet"]

        # 2. Search case-sensitive
        res_case = await client.get(f"/api/v1/documents/{doc_id}/search?q=swiss&case_sensitive=true")
        assert res_case.status_code == 200
        data_case = res_case.json()
        assert data_case["total_matches"] == 0

        # 3. Exact word match
        res_exact = await client.get(f"/api/v1/documents/{doc_id}/search?q=grid&exact=true")
        assert res_exact.status_code == 200
        data_exact = res_exact.json()
        assert data_exact["total_matches"] == 1
        assert data_exact["matches"][0]["page_number"] == 2


@pytest.mark.asyncio
async def test_stream_chat_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        doc_id = "test-stream-doc-456"
        await document_state_manager.register_document(
            document_id=doc_id,
            filename="test_manual.pdf",
            file_path="storage/manual.pdf",
            file_size_bytes=2048,
        )
        record = await document_state_manager.get_document(doc_id)
        record.status = DocumentStatus.READY
        record.page_count = 1
        record.chunks = [
            DocumentChunk(
                chunk_id="manual_c1",
                document_id=doc_id,
                page_number=1,
                text="El sistema garantiza una latencia de Time-To-First-Token inferior a 1.2 segundos mediante streaming.",
                bbox=[50.0, 50.0, 500.0, 80.0],
            )
        ]
        from app.services.retrieval.bm25_store import bm25_store
        bm25_store.index_document(doc_id, record.chunks)

        response = await client.post(
            "/api/v1/chat/stream",
            json={"document_id": doc_id, "query": "¿Cuál es la latencia del sistema?"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        text = response.text
        assert "event: citations" in text
        assert "event: token" in text or "event: done" in text
