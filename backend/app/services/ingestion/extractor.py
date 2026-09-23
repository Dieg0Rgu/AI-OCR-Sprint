import io
import re
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import pymupdf as fitz  # PyMuPDF
from PIL import Image

try:
    import pypdf
except ImportError:
    pypdf = None

from app.core.config import settings
from app.core.logging import logger
from app.schemas.documents import ExtractedImageMetadata
from app.services.ingestion.ocr import ocr_service

CAPTION_REGEX = re.compile(
    r"^(?:Figura|Fig\.|Figure|Gráfico|Grafico|Esquema|Diagrama|Tabla|Cuadro|Illustration)\s*\d*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

HEADER_REGEX = re.compile(
    r"^(?:(?:SECCIÓN|CAPÍTULO|SECCION|SECTION|CAPITULO)\s*#?\d+|(?:\d+\.)+\s+[A-ZÁÉÍÓÚÑ]|DOCUMENTO\s+TÉCNICO|[A-ZÁÉÍÓÚÑ\s]{4,70}$)",
    re.IGNORECASE,
)


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
    Production-grade PDF extractor utilizing PyMuPDF (fitz) with OCR and pypdf fallback.
    Extracts structured text, block bounding boxes, 100% of visual assets, and
    associates proximity-based image-to-text context (caption, section title, surrounding text).
    """

    def __init__(self, doc_id: str, file_path: Path):
        self.doc_id = doc_id
        self.file_path = file_path
        self.images_dir = settings.documents_dir / doc_id / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.image_counter = 0

    def extract_document(
        self,
    ) -> Tuple[List[PageExtractionResult], List[ExtractedImageMetadata], Dict[str, float]]:
        start_time = time.perf_counter()
        ocr_time = 0.0

        page_results: List[PageExtractionResult] = []
        all_images: List[ExtractedImageMetadata] = []

        logger.info("Opening PDF document for extraction", extra={"doc_id": self.doc_id, "path": str(self.file_path)})

        doc = None
        try:
            doc = fitz.open(self.file_path)
        except Exception as open_err:
            logger.warning("Standard fitz.open failed, attempting stream recovery", extra={"error": str(open_err)})
            try:
                with open(self.file_path, "rb") as f:
                    stream_bytes = f.read()
                doc = fitz.open(stream=stream_bytes, filetype="pdf")
            except Exception as stream_err:
                if pypdf is not None:
                    try:
                        logger.info("Attempting pypdf fallback reader", extra={"doc_id": self.doc_id})
                        return self._fallback_extract_pypdf(stream_bytes, start_time)
                    except Exception as pypdf_err:
                        logger.error("pypdf fallback also failed", extra={"error": str(pypdf_err)})
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
                    # block_type 0 is text
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

                # 3. Extract 100% of embedded images and associate Image-to-Text context
                page_images = self._extract_page_images(doc, page, page_number, text_blocks)
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
            if doc is not None:
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
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_number: int,
        text_blocks: List[Dict[str, Any]],
    ) -> List[ExtractedImageMetadata]:
        """
        Scans and extracts 100% of embedded images without arbitrary resolution cuts.
        Computes bounding box coordinates and extracts proximity-based text context:
        - Caption (pie de figura)
        - Section title (título de sección)
        - Surrounding text (párrafos adyacentes anterior y posterior)
        """
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

                # Filter ONLY corrupt or microscopic noise (< 5px) to guarantee 100% figure capture
                if width < 5 or height < 5:
                    continue

                self.image_counter += 1
                image_order = self.image_counter

                image_id = f"img_{self.doc_id}_{page_number}_{img_idx}_{uuid.uuid4().hex[:6]}"
                file_name = f"{image_id}.{ext}"
                file_path = self.images_dir / file_name

                with open(file_path, "wb") as f:
                    f.write(image_bytes)

                # Relative bounding box on page
                rects = page.get_image_rects(xref)
                bbox = None
                if rects:
                    r = rects[0]
                    bbox = [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]

                # Extract Proximity Image-to-Text Context
                caption, section_title, surrounding_text = self._extract_image_context(
                    bbox=bbox,
                    text_blocks=text_blocks,
                    page_number=page_number,
                )

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
                    order=image_order,
                    caption=caption,
                    section_title=section_title,
                    surrounding_text=surrounding_text,
                )
                page_images.append(meta)
            except Exception as e:
                logger.warning(
                    "Failed to extract image xref",
                    extra={"doc_id": self.doc_id, "page": page_number, "xref": xref, "error": str(e)},
                )

        return page_images

    def _extract_image_context(
        self,
        bbox: Optional[List[float]],
        text_blocks: List[Dict[str, Any]],
        page_number: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Associates adjacent textual context by analyzing vertical spatial proximity:
        1. Caption (pie de figura): text block below/above image matching caption syntax or within delta.
        2. Section title: preceding heading or first title block on the page.
        3. Surrounding text: preceding and subsequent textual paragraphs.
        """
        if not text_blocks:
            return None, None, f"Figura técnica en página {page_number}."

        iy0 = bbox[1] if bbox else 0.0
        iy1 = bbox[3] if bbox else 400.0

        caption: Optional[str] = None
        section_title: Optional[str] = None
        prev_paragraph: Optional[str] = None
        next_paragraph: Optional[str] = None

        # 1. Search for caption
        best_caption_dist = float("inf")
        for b in text_blocks:
            b_box = b["bbox"]
            b_text = b["text"]
            b_y0, b_y1 = b_box[1], b_box[3]

            # Direct regex match for caption
            if CAPTION_REGEX.search(b_text):
                caption = b_text
                break

            # Distance below image
            dist_below = b_y0 - iy1
            if 0 <= dist_below <= 80 and dist_below < best_caption_dist and len(b_text) < 220:
                best_caption_dist = dist_below
                caption = b_text

        # 2. Search for section title (blocks preceding the image)
        for b in text_blocks:
            b_text = b["text"]
            b_y1 = b["bbox"][3]
            if b_y1 <= iy0 + 5:
                if HEADER_REGEX.search(b_text) or (len(b_text) < 80 and b_text.isupper()):
                    section_title = b_text

        if not section_title and text_blocks:
            # Fallback to the first text block if short
            first_text = text_blocks[0]["text"]
            if len(first_text) < 90:
                section_title = first_text

        # 3. Find preceding and subsequent paragraphs
        min_prev_dist = float("inf")
        min_next_dist = float("inf")

        for b in text_blocks:
            b_text = b["text"]
            b_box = b["bbox"]
            b_y0, b_y1 = b_box[1], b_box[3]

            if b_text == caption or b_text == section_title:
                continue

            # Preceding paragraph
            if b_y1 <= iy0 + 5:
                dist = iy0 - b_y1
                if dist < min_prev_dist:
                    min_prev_dist = dist
                    prev_paragraph = b_text

            # Following paragraph
            elif b_y0 >= iy1 - 5:
                dist = b_y0 - iy1
                if dist < min_next_dist:
                    min_next_dist = dist
                    next_paragraph = b_text

        # 4. Construct comprehensive surrounding text block
        parts = []
        if section_title:
            parts.append(f"Sección: {section_title.strip()}")
        if caption:
            parts.append(f"Pie de figura: {caption.strip()}")
        if prev_paragraph:
            parts.append(f"Párrafo anterior: {prev_paragraph.strip()}")
        if next_paragraph:
            parts.append(f"Párrafo posterior: {next_paragraph.strip()}")

        if not parts:
            # Fallback to page text summary
            joined_text = " ".join([b["text"].strip() for b in text_blocks[:2]])
            surrounding_text = f"Entorno textual de la página {page_number}: {joined_text[:350]}"
        else:
            surrounding_text = " // ".join(parts)

        return caption, section_title, surrounding_text

    def _fallback_extract_pypdf(
        self, stream_bytes: bytes, start_time: float
    ) -> Tuple[List[PageExtractionResult], List[ExtractedImageMetadata], Dict[str, float]]:
        """
        Pure-python extraction fallback using pypdf for resilient stream recovery.
        """
        reader = pypdf.PdfReader(io.BytesIO(stream_bytes))
        page_results: List[PageExtractionResult] = []
        all_images: List[ExtractedImageMetadata] = []

        total_pages = len(reader.pages)
        for page_idx in range(total_pages):
            page_number = page_idx + 1
            page = reader.pages[page_idx]
            extracted_text = page.extract_text() or ""

            # Extract embedded images via pypdf
            page_images: List[ExtractedImageMetadata] = []
            for img_idx, img_obj in enumerate(page.images):
                try:
                    self.image_counter += 1
                    image_id = f"img_{self.doc_id}_{page_number}_{img_idx}_{uuid.uuid4().hex[:6]}"
                    ext = img_obj.name.split(".")[-1].lower() if "." in img_obj.name else "png"
                    file_name = f"{image_id}.{ext}"
                    file_path = self.images_dir / file_name

                    with open(file_path, "wb") as f:
                        f.write(img_obj.data)

                    img_pil = Image.open(io.BytesIO(img_obj.data))
                    w, h = img_pil.size

                    meta = ExtractedImageMetadata(
                        image_id=image_id,
                        document_id=self.doc_id,
                        page_number=page_number,
                        bbox=None,
                        width=w,
                        height=h,
                        file_path=str(file_path),
                        url=f"/api/v1/documents/{self.doc_id}/images/{image_id}",
                        order=self.image_counter,
                        caption=None,
                        section_title=None,
                        surrounding_text=f"Figura extraída de página {page_number}: {extracted_text[:200]}",
                    )
                    page_images.append(meta)
                except Exception as img_err:
                    logger.warning("pypdf image extraction error", extra={"error": str(img_err)})

            all_images.extend(page_images)
            page_results.append(
                PageExtractionResult(
                    page_number=page_number,
                    text=extracted_text,
                    blocks=[{"bbox": [0.0, 0.0, 595.0, 842.0], "text": extracted_text, "block_no": 0}],
                    images=page_images,
                    used_ocr=False,
                )
            )

        latencies = {
            "extraction_time": round(time.perf_counter() - start_time, 4),
            "ocr_time": 0.0,
        }
        return page_results, all_images, latencies

