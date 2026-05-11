import uuid
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class DocumentChunk(BaseModel):
    id: uuid.UUID
    text: str
    metadata: Dict[str, Any]

class SearchResult(BaseModel):
    chunk: DocumentChunk
    score: float # Standardized score (0.0 to 1.0)

class DocumentMetadata(SQLModel, table=True):
    __tablename__ = "document_metadata"
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    qdrant_collection: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)    