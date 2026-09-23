from fastapi import APIRouter, HTTPException, status
from app.core.logging import logger
from app.models.document_state import document_state_manager
from app.schemas.vision import VisionQueryRequest, VisionQueryResponse
from app.services.retrieval.vision_engine import vision_engine

router = APIRouter(prefix="/vision", tags=["Vision"])


@router.post(
    "/query",
    response_model=VisionQueryResponse,
    summary="Query an extracted image or chart using Moondream multimodal vision",
)
async def query_figure(request: VisionQueryRequest):
    """
    Submits an extracted figure/diagram to Moondream.
    Detects if the answer incorporates numerical estimates from graphics
    and appends a transparent estimation warning badge.
    """
    doc = await document_state_manager.get_document(request.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con id '{request.document_id}' no encontrado.",
        )

    try:
        response = await vision_engine.analyze_figure(
            document_id=request.document_id,
            image_id=request.image_id,
            prompt=request.prompt,
        )
        return response
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Vision query failed", extra={"document_id": request.document_id, "image_id": request.image_id, "error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en análisis de visión: {str(e)}",
        )
