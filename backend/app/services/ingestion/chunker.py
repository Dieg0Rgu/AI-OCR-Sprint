import re
from typing import List, Optional
from app.schemas.documents import DocumentChunk
from app.services.ingestion.extractor import PageExtractionResult


class DocumentChunker:
    """
    Page-aware semantic text chunker.
    Preserves page boundaries, bounding boxes, and associates page images.
    """

    def __init__(self, target_chunk_size: int = 600, chunk_overlap: int = 100):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        document_id: str,
        page_results: List[PageExtractionResult],
    ) -> List[DocumentChunk]:
        all_chunks: List[DocumentChunk] = []

        for page in page_results:
            page_chunks = self._chunk_page(document_id, page)
            all_chunks.extend(page_chunks)

        return all_chunks

    def _chunk_page(
        self, document_id: str, page: PageExtractionResult
    ) -> List[DocumentChunk]:
        page_chunks: List[DocumentChunk] = []
        associated_image_ids = [img.image_id for img in page.images]

        # If page has blocks, group blocks logically
        if page.blocks:
            current_text_parts: List[str] = []
            current_bboxes: List[List[float]] = []
            current_len = 0
            chunk_idx = 0

            for block in page.blocks:
                block_text = block["text"]
                block_bbox = block["bbox"]

                if current_len + len(block_text) > self.target_chunk_size and current_text_parts:
                    # Flush current chunk
                    chunk_text = "\n".join(current_text_parts)
                    merged_bbox = self._merge_bboxes(current_bboxes)
                    chunk_id = f"{document_id}_p{page.page_number}_c{chunk_idx}"

                    page_chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            document_id=document_id,
                            page_number=page.page_number,
                            text=chunk_text,
                            bbox=merged_bbox,
                            associated_image_ids=associated_image_ids,
                        )
                    )
                    chunk_idx += 1

                    # Keep last part for overlap if applicable
                    if self.chunk_overlap > 0 and len(current_text_parts[-1]) <= self.chunk_overlap:
                        current_text_parts = [current_text_parts[-1], block_text]
                        current_bboxes = [current_bboxes[-1], block_bbox]
                        current_len = sum(len(p) for p in current_text_parts)
                    else:
                        current_text_parts = [block_text]
                        current_bboxes = [block_bbox]
                        current_len = len(block_text)
                else:
                    current_text_parts.append(block_text)
                    current_bboxes.append(block_bbox)
                    current_len += len(block_text)

            # Flush remaining
            if current_text_parts:
                chunk_text = "\n".join(current_text_parts)
                merged_bbox = self._merge_bboxes(current_bboxes)
                chunk_id = f"{document_id}_p{page.page_number}_c{chunk_idx}"

                page_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_number=page.page_number,
                        text=chunk_text,
                        bbox=merged_bbox,
                        associated_image_ids=associated_image_ids,
                    )
                )

        elif page.text.strip():
            # Fallback for plain page text without fine-grained blocks
            text = page.text.strip()
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            chunk_idx = 0
            cur_parts = []
            cur_len = 0

            for p in paragraphs:
                if cur_len + len(p) > self.target_chunk_size and cur_parts:
                    chunk_id = f"{document_id}_p{page.page_number}_c{chunk_idx}"
                    page_chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            document_id=document_id,
                            page_number=page.page_number,
                            text="\n\n".join(cur_parts),
                            bbox=None,
                            associated_image_ids=associated_image_ids,
                        )
                    )
                    chunk_idx += 1
                    cur_parts = [p]
                    cur_len = len(p)
                else:
                    cur_parts.append(p)
                    cur_len += len(p)

            if cur_parts:
                chunk_id = f"{document_id}_p{page.page_number}_c{chunk_idx}"
                page_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_number=page.page_number,
                        text="\n\n".join(cur_parts),
                        bbox=None,
                        associated_image_ids=associated_image_ids,
                    )
                )

        return page_chunks

    def _merge_bboxes(self, bboxes: List[List[float]]) -> Optional[List[float]]:
        if not bboxes:
            return None
        min_x0 = min(b[0] for b in bboxes)
        min_y0 = min(b[1] for b in bboxes)
        max_x1 = max(b[2] for b in bboxes)
        max_y1 = max(b[3] for b in bboxes)
        return [round(min_x0, 2), round(min_y0, 2), round(max_x1, 2), round(max_y1, 2)]
