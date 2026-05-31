import uuid
from pydantic import BaseModel


class SourceReference(BaseModel):
    material_id: uuid.UUID
    file_name: str
    download_url: str


class SourcesEvent:
    def __init__(self, sources: list[SourceReference]) -> None:
        self.sources = sources
