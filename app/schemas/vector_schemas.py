import uuid
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class DocumentChunk(BaseModel):
    id: uuid.UUID
    text: str
    metadata: Dict[str, Any]

class SearchResult(BaseModel):
    chunk: DocumentChunk
    score: float # Standardized score (0.0 to 1.0)