import uuid
from pydantic import BaseModel
from typing import Dict, Any, List


class SparseVectorSchema(BaseModel):
    """BM25 sparse vector as parallel index/value lists (mirrors qdrant_client.models.SparseVector)."""

    indices: List[int]
    values: List[float]


class DocumentChunk(BaseModel):
    id: uuid.UUID
    text: str
    metadata: Dict[str, Any]


class SearchResult(BaseModel):
    chunk: DocumentChunk
    score: float  # Relevance/ranking score; not guaranteed to be normalized and may vary by scoring method (e.g. similarity, BM25, RRF, reranker score)
