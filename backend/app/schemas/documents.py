from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    OCR_PROCESSING = "ocr_processing"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class ChunkMetadata(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int
    bbox: Optional[List[float]] = None
    associated_image_ids: List[str] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int
    text: str
    bbox: Optional[List[float]] = None
    associated_image_ids: List[str] = Field(default_factory=list)

    @property
    def metadata(self) -> ChunkMetadata:
        return ChunkMetadata(
            chunk_id=self.chunk_id,
            document_id=self.document_id,
            page_number=self.page_number,
            bbox=self.bbox,
            associated_image_ids=self.associated_image_ids,
        )


class ExtractedImageMetadata(BaseModel):
    image_id: str
    document_id: str
    page_number: int
    bbox: Optional[List[float]] = None
    width: int
    height: int
    file_path: str
    url: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    message: str


class DocumentDetailResponse(BaseModel):
    document_id: str
    filename: str
    file_size_bytes: int
    status: DocumentStatus
    page_count: int = 0
    total_chunks: int = 0
    total_images: int = 0
    stage_latencies: Dict[str, float] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class KeywordSearchMatch(BaseModel):
    match_id: str
    document_id: str
    page_number: int
    chunk_id: str
    matched_text: str
    snippet: str
    bbox: Optional[List[float]] = None
    line_number: Optional[int] = None


class KeywordSearchResponse(BaseModel):
    document_id: str
    query: str
    case_sensitive: bool
    exact_match: bool
    total_matches: int
    matches: List[KeywordSearchMatch] = Field(default_factory=list)
