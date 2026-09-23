import time
from typing import Optional, Dict
from pydantic import BaseModel, Field
from app.schemas.documents import DocumentStatus


class SSEEventPayload(BaseModel):
    document_id: str
    status: DocumentStatus
    progress_percent: float = Field(ge=0.0, le=100.0)
    message: str
    error: Optional[str] = None
    stage_latencies: Dict[str, float] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    def to_sse_data(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"
