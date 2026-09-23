import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core.logging import logger
from app.schemas.documents import DocumentChunk


def tokenize_text(text: str) -> List[str]:
    """Simple alphanumeric tokenization with lowercasing."""
    return re.findall(r"\b\w+\b", text.lower())


class DocumentBM25Index:
    def __init__(self, document_id: str, chunks: List[DocumentChunk]):
        self.document_id = document_id
        self.chunks = chunks
        self.tokenized_corpus = [tokenize_text(c.text) for c in chunks]
        self.bm25 = BM25Okapi(self.tokenized_corpus) if self.tokenized_corpus else None

    def search(self, query: str, top_k: int = 10) -> List[Tuple[DocumentChunk, float]]:
        if not self.bm25 or not self.chunks:
            return []

        tokens = tokenize_text(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        scored_pairs = list(zip(self.chunks, scores))
        # Filter zero/negative scores if positive scores exist
        positive_pairs = [p for p in scored_pairs if p[1] > 0.0]
        if positive_pairs:
            scored_pairs = positive_pairs
        else:
            # Fallback for small corpora where Okapi BM25 yields negative IDF:
            # check lexical overlap with tokens
            matching_pairs = [
                (c, max(s, 0.1))
                for c, s in scored_pairs
                if any(t in tokenize_text(c.text) for t in tokens)
            ]
            scored_pairs = matching_pairs

        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        return scored_pairs[:top_k]


class BM25Store:
    """
    Manager for document-level lexical BM25 indexes.
    Persists and loads index structures under storage/documents/{doc_id}/bm25.json.
    """

    def __init__(self):
        self._indexes: Dict[str, DocumentBM25Index] = {}

    def index_document(self, document_id: str, chunks: List[DocumentChunk]) -> None:
        idx = DocumentBM25Index(document_id, chunks)
        self._indexes[document_id] = idx
        self._save_index(document_id, chunks)
        logger.info(
            "BM25 index built for document",
            extra={"document_id": document_id, "chunk_count": len(chunks)},
        )

    def search(
        self,
        query: str,
        document_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Tuple[DocumentChunk, float]]:
        if document_id:
            idx = self._indexes.get(document_id) or self._load_index(document_id)
            if idx:
                return idx.search(query, top_k=top_k)
            return []

        # Global search across all indexed documents
        all_results: List[Tuple[DocumentChunk, float]] = []
        for idx in self._indexes.values():
            all_results.extend(idx.search(query, top_k=top_k))

        all_results.sort(key=lambda x: x[1], reverse=True)
        return all_results[:top_k]

    def _save_index(self, document_id: str, chunks: List[DocumentChunk]) -> None:
        try:
            doc_dir = settings.documents_dir / document_id
            doc_dir.mkdir(parents=True, exist_ok=True)
            bm25_file = doc_dir / "bm25.json"

            data = [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "page_number": c.page_number,
                    "text": c.text,
                    "bbox": c.bbox,
                    "associated_image_ids": c.associated_image_ids,
                }
                for c in chunks
            ]
            with open(bm25_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save BM25 index to disk", extra={"document_id": document_id, "error": str(e)})

    def _load_index(self, document_id: str) -> Optional[DocumentBM25Index]:
        try:
            bm25_file = settings.documents_dir / document_id / "bm25.json"
            if not bm25_file.exists():
                return None

            with open(bm25_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            chunks = [DocumentChunk(**item) for item in data]
            idx = DocumentBM25Index(document_id, chunks)
            self._indexes[document_id] = idx
            return idx
        except Exception as e:
            logger.error("Failed to load BM25 index from disk", extra={"document_id": document_id, "error": str(e)})
            return None


# Global singleton
bm25_store = BM25Store()
