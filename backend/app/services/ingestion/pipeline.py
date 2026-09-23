import asyncio
import time
from pathlib import Path
from app.core.logging import logger
from app.core.security import safe_cleanup_path
from app.models.document_state import document_state_manager
from app.schemas.documents import DocumentStatus
from app.schemas.events import SSEEventPayload
from app.services.ingestion.broadcaster import event_broadcaster
from app.services.ingestion.chunker import DocumentChunker
from app.services.ingestion.extractor import PDFExtractor
from app.services.providers.factory import ProviderFactory
from app.services.retrieval.bm25_store import bm25_store
from app.services.retrieval.qdrant_store import qdrant_store


class IngestionPipeline:
    """
    Asynchronous document ingestion orchestrator.
    Drives the document state machine and broadcasts real-time SSE progress events.
    """

    def __init__(self):
        self.chunker = DocumentChunker(target_chunk_size=700, chunk_overlap=120)

    async def process_document(self, document_id: str, file_path: Path) -> None:
        total_start = time.perf_counter()
        logger.info("Starting ingestion pipeline", extra={"document_id": document_id, "file": str(file_path)})

        try:
            # 1. State: UPLOADED
            await document_state_manager.update_status(document_id, DocumentStatus.UPLOADED)
            await event_broadcaster.publish(
                SSEEventPayload(
                    document_id=document_id,
                    status=DocumentStatus.UPLOADED,
                    progress_percent=10.0,
                    message="Documento recibido y validado con éxito.",
                )
            )

            # 2. State: EXTRACTING
            await document_state_manager.update_status(document_id, DocumentStatus.EXTRACTING)
            await event_broadcaster.publish(
                SSEEventPayload(
                    document_id=document_id,
                    status=DocumentStatus.EXTRACTING,
                    progress_percent=30.0,
                    message="Extrayendo texto estructurado e imágenes embebidas...",
                )
            )

            extractor = PDFExtractor(doc_id=document_id, file_path=file_path)
            # Run blocking PDF I/O in thread pool to avoid blocking asyncio event loop
            page_results, all_images, extract_latencies = await asyncio.to_thread(extractor.extract_document)

            doc_record = await document_state_manager.get_document(document_id)
            if doc_record:
                doc_record.page_count = len(page_results)
                doc_record.images = all_images
                for stage, dur in extract_latencies.items():
                    doc_record.record_stage_latency(stage, dur)

            # 3. State: OCR_PROCESSING
            await document_state_manager.update_status(document_id, DocumentStatus.OCR_PROCESSING)
            ocr_used_pages = sum(1 for p in page_results if p.used_ocr)
            ocr_msg = (
                f"OCR de respaldo aplicado en {ocr_used_pages} página(s) escaneada(s)."
                if ocr_used_pages > 0
                else "Páginas nativas verificadas con texto vectorial (no requirió OCR)."
            )
            await event_broadcaster.publish(
                SSEEventPayload(
                    document_id=document_id,
                    status=DocumentStatus.OCR_PROCESSING,
                    progress_percent=55.0,
                    message=ocr_msg,
                    stage_latencies=extract_latencies,
                )
            )

            # 4. State: CHUNKING
            await document_state_manager.update_status(document_id, DocumentStatus.CHUNKING)
            await event_broadcaster.publish(
                SSEEventPayload(
                    document_id=document_id,
                    status=DocumentStatus.CHUNKING,
                    progress_percent=70.0,
                    message="Segmentando semánticamente y asociando figuras...",
                )
            )

            chunking_start = time.perf_counter()
            chunks = self.chunker.chunk_document(document_id, page_results)
            chunking_dur = time.perf_counter() - chunking_start
            await document_state_manager.update_chunks(document_id, chunks)
            await document_state_manager.record_latency(document_id, "chunking_time", chunking_dur)

            # 5. State: INDEXING
            await document_state_manager.update_status(document_id, DocumentStatus.INDEXING)
            await event_broadcaster.publish(
                SSEEventPayload(
                    document_id=document_id,
                    status=DocumentStatus.INDEXING,
                    progress_percent=85.0,
                    message=f"Indexando {len(chunks)} fragmentos en base vectorial y léxica...",
                )
            )

            indexing_start = time.perf_counter()
            embed_provider = ProviderFactory.get_embedding_provider()
            chunk_texts = [c.text for c in chunks]

            embed_start = time.perf_counter()
            embeddings = await embed_provider.embed_texts(chunk_texts)
            embed_dur = time.perf_counter() - embed_start
            await document_state_manager.record_latency(document_id, "embedding_time", embed_dur)

            # Upsert into Qdrant
            await qdrant_store.upsert_chunks(chunks, embeddings)

            # Index into BM25
            bm25_store.index_document(document_id, chunks)

            indexing_dur = time.perf_counter() - indexing_start
            await document_state_manager.record_latency(document_id, "indexing_time", indexing_dur)

            # 6. State: READY
            total_duration = time.perf_counter() - total_start
            await document_state_manager.record_latency(document_id, "total_ingestion_time", total_duration)
            await document_state_manager.update_status(document_id, DocumentStatus.READY)

            latest_doc = await document_state_manager.get_document(document_id)
            latencies = latest_doc.stage_latencies if latest_doc else {}

            ready_msg = (
                f"Procesamiento finalizado exitosamente. "
                f"{len(page_results)} páginas, {len(chunks)} chunks, {len(all_images)} figuras indexadas."
            )
            await event_broadcaster.publish(
                SSEEventPayload(
                    document_id=document_id,
                    status=DocumentStatus.READY,
                    progress_percent=100.0,
                    message=ready_msg,
                    stage_latencies=latencies,
                )
            )

            logger.info("Document ingestion completed successfully", extra={"document_id": document_id, "total_seconds": round(total_duration, 3)})

        except Exception as e:
            error_str = f"Error en pipeline de ingestión: {str(e)}"
            logger.error("Ingestion failed", extra={"document_id": document_id, "error": str(e)}, exc_info=True)
            await document_state_manager.update_status(document_id, DocumentStatus.FAILED, error=error_str)
            await event_broadcaster.publish(
                SSEEventPayload(
                    document_id=document_id,
                    status=DocumentStatus.FAILED,
                    progress_percent=100.0,
                    message="Fallo durante la ingestión del documento.",
                    error=error_str,
                )
            )


ingestion_pipeline = IngestionPipeline()
