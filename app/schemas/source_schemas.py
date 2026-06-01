from typing import List, Literal
import uuid
from pydantic import BaseModel


class SourceReference(BaseModel):
    material_id: uuid.UUID
    file_name: str
    download_url: str


class SourcesEvent(BaseModel):
    type: Literal["sources"] = "sources"
    sources: List[SourceReference]
