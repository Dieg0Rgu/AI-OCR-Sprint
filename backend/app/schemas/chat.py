from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    page_number: int
    chunk_id: str
    snippet: str


class RAGResponse(BaseModel):
    answer: str
    citations: List[Citation]
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Stage latencies: retrieval_time, llm_time, total_time in seconds",
    )


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatQueryRequest(BaseModel):
    document_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    conversation_history: List[ChatMessage] = Field(default_factory=list)
