import pytest
from fastapi import HTTPException
from app.core.security import (
    sanitize_filename,
    validate_file_size,
    validate_pdf_content,
    SecurityException,
)


def test_sanitize_filename_prevents_path_traversal():
    dangerous_names = [
        "../../../../etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe",
        "/absolute/path/file.pdf",
        "foo/bar/nested.pdf",
        "test\x00nullbyte.pdf",
        "normal_document.pdf",
    ]

    for raw in dangerous_names:
        clean = sanitize_filename(raw)
        assert "/" not in clean
        assert "\\" not in clean
        assert ".." not in clean
        assert clean.endswith(".pdf")
        assert len(clean) > 4


def test_validate_pdf_content_magic_bytes():
    valid_pdf_header = b"%PDF-1.7\n%some binary data"
    invalid_header = b"NOT_A_PDF_HEADER"
    empty_header = b""

    # Valid header should not raise
    validate_pdf_content(valid_pdf_header, content_type="application/pdf")

    # Invalid header should raise SecurityException (400)
    with pytest.raises(SecurityException) as exc_info:
        validate_pdf_content(invalid_header, content_type="application/pdf")
    assert exc_info.value.status_code == 400
    assert "número mágico" in exc_info.value.detail

    # Empty header should raise SecurityException (400)
    with pytest.raises(SecurityException) as exc_info:
        validate_pdf_content(empty_header, content_type="application/pdf")
    assert exc_info.value.status_code == 400


def test_validate_pdf_content_mime_type():
    valid_header = b"%PDF-1.4"
    invalid_mime = "image/png"

    with pytest.raises(SecurityException) as exc_info:
        validate_pdf_content(valid_header, content_type=invalid_mime)
    assert exc_info.value.status_code == 415


def test_validate_file_size_limit():
    small_size = 5 * 1024 * 1024  # 5 MB
    large_size = 55 * 1024 * 1024  # 55 MB

    # 5 MB is under 50 MB limit
    validate_file_size(small_size, max_mb=50)

    # 55 MB should raise 413
    with pytest.raises(SecurityException) as exc_info:
        validate_file_size(large_size, max_mb=50)
    assert exc_info.value.status_code == 413
    assert "excede el límite" in exc_info.value.detail
