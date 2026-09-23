import os
import re
from pathlib import Path
from typing import BinaryIO
from fastapi import HTTPException, status
from app.core.logging import logger

PDF_MAGIC_BYTES = b"%PDF-"


class SecurityErrorCode:
    ERROR_EMPTY_PAYLOAD = "ERROR_EMPTY_PAYLOAD"
    ERROR_INVALID_MIME_OR_MAGIC = "ERROR_INVALID_MIME_OR_MAGIC"
    ERROR_SIZE_LIMIT_EXCEEDED = "ERROR_SIZE_LIMIT_EXCEEDED"
    ERROR_CORRUPTED_STREAM = "ERROR_CORRUPTED_STREAM"
    ERROR_PAGE_LIMIT_EXCEEDED = "ERROR_PAGE_LIMIT_EXCEEDED"
    ERROR_TIMEOUT_INGESTION = "ERROR_TIMEOUT_INGESTION"


class SecurityException(HTTPException):
    def __init__(
        self,
        detail: str,
        error_code: str = "ERROR_SECURITY_VIOLATION",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.error_code = error_code
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"X-Error-Code": error_code},
        )


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes an uploaded filename to prevent Path Traversal and shell injection attacks.
    Extracts only the basename, removes directory separators, and strips dangerous characters.
    """
    if not filename or not filename.strip():
        return "document.pdf"

    # Take purely the basename to eliminate ../ or absolute paths
    base = Path(filename).name

    # Remove any null bytes or control characters
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)

    # Normalize characters: only allow alphanumerics, dashes, underscores, and dots
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base)

    # Collapse multiple dots or underscores
    sanitized = re.sub(r"\.{2,}", ".", sanitized)
    sanitized = re.sub(r"_{2,}", "_", sanitized)

    if not sanitized.lower().endswith(".pdf"):
        sanitized = f"{sanitized}.pdf"

    return sanitized


def validate_pdf_content(header_bytes: bytes, content_type: str | None = None) -> None:
    """
    Validates that the file has valid PDF magic bytes and content type.
    """
    if not header_bytes:
        logger.warning("Empty file payload rejected.")
        raise SecurityException(
            "El archivo subido está vacío.",
            error_code=SecurityErrorCode.ERROR_EMPTY_PAYLOAD,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not header_bytes.startswith(PDF_MAGIC_BYTES):
        logger.warning("Magic bytes validation failed. Header does not start with %%PDF-", extra={"header_preview": header_bytes[:10]})
        raise SecurityException(
            "El archivo no es un documento PDF válido (falló verificación de número mágico %PDF-).",
            error_code=SecurityErrorCode.ERROR_INVALID_MIME_OR_MAGIC,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if content_type and content_type.lower() not in {"application/pdf", "application/x-pdf", "binary/octet-stream"}:
        logger.warning("Content-Type validation failed.", extra={"content_type": content_type})
        raise SecurityException(
            f"Tipo MIME inválido: {content_type}. Solo se permite application/pdf.",
            error_code=SecurityErrorCode.ERROR_INVALID_MIME_OR_MAGIC,
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )


def validate_file_size(size_bytes: int, max_mb: int = 50) -> None:
    """
    Validates file size against configured limit.
    """
    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        logger.warning("File size exceeded maximum limit", extra={"size_bytes": size_bytes, "max_bytes": max_bytes})
        raise SecurityException(
            f"El tamaño del archivo ({size_bytes / (1024*1024):.2f} MB) excede el límite permitido de {max_mb} MB.",
            error_code=SecurityErrorCode.ERROR_SIZE_LIMIT_EXCEEDED,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


def safe_cleanup_path(path: Path | str | None) -> None:
    """
    Purges temporary or corrupted files safely without raising exceptions.
    """
    if path is None:
        return
    try:
        target = Path(path)
        if target.is_file():
            target.unlink(missing_ok=True)
            logger.info("Purged file successfully", extra={"path": str(target)})
        elif target.is_dir():
            for child in target.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            target.rmdir()
            logger.info("Purged directory successfully", extra={"path": str(target)})
    except Exception as e:
        logger.error("Failed to safely cleanup path", extra={"path": str(path), "error": str(e)})
