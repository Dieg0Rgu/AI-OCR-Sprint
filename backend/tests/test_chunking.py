import pytest
from app.schemas.documents import ExtractedImageMetadata
from app.services.ingestion.chunker import DocumentChunker
from app.services.ingestion.extractor import PageExtractionResult


def test_chunker_preserves_page_number_and_images():
    chunker = DocumentChunker(target_chunk_size=200, chunk_overlap=30)

    # Mock page results with blocks and images
    img1 = ExtractedImageMetadata(
        image_id="img_p1_0",
        document_id="doc1",
        page_number=1,
        bbox=[10.0, 20.0, 100.0, 150.0],
        width=200,
        height=300,
        file_path="/tmp/img.png",
        url="/api/v1/documents/doc1/images/img_p1_0",
    )

    page1 = PageExtractionResult(
        page_number=1,
        text="Este es un párrafo de prueba inicial sobre arquitectura de software.",
        blocks=[
            {
                "bbox": [10.0, 10.0, 200.0, 50.0],
                "text": "Este es un párrafo de prueba inicial sobre arquitectura de software.",
                "block_no": 0,
            },
            {
                "bbox": [10.0, 60.0, 200.0, 120.0],
                "text": "El segundo bloque describe el subsistema de ingestión asíncrono y bases vectoriales.",
                "block_no": 1,
            },
        ],
        images=[img1],
    )

    page2 = PageExtractionResult(
        page_number=2,
        text="Contenido de la página dos relativo a métricas y observabilidad.",
        blocks=[
            {
                "bbox": [15.0, 15.0, 180.0, 80.0],
                "text": "Contenido de la página dos relativo a métricas y observabilidad.",
                "block_no": 0,
            }
        ],
        images=[],
    )

    chunks = chunker.chunk_document("doc1", [page1, page2])

    assert len(chunks) >= 2
    # Verify page 1 chunks have associated_image_ids
    p1_chunks = [c for c in chunks if c.page_number == 1]
    assert len(p1_chunks) > 0
    assert "img_p1_0" in p1_chunks[0].associated_image_ids
    assert p1_chunks[0].bbox is not None

    # Verify page 2 chunks have page_number 2 and no images
    p2_chunks = [c for c in chunks if c.page_number == 2]
    assert len(p2_chunks) > 0
    assert p2_chunks[0].page_number == 2
    assert len(p2_chunks[0].associated_image_ids) == 0
