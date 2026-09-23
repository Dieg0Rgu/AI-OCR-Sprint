import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.schemas.documents import (
    DocumentStatus,
    DocumentChunk,
    ExtractedImageMetadata,
    DocumentDetailResponse,
)


class DocumentRecord:
    def __init__(
        self,
        document_id: str,
        filename: str,
        file_path: Path,
        file_size_bytes: int,
    ):
        self.document_id = document_id
        self.filename = filename
        self.file_path = file_path
        self.file_size_bytes = file_size_bytes
        self.status = DocumentStatus.UPLOADED
        self.page_count: int = 0
        self.chunks: List[DocumentChunk] = []
        self.images: List[ExtractedImageMetadata] = []
        self.stage_latencies: Dict[str, float] = {}
        self.error_message: Optional[str] = None
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = self.created_at

    def update_status(self, status: DocumentStatus, error: Optional[str] = None) -> None:
        self.status = status
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if error:
            self.error_message = error

    def record_stage_latency(self, stage: str, duration_seconds: float) -> None:
        self.stage_latencies[stage] = round(duration_seconds, 4)

    def to_detail_response(self) -> DocumentDetailResponse:
        return DocumentDetailResponse(
            document_id=self.document_id,
            filename=self.filename,
            file_size_bytes=self.file_size_bytes,
            status=self.status,
            page_count=self.page_count,
            total_chunks=len(self.chunks),
            total_images=len(self.images),
            stage_latencies=self.stage_latencies,
            error_message=self.error_message,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class DocumentStateManager:
    """
    Thread-safe registry for document metadata and ingestion states.
    Can persist state metadata to disk under storage/documents/{doc_id}/meta.json.
    """

    def __init__(self):
        self._documents: Dict[str, DocumentRecord] = {}
        self._lock = asyncio.Lock()

    async def register_document(
        self,
        document_id: str,
        filename: str,
        file_path: Path,
        file_size_bytes: int,
    ) -> DocumentRecord:
        async with self._lock:
            doc = DocumentRecord(
                document_id=document_id,
                filename=filename,
                file_path=file_path,
                file_size_bytes=file_size_bytes,
            )
            self._documents[document_id] = doc
            self._persist_to_disk(doc)
            return doc

    async def get_document(self, document_id: str) -> Optional[DocumentRecord]:
        async with self._lock:
            if document_id in self._documents:
                return self._documents[document_id]
            # Attempt to restore from disk if backend restarted
            return self._load_from_disk(document_id)

    async def list_documents(self) -> List[DocumentDetailResponse]:
        async with self._lock:
            return [doc.to_detail_response() for doc in self._documents.values()]

    async def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        error: Optional[str] = None,
    ) -> Optional[DocumentRecord]:
        async with self._lock:
            doc = self._documents.get(document_id)
            if doc:
                doc.update_status(status, error)
                self._persist_to_disk(doc)
            return doc

    async def update_chunks(
        self, document_id: str, chunks: List[DocumentChunk]
    ) -> None:
        async with self._lock:
            doc = self._documents.get(document_id)
            if doc:
                doc.chunks = chunks
                self._persist_to_disk(doc)

    async def update_images(
        self, document_id: str, images: List[ExtractedImageMetadata]
    ) -> None:
        async with self._lock:
            doc = self._documents.get(document_id)
            if doc:
                doc.images = images
                self._persist_to_disk(doc)

    async def record_latency(
        self, document_id: str, stage: str, duration: float
    ) -> None:
        async with self._lock:
            doc = self._documents.get(document_id)
            if doc:
                doc.record_stage_latency(stage, duration)
                self._persist_to_disk(doc)

    def _persist_to_disk(self, doc: DocumentRecord) -> None:
        try:
            doc_dir = settings.documents_dir / doc.document_id
            doc_dir.mkdir(parents=True, exist_ok=True)
            meta_file = doc_dir / "meta.json"
            data = {
                "document_id": doc.document_id,
                "filename": doc.filename,
                "file_path": str(doc.file_path),
                "file_size_bytes": doc.file_size_bytes,
                "status": doc.status.value,
                "page_count": doc.page_count,
                "total_chunks": len(doc.chunks),
                "total_images": len(doc.images),
                "stage_latencies": doc.stage_latencies,
                "error_message": doc.error_message,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            }
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to persist document metadata to disk", extra={"document_id": doc.document_id, "error": str(e)})

    def _load_from_disk(self, document_id: str) -> Optional[DocumentRecord]:
        try:
            meta_file = settings.documents_dir / document_id / "meta.json"
            if not meta_file.exists():
                return None
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc = DocumentRecord(
                document_id=data["document_id"],
                filename=data["filename"],
                file_path=Path(data["file_path"]),
                file_size_bytes=data["file_size_bytes"],
            )
            doc.status = DocumentStatus(data["status"])
            doc.page_count = data.get("page_count", 0)
            doc.stage_latencies = data.get("stage_latencies", {})
            doc.error_message = data.get("error_message")
            doc.created_at = data.get("created_at", "")
            doc.updated_at = data.get("updated_at", "")
            self._documents[document_id] = doc
            return doc
        except Exception as e:
            logger.error("Failed to restore document metadata from disk", extra={"document_id": document_id, "error": str(e)})
            return None


# Global singleton
document_state_manager = DocumentStateManager()
