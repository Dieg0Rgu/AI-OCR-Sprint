import asyncio
from typing import Dict, List, Optional
from app.core.logging import logger
from app.schemas.events import SSEEventPayload
from app.schemas.documents import DocumentStatus


class DocumentEventBroadcaster:
    """
    In-memory asynchronous event broadcaster for Server-Sent Events (SSE).
    Maintains subscriber queues per document_id and caches the latest event
    so clients connecting late immediately receive current state.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._latest_event: Dict[str, SSEEventPayload] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, document_id: str) -> asyncio.Queue:
        async with self._lock:
            queue: asyncio.Queue = asyncio.Queue(maxsize=100)
            if document_id not in self._subscribers:
                self._subscribers[document_id] = []
            self._subscribers[document_id].append(queue)

            # If an event already exists for this document, immediately dispatch it
            if document_id in self._latest_event:
                await queue.put(self._latest_event[document_id])

            logger.info("New SSE subscriber registered", extra={"document_id": document_id, "active_subscribers": len(self._subscribers[document_id])})
            return queue

    async def unsubscribe(self, document_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            if document_id in self._subscribers:
                if queue in self._subscribers[document_id]:
                    self._subscribers[document_id].remove(queue)
                if not self._subscribers[document_id]:
                    del self._subscribers[document_id]
            logger.info("SSE subscriber removed", extra={"document_id": document_id})

    async def publish(self, event: SSEEventPayload) -> None:
        async with self._lock:
            document_id = event.document_id
            self._latest_event[document_id] = event
            subscribers = self._subscribers.get(document_id, [])
            for queue in subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("SSE queue full, dropping event", extra={"document_id": document_id})

    def get_latest_event(self, document_id: str) -> Optional[SSEEventPayload]:
        return self._latest_event.get(document_id)

    async def cleanup(self, document_id: str) -> None:
        async with self._lock:
            if document_id in self._subscribers:
                del self._subscribers[document_id]
            if document_id in self._latest_event:
                del self._latest_event[document_id]


event_broadcaster = DocumentEventBroadcaster()
