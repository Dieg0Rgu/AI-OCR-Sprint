import io
import shutil
from typing import Union
from PIL import Image
from app.core.logging import logger

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


class OCRService:
    """
    OCR Fallback service for scanned PDF pages or textless document images.
    Prioritizes Tesseract (supporting spa + eng), with graceful handling.
    """

    def __init__(self):
        self.is_available = TESSERACT_AVAILABLE
        if self.is_available:
            logger.info("Tesseract binary detected on system.")
        else:
            logger.warning("Tesseract binary not found on host. OCR fallback will operate in graceful degraded mode.")

    def run_ocr(self, image_data: Union[bytes, Image.Image], lang: str = "spa+eng") -> str:
        """
        Runs OCR on given image bytes or PIL Image.
        Returns extracted text.
        """
        if not self.is_available:
            return ""

        try:
            import pytesseract

            if isinstance(image_data, bytes):
                img = Image.open(io.BytesIO(image_data))
            else:
                img = image_data

            # Try requested languages, fallback to eng if spa language pack not installed
            try:
                text = pytesseract.image_to_string(img, lang=lang)
            except Exception:
                text = pytesseract.image_to_string(img, lang="eng")

            return text.strip()
        except Exception as e:
            logger.warning("OCR processing encountered an issue", extra={"error": str(e)})
            return ""


ocr_service = OCRService()
