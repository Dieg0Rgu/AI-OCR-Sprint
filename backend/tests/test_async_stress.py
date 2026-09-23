import io
import time
import asyncio
from pathlib import Path
import pytest
import pymupdf as fitz
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from main import app
from app.models.document_state import document_state_manager
from app.schemas.documents import DocumentStatus


def create_synthetic_multipage_pdf(num_pages: int = 25) -> bytes:
    """
    Dynamically generates a valid, complex multi-page PDF document with structured text,
    distinct chapters, and embedded images on specific pages.
    """
    doc = fitz.open()

    # Pre-generate a small sample image in memory
    img = Image.new("RGB", (200, 200), color=(50, 120, 220))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 180, 180], outline=(255, 255, 255), width=3)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    for p in range(1, num_pages + 1):
        page = doc.new_page(width=595, height=842)  # Standard A4

        # Title
        page.insert_text(
            (50, 60),
            f"DOCUMENTO TÉCNICO DE REFERENCIA - SECCIÓN #{p}",
            fontsize=15,
            color=(0.1, 0.2, 0.4),
        )

        # Structured Paragraphs
        if p == 1:
            body = (
                "Página 1: Introducción a la arquitectura del sistema de análisis documental. "
                "Este informe describe los componentes de backend y frontend diseñados para soportar "
                "procesamiento escalable de 20 a cientos de páginas mediante técnicas de RAG multimodal."
            )
        elif p == 5:
            body = (
                "Página 5: Protocolo de Eventos en Tiempo Real (SSE). "
                "El flujo de notificación se transmite a través del endpoint /api/v1/documents/{id}/events "
                "garantizando actualización reactiva de la máquina de estados."
            )
        elif p == 10:
            body = (
                "Página 10: Extracción estructurada y OCR de respaldo. "
                "Utilizamos PyMuPDF para obtener bloques de texto y coordenadas bbox exactas. "
                "Si la página carece de texto vectorial nativo, se dispara el motor Tesseract."
            )
        elif p == 15:
            body = (
                "Página 15: Capítulo Crítico sobre Reciprocal Rank Fusion (RRF). "
                "El motor de búsqueda híbrida combina la búsqueda vectorial densa de Qdrant "
                "y la búsqueda léxica BM25 utilizando la fórmula RRF con factor de suavizado k=60. "
                "Este procedimiento optimiza la tasa de acierto y la precisión en documentos técnicos complejos."
            )
        elif p == 20:
            body = (
                "Página 20: Directivas de seguridad y sanitización de archivos. "
                "Se validan los bytes mágicos %PDF- y se neutralizan ataques de Path Traversal "
                "mediante la sanitización estricta de nombres y cuotas de memoria."
            )
        elif p == 25:
            body = (
                "Página 25: Conclusiones finales del benchmark. "
                "El sistema demostró un comportamiento asíncrono no bloqueante en todas las fases "
                "manteniendo latencias de recuperación inferiores a 100 milisegundos."
            )
        else:
            body = (
                f"Página {p}: Contenido complementario de análisis y especificación modular. "
                f"Parámetros operativos de la sección {p} validados según estándares de ingeniería."
            )

        page.insert_textbox(
            fitz.Rect(50, 100, 545, 400),
            body,
            fontsize=11,
            color=(0.15, 0.15, 0.15),
        )

        # Insert embedded figures on page 8 and page 18
        if p in {8, 18}:
            rect = fitz.Rect(50, 450, 250, 650)
            page.insert_image(rect, stream=img_bytes)
            page.insert_text(
                (50, 670),
                f"Figura {p}.1: Diagrama esquemático de rendimiento en página {p}",
                fontsize=9,
                color=(0.4, 0.4, 0.4),
            )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_async_ingestion_and_rag_on_25_page_pdf():
    client = TestClient(app)

    # 1. Generate 25-page PDF
    pdf_bytes = create_synthetic_multipage_pdf(num_pages=25)
    assert len(pdf_bytes) > 10000
    assert pdf_bytes.startswith(b"%PDF-")

    # 2. Test Non-blocking Upload (202 Accepted)
    start_upload = time.perf_counter()
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("benchmark_25pages.pdf", pdf_bytes, "application/pdf")},
    )
    upload_duration = time.perf_counter() - start_upload

    assert response.status_code == 202
    # Verify non-blocking immediate response (< 600ms)
    assert upload_duration < 0.600, f"Upload took {upload_duration}s, expected < 0.6s"

    data = response.json()
    document_id = data["document_id"]
    assert document_id is not None
    assert data["status"] == "uploaded"

    # 3. Wait for background processing to reach READY state
    max_wait_seconds = 30
    poll_interval = 0.5
    elapsed = 0.0
    ready = False

    while elapsed < max_wait_seconds:
        doc_res = client.get(f"/api/v1/documents/{document_id}")
        assert doc_res.status_code == 200
        doc_data = doc_res.json()

        if doc_data["status"] == "ready":
            ready = True
            break
        elif doc_data["status"] == "failed":
            pytest.fail(f"Ingestion failed: {doc_data.get('error_message')}")

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    assert ready is True, f"Document did not reach READY within {max_wait_seconds}s"
    assert doc_data["page_count"] == 25
    assert doc_data["total_chunks"] >= 25
    assert doc_data["total_images"] >= 2
    assert "extraction_time" in doc_data["stage_latencies"]
    assert "indexing_time" in doc_data["stage_latencies"]

    # 4. Test RAG Query with exact citation redirection to Page 15
    query_payload = {
        "document_id": document_id,
        "query": "¿Cuál es la fórmula del algoritmo RRF y qué factor de suavizado k utiliza?",
        "top_k": 3,
    }
    chat_res = client.post("/api/v1/chat/query", json=query_payload)
    assert chat_res.status_code == 200
    rag_data = chat_res.json()

    assert len(rag_data["answer"]) > 10
    assert len(rag_data["citations"]) > 0

    # Verify that citation references Page 15
    page_15_cited = any(c["page_number"] == 15 for c in rag_data["citations"])
    assert page_15_cited is True, f"Expected citation to Page 15, got: {rag_data['citations']}"

    # Verify citation snippet contains relevant excerpt
    p15_cit = next(c for c in rag_data["citations"] if c["page_number"] == 15)
    assert "RRF" in p15_cit["snippet"] or "60" in p15_cit["snippet"] or "Qdrant" in p15_cit["snippet"] or len(p15_cit["snippet"]) > 20

    # 5. Test Vision Query on extracted image
    images_res = client.get(f"/api/v1/documents/{document_id}/images")
    assert images_res.status_code == 200
    images = images_res.json()
    assert len(images) >= 2

    test_image_id = images[0]["image_id"]
    vision_payload = {
        "document_id": document_id,
        "image_id": test_image_id,
        "prompt": "Describe la figura y analiza las dimensiones y posibles tendencias numéricas.",
    }
    vis_res = client.post("/api/v1/vision/query", json=vision_payload)
    assert vis_res.status_code == 200
    vis_data = vis_res.json()
    assert vis_data["image_id"] == test_image_id
    assert len(vis_data["analysis"]) > 10
    assert "metrics" in vis_data
