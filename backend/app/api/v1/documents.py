import re
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, Query, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import logger
from app.core.security import (
    sanitize_filename,
    validate_file_size,
    validate_pdf_content,
    safe_cleanup_path,
    SecurityException,
    SecurityErrorCode,
)
from app.models.document_state import document_state_manager
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentStatus,
    DocumentUploadResponse,
    ExtractedImageMetadata,
    KeywordSearchMatch,
    KeywordSearchResponse,
)
from app.services.ingestion.pipeline import ingestion_pipeline

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload and begin asynchronous ingestion of a PDF document",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Streams PDF file directly to disk in 64 KB chunks.
    Validates MIME type, magic bytes, and size dynamically without buffer exhaustion.
    Responds immediately with HTTP 202 Accepted and document_id.
    Dispatches asynchronous extraction and indexing pipeline.
    """
    raw_filename = file.filename or "document.pdf"
    clean_filename = sanitize_filename(raw_filename)

    document_id = str(uuid.uuid4())
    doc_storage_dir = settings.documents_dir / document_id
    doc_storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_storage_dir / "original.pdf"

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    total_bytes_written = 0
    first_chunk = True

    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(65536)  # 64 KB
                if not chunk:
                    break

                if first_chunk:
                    validate_pdf_content(chunk, content_type=file.content_type)
                    first_chunk = False

                total_bytes_written += len(chunk)
                if total_bytes_written > max_bytes:
                    raise SecurityException(
                        f"El tamaño del archivo ({total_bytes_written / (1024*1024):.2f} MB) excede el límite permitido de {settings.MAX_UPLOAD_SIZE_MB} MB.",
                        error_code=SecurityErrorCode.ERROR_SIZE_LIMIT_EXCEEDED,
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
                f.write(chunk)

        if total_bytes_written == 0:
            raise SecurityException(
                "El archivo subido está vacío.",
                error_code=SecurityErrorCode.ERROR_EMPTY_PAYLOAD,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as e:
        safe_cleanup_path(doc_storage_dir)
        if isinstance(e, SecurityException):
            raise
        logger.error("Failed to stream uploaded file to disk", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando archivo en disco: {str(e)}",
        )

    # Register initial document record
    await document_state_manager.register_document(
        document_id=document_id,
        filename=clean_filename,
        file_path=file_path,
        file_size_bytes=total_bytes_written,
    )

    # Dispatch ingestion in background
    background_tasks.add_task(ingestion_pipeline.process_document, document_id, file_path)

    logger.info("Upload accepted", extra={"document_id": document_id, "doc_name": clean_filename, "size_bytes": total_bytes_written})

    return DocumentUploadResponse(
        document_id=document_id,
        filename=clean_filename,
        status=DocumentStatus.UPLOADED,
        message="Documento aceptado. Ingestión asíncrona iniciada.",
    )


@router.get(
    "",
    response_model=List[DocumentDetailResponse],
    summary="List all indexed documents",
)
async def list_documents():
    return await document_state_manager.list_documents()


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document processing status and details",
)
async def get_document(document_id: str):
    doc = await document_state_manager.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con id '{document_id}' no encontrado.",
        )
    return doc.to_detail_response()


@router.get(
    "/{document_id}/file",
    summary="Download or stream the original PDF file",
)
async def get_document_file(document_id: str):
    doc = await document_state_manager.get_document(document_id)
    if not doc or not doc.file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo original no encontrado en almacenamiento.",
        )
    return FileResponse(
        path=doc.file_path,
        media_type="application/pdf",
        filename=doc.filename,
    )


@router.get(
    "/{document_id}/images",
    response_model=List[ExtractedImageMetadata],
    summary="List all extracted figures and images for a document",
)
async def list_document_images(document_id: str):
    doc = await document_state_manager.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado.",
        )
    return doc.images


@router.get(
    "/{document_id}/images/{image_id}",
    summary="Retrieve extracted image binary",
)
async def get_image_file(document_id: str, image_id: str):
    doc = await document_state_manager.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado.",
        )

    matched = next((img for img in doc.images if img.image_id == image_id), None)
    if not matched or not Path(matched.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Figura '{image_id}' no encontrada.",
        )

    # Determine media type based on extension
    ext = Path(matched.file_path).suffix.lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"

    return FileResponse(
        path=Path(matched.file_path),
        media_type=media_type,
    )


@router.get(
    "/{document_id}/search",
    response_model=KeywordSearchResponse,
    summary="Fast lexical keyword search across document chunks with page & bbox coordinates",
)
async def search_document_keywords(
    document_id: str,
    q: str = Query(..., min_length=1, description="Search query keyword or phrase"),
    case_sensitive: bool = Query(False, description="Whether search should be case sensitive"),
    exact: bool = Query(False, description="Match whole words only"),
):
    doc = await document_state_manager.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado.",
        )

    query_str = q.strip()
    if not query_str:
        return KeywordSearchResponse(
            document_id=document_id,
            query=q,
            case_sensitive=case_sensitive,
            exact_match=exact,
            total_matches=0,
            matches=[],
        )

    flags = 0 if case_sensitive else re.IGNORECASE
    escaped = re.escape(query_str)
    pattern_str = rf"\b{escaped}\b" if exact else escaped

    try:
        pattern = re.compile(pattern_str, flags)
    except re.error:
        pattern = re.compile(re.escape(query_str), flags)

    matches: List[KeywordSearchMatch] = []
    match_counter = 0

    for chunk in doc.chunks:
        text = chunk.text
        lines = text.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            for match in pattern.finditer(line):
                match_counter += 1
                start, end = match.span()
                matched_text = match.group(0)

                pre_start = max(0, start - 45)
                post_end = min(len(line), end + 45)

                prefix = ("..." if pre_start > 0 else "") + line[pre_start:start]
                suffix = line[end:post_end] + ("..." if post_end < len(line) else "")
                snippet = f"{prefix}**{matched_text}**{suffix}".strip()

                matches.append(
                    KeywordSearchMatch(
                        match_id=f"m_{document_id[:8]}_{chunk.page_number}_{match_counter}",
                        document_id=document_id,
                        page_number=chunk.page_number,
                        chunk_id=chunk.chunk_id,
                        matched_text=matched_text,
                        snippet=snippet,
                        bbox=chunk.bbox,
                        line_number=line_idx,
                    )
                )

    return KeywordSearchResponse(
        document_id=document_id,
        query=q,
        case_sensitive=case_sensitive,
        exact_match=exact,
        total_matches=len(matches),
        matches=matches,
    )
