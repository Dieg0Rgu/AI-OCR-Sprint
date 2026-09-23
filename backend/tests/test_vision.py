import pytest
from pathlib import Path
from app.services.retrieval.vision_engine import vision_engine


def test_detect_numerical_estimation_triggers_warning():
    # Case with numbers and percentages (typical in chart interpretations)
    text_with_stats = (
        "El gráfico de barras muestra un crecimiento del 24.5% en el año 2023, "
        "alcanzando un total aproximado de 1500 unidades vendidas."
    )
    has_num, warning = vision_engine._detect_numerical_estimation(text_with_stats)
    assert has_num is True
    assert warning is not None
    assert "estimaciones aproximadas" in warning

    # Case purely descriptive without numbers
    text_purely_descriptive = (
        "La figura ilustra el diagrama conceptual del pipeline de datos "
        "con flechas conectando los componentes sin cifras específicas."
    )
    has_num_desc, warning_desc = vision_engine._detect_numerical_estimation(text_purely_descriptive)
    assert has_num_desc is False
    assert warning_desc is None


def test_image_proximity_context_extraction():
    from pathlib import Path
    from app.services.ingestion.extractor import PDFExtractor

    extractor = PDFExtractor(doc_id="test_doc", file_path=Path("/tmp/fake.pdf"))

    text_blocks = [
        {
            "bbox": [50.0, 40.0, 400.0, 60.0],
            "text": "SECCIÓN 3: RENDIMIENTO Y ARQUITECTURA",
            "block_no": 0,
        },
        {
            "bbox": [50.0, 80.0, 500.0, 150.0],
            "text": "Los parámetros operativos demuestran una alta eficiencia en la ingestión concurrente.",
            "block_no": 1,
        },
        {
            "bbox": [50.0, 420.0, 380.0, 440.0],
            "text": "Figura 3.1: Diagrama de flujo de inferencia multimodal y tiempos de latencia",
            "block_no": 2,
        },
        {
            "bbox": [50.0, 460.0, 500.0, 520.0],
            "text": "El bloque posterior describe las optimizaciones aplicadas al modelo de lenguaje.",
            "block_no": 3,
        },
    ]

    # Image placed between Y=200 and Y=400
    img_bbox = [50.0, 200.0, 350.0, 400.0]

    caption, section_title, surrounding = extractor._extract_image_context(
        bbox=img_bbox,
        text_blocks=text_blocks,
        page_number=3,
    )

    assert caption is not None
    assert "Figura 3.1" in caption
    assert section_title is not None
    assert "SECCIÓN 3" in section_title
    assert "eficiencia en la ingestión" in surrounding
    assert "optimizaciones aplicadas" in surrounding


@pytest.mark.asyncio
async def test_vision_engine_injects_surrounding_context():
    from unittest.mock import AsyncMock, patch
    from app.models.document_state import document_state_manager
    from app.schemas.documents import ExtractedImageMetadata, DocumentDetailResponse, DocumentStatus

    # Create dummy image metadata with surrounding context
    meta = ExtractedImageMetadata(
        image_id="img_test_1",
        document_id="doc_ctx_1",
        page_number=4,
        bbox=[10.0, 20.0, 200.0, 150.0],
        width=300,
        height=200,
        file_path="/tmp/test_img.png",
        url="/api/v1/documents/doc_ctx_1/images/img_test_1",
        order=1,
        caption="Figura 4.2: Curva de precisión-recuperación",
        section_title="Sección 4: Evaluación Experimental",
        surrounding_text="Sección: Evaluación Experimental // Pie de figura: Curva PR // Párrafo anterior: Métricas RRF.",
    )

    from app.models.document_state import DocumentRecord
    doc_state = DocumentRecord(
        document_id="doc_ctx_1",
        filename="evaluacion.pdf",
        file_path=Path("/tmp/evaluacion.pdf"),
        file_size_bytes=1024,
    )
    doc_state.status = DocumentStatus.READY
    doc_state.page_count = 5
    doc_state.images = [meta]

    captured_prompt = None

    class MockProvider:
        async def analyze_image(self, image_path, prompt):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "Análisis de la curva de precisión con 95% de confianza."

    with patch.object(document_state_manager, "get_document", AsyncMock(return_value=doc_state)), \
         patch("app.services.providers.factory.ProviderFactory.get_vision_provider", return_value=MockProvider()), \
         patch("pathlib.Path.exists", return_value=True):

        res = await vision_engine.analyze_figure(
            document_id="doc_ctx_1",
            image_id="img_test_1",
            prompt="¿Qué representa la curva?",
        )

        assert captured_prompt is not None
        assert "Contexto textual de la página 4 adyacente a la figura:" in captured_prompt
        assert "Sección: Evaluación Experimental" in captured_prompt
        assert "¿Qué representa la curva?" in captured_prompt
        assert res.has_numerical_estimates is True
        assert res.estimation_warning is not None

