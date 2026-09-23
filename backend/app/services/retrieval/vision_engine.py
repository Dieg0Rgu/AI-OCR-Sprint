import re
import time
from pathlib import Path
from typing import Optional, Tuple
from app.core.logging import logger
from app.models.document_state import document_state_manager
from app.schemas.vision import VisionQueryResponse
from app.services.providers.factory import ProviderFactory


# Regex detecting quantitative / numerical statements
NUMERICAL_PATTERN = re.compile(
    r"\b\d+(?:[\.,]\d+)?\s*(?:%|por ciento|millones|mil|dólares|\$|€|USD|EUR|kg|m|cm|mm|px|unidades|años|días|horas|minutos)?\b",
    re.IGNORECASE,
)


class VisionEngine:
    """
    Multimodal visual inspection engine utilizing LLaVA 7B.
    Detects visual numerical estimations and generates warning disclosures.
    """

    WARNING_MESSAGE = (
        "Aviso: Esta respuesta contiene valores numéricos interpretados visualmente a partir de la "
        "figura o gráfico mediante LLaVA 7B. Al tratarse de inferencia visual, los números representan "
        "estimaciones aproximadas y deben contrastarse con los datos tabulares o el texto fuente del documento."
    )

    async def analyze_figure(
        self,
        document_id: str,
        image_id: str,
        prompt: str,
    ) -> VisionQueryResponse:
        total_start = time.perf_counter()

        # 1. Resolve image file path
        doc = await document_state_manager.get_document(document_id)
        if not doc:
            raise FileNotFoundError(f"Documento '{document_id}' no encontrado.")

        matched_image = next((img for img in doc.images if img.image_id == image_id), None)
        if not matched_image:
            raise FileNotFoundError(f"Figura '{image_id}' no encontrada en el documento.")

        image_path = Path(matched_image.file_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Archivo de imagen no existe en '{image_path}'.")

        # 2. Vision Inference
        vision_provider = ProviderFactory.get_vision_provider()
        vision_start = time.perf_counter()

        system_instruction = (
            f"Analiza la siguiente imagen extraída de la página {matched_image.page_number} "
            f"del documento técnico en respuesta a la pregunta del usuario: {prompt}"
        )

        try:
            analysis = await vision_provider.analyze_image(
                image_path=image_path,
                prompt=f"{system_instruction}\nPregunta: {prompt}",
            )
        except Exception as e:
            logger.warning("Primary vision provider failed, falling back to local vision analyzer", extra={"error": str(e)})
            from app.services.providers.local_provider import FallbackVisionProvider

            analysis = await FallbackVisionProvider().analyze_image(
                image_path=image_path,
                prompt=prompt,
            )

        vision_time = time.perf_counter() - vision_start

        # 3. Detect Numerical Visual Estimations
        has_numbers, warning = self._detect_numerical_estimation(analysis)

        total_time = time.perf_counter() - total_start
        metrics = {
            "vision_time": round(vision_time, 4),
            "total_time": round(total_time, 4),
        }

        logger.info(
            "Vision analysis completed",
            extra={
                "document_id": document_id,
                "image_id": image_id,
                "has_numerical_estimates": has_numbers,
                "metrics": metrics,
            },
        )

        return VisionQueryResponse(
            image_id=image_id,
            analysis=analysis,
            has_numerical_estimates=has_numbers,
            estimation_warning=warning,
            metrics=metrics,
        )

    def _detect_numerical_estimation(self, text: str) -> Tuple[bool, Optional[str]]:
        matches = NUMERICAL_PATTERN.findall(text)
        if matches and len(matches) > 0:
            return True, self.WARNING_MESSAGE
        return False, None


vision_engine = VisionEngine()
