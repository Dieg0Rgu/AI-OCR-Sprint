from typing import Dict, Optional
from pydantic import BaseModel, Field


class VisionQueryRequest(BaseModel):
    document_id: str
    image_id: str
    prompt: str = Field(..., min_length=1, max_length=1000)


class VisionQueryResponse(BaseModel):
    image_id: str
    analysis: str
    has_numerical_estimates: bool
    estimation_warning: Optional[str] = None
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Vision latency metrics: vision_time, total_time",
    )
