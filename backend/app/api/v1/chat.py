from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from app.core.logging import logger
from app.models.document_state import document_state_manager
from app.schemas.chat import ChatQueryRequest, RAGResponse
from app.schemas.documents import DocumentStatus
from app.services.retrieval.rag_engine import rag_engine

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.post(
    "/query",
    response_model=RAGResponse,
    summary="Ask questions about an indexed document with verifiable citations",
)
async def query_document(request: ChatQueryRequest):
    """
    Executes hybrid retrieval (Dense + BM25 with RRF), queries Qwen 2.5,
    and returns answer grounded in retrieved chunks with exact citations.
    """
    doc = await document_state_manager.get_document(request.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con id '{request.document_id}' no encontrado.",
        )

    if doc.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El documento aún no está listo para consultas (estado actual: {doc.status.value}).",
        )

    try:
        response = await rag_engine.answer_query(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k,
            conversation_history=request.conversation_history,
        )
        return response
    except Exception as e:
        logger.error("RAG query failed", extra={"document_id": request.document_id, "error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar consulta RAG: {str(e)}",
        )


@router.post(
    "/stream",
    summary="Streaming RAG query using Server-Sent Events (SSE) for low TTFT",
)
async def stream_query_document(request: ChatQueryRequest):
    """
    Executes hybrid retrieval and streams tokens and citations in real time via SSE.
    Events: 'citations', 'token', 'ttft', 'metrics', 'done'.
    """
    doc = await document_state_manager.get_document(request.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con id '{request.document_id}' no encontrado.",
        )

    if doc.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El documento aún no está listo para consultas (estado actual: {doc.status.value}).",
        )

    return StreamingResponse(
        rag_engine.answer_query_stream(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k,
            conversation_history=request.conversation_history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
