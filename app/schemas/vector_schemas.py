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
    score: float # Standardized score (0.0 to 1.0)    