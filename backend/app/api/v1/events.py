import asyncio
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.logging import logger
from app.models.document_state import document_state_manager
from app.schemas.documents import DocumentStatus
from app.services.ingestion.broadcaster import event_broadcaster

router = APIRouter(prefix="/documents", tags=["Events"])


@router.get(
    "/{document_id}/events",
    summary="Subscribe to real-time ingestion events via Server-Sent Events (SSE)",
)
async def document_events_stream(document_id: str, request: Request):
    """
    Server-Sent Events endpoint streaming pipeline progress and stage latencies.
    Closes automatically once processing reaches 'ready' or 'failed'.
    """
    doc = await document_state_manager.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con id '{document_id}' no encontrado.",
        )

    async def event_generator():
        queue = await event_broadcaster.subscribe(document_id)
        logger.info("SSE client connected", extra={"document_id": document_id})
        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    logger.info("SSE client disconnected by user request", extra={"document_id": document_id})
                    break

                try:
                    # Wait up to 15 seconds for next event; send keepalive comment if silent
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event.to_sse_data()

                    # Stop streaming once terminal state is reached
                    if event.status in {DocumentStatus.READY, DocumentStatus.FAILED}:
                        logger.info("Terminal state reached, ending SSE stream", extra={"document_id": document_id, "status": event.status.value})
                        break
                except asyncio.TimeoutError:
                    # SSE Keep-alive heartbeat
                    yield ": ping\n\n"

        except asyncio.CancelledError:
            logger.info("SSE generator cancelled", extra={"document_id": document_id})
        finally:
            await event_broadcaster.unsubscribe(document_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
