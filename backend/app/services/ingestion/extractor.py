import io
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pymupdf as fitz  # PyMuPDF
from PIL import Image

from app.core.config import settings
from app.core.logging import logger
from app.schemas.documents import ExtractedImageMetadata
from app.services.ingestion.ocr import ocr_service


class PageExtractionResult:
    def __init__(
        self,
        page_number: int,
        text: str,
        blocks: List[Dict[str, Any]],
        images: List[ExtractedImageMetadata],
        used_ocr: bool = False,
    ):
        self.page_number = page_number
        self.text = text
        self.blocks = blocks
        self.images = images
        self.used_ocr = used_ocr


class PDFExtractor:
    """
    Production-grade PDF extractor utilizing PyMuPDF (fitz) with OCR fallback.
    Extracts structured text, block bounding boxes, and embedded visual assets.
    """

    def __init__(self, doc_id: str, file_path: Path):
        self.doc_id = doc_id
        self.file_path = file_path
        self.images_dir = settings.documents_dir / doc_id / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def extract_document(
        self,
    ) -> Tuple[List[PageExtractionResult], List[ExtractedImageMetadata], Dict[str, float]]:
        """
        Processes all pages in the PDF document.
        Returns:
            - List of PageExtractionResult
            - List of all ExtractedImageMetadata
            - Latencies dict: {"extraction_time": ..., "ocr_time": ...}
        """
        start_time = time.perf_counter()
        ocr_time = 0.0

        page_results: List[PageExtractionResult] = []
        all_images: List[ExtractedImageMetadata] = []

        logger.info("Opening PDF document for extraction", extra={"doc_id": self.doc_id, "path": str(self.file_path)})

        try:
            doc = fitz.open(self.file_path)
        except Exception as open_err:
            logger.warning("Standard fitz.open failed, attempting stream recovery", extra={"error": str(open_err)})
            try:
                with open(self.file_path, "rb") as f:
                    stream_bytes = f.read()
                doc = fitz.open(stream=stream_bytes, filetype="pdf")
            except Exception as stream_err:
                from app.core.security import SecurityException, SecurityErrorCode
                raise SecurityException(
                    f"El archivo PDF está dañado o tiene una estructura corrupta: {str(stream_err)}",
                    error_code=SecurityErrorCode.ERROR_CORRUPTED_STREAM,
                    status_code=400,
                )

        try:
            # Handle empty password protected PDFs
            if doc.needs_pass:
                logger.info("PDF requires password, attempting empty-string authentication", extra={"doc_id": self.doc_id})
                if not doc.authenticate(""):
                    from app.core.security import SecurityException, SecurityErrorCode
                    raise SecurityException(
                        "El documento PDF está protegido con contraseña cifrada no vacía.",
                        error_code=SecurityErrorCode.ERROR_CORRUPTED_STREAM,
                        status_code=400,
                    )

            total_pages = len(doc)
            if total_pages == 0:
                from app.core.security import SecurityException, SecurityErrorCode
                raise SecurityException(
                    "El documento PDF no contiene páginas legibles.",
                    error_code=SecurityErrorCode.ERROR_EMPTY_PAYLOAD,
                    status_code=400,
                )

            for page_idx in range(total_pages):
                page_number = page_idx + 1
                try:
                    page = doc[page_idx]
                except Exception as p_err:
                    logger.warning("Failed to access page, skipping to fallback", extra={"doc_id": self.doc_id, "page": page_number, "error": str(p_err)})
                    page_results.append(
                        PageExtractionResult(
                            page_number=page_number,
                            text="[Página malformada o ilegible]",
                            blocks=[],
                            images=[],
                            used_ocr=False,
                        )
                    )
                    continue

                # 1. Extract text and blocks
                try:
                    raw_blocks = page.get_text("blocks")
                except Exception:
                    raw_blocks = []
                text_blocks = []
                full_text_parts = []

                for b in raw_blocks:
                    # block_type 0 is text, 1 is image
                    if b[6] == 0:
                        block_text = b[4].strip()
                        if block_text:
                            text_blocks.append({
                                "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                                "text": block_text,
                                "block_no": b[5],
                            })
                            full_text_parts.append(block_text)

                combined_text = "\n\n".join(full_text_parts)
                used_ocr = False

                # 2. Check for OCR fallback condition (scanned page or minimal text)
                if len(combined_text.strip()) < 50:
                    ocr_start = time.perf_counter()
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    ocr_text = ocr_service.run_ocr(img_bytes)
                    ocr_duration = time.perf_counter() - ocr_start
                    ocr_time += ocr_duration

                    if ocr_text and len(ocr_text) > len(combined_text):
                        logger.info(
                            "OCR fallback applied to page",
                            extra={"doc_id": self.doc_id, "page_number": page_number, "chars_extracted": len(ocr_text)},
                        )
                        combined_text = ocr_text
                        used_ocr = True
                        text_blocks.append({
                            "bbox": [0.0, 0.0, float(page.rect.width), float(page.rect.height)],
                            "text": ocr_text,
                            "block_no": 0,
                        })

                # 3. Extract embedded images and figures
                page_images = self._extract_page_images(doc, page, page_number)
                all_images.extend(page_images)

                page_results.append(
                    PageExtractionResult(
                        page_number=page_number,
                        text=combined_text,
                        blocks=text_blocks,
                        images=page_images,
                        used_ocr=used_ocr,
                    )
                )
        finally:
            doc.close()

        extraction_time = time.perf_counter() - start_time

        latencies = {
            "extraction_time": round(extraction_time, 4),
            "ocr_time": round(ocr_time, 4),
        }

        logger.info(
            "Extraction completed",
            extra={
                "doc_id": self.doc_id,
                "pages": len(page_results),
                "images": len(all_images),
                "latencies": latencies,
            },
        )

        return page_results, all_images, latencies

    def _extract_page_images(
        self, doc: fitz.Document, page: fitz.Page, page_number: int
    ) -> List[ExtractedImageMetadata]:
        page_images: List[ExtractedImageMetadata] = []
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue

                image_bytes = base_image["image"]
                width = base_image["width"]
                height = base_image["height"]
                ext = base_image.get("ext", "png").lower()

                # Filter out tiny icon noise (e.g., bullet points or 1x1 spacer images)
                if width < 50 or height < 50:
                    continue

                image_id = f"img_{self.doc_id}_{page_number}_{img_idx}_{uuid.uuid4().hex[:6]}"
                file_name = f"{image_id}.{ext}"
                file_path = self.images_dir / file_name

                with open(file_path, "wb") as f:
                    f.write(image_bytes)

                # Attempt to get bounding box coordinates on the page
                rects = page.get_image_rects(xref)
                bbox = None
                if rects:
                    r = rects[0]
                    bbox = [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]

                url = f"/api/v1/documents/{self.doc_id}/images/{image_id}"

                meta = ExtractedImageMetadata(
                    image_id=image_id,
                    document_id=self.doc_id,
                    page_number=page_number,
                    bbox=bbox,
                    width=width,
                    height=height,
                    file_path=str(file_path),
                    url=url,
                )
                page_images.append(meta)
            except Exception as e:
                logger.warning(
                    "Failed to extract image xref",
                    extra={"doc_id": self.doc_id, "page": page_number, "xref": xref, "error": str(e)},
                )

        return page_images
