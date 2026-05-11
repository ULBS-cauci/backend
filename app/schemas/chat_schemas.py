from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=5,
        description="The student's question to be answered by the LLM.",
    )

class ChatRequest(BaseModel):
    message: str
    collection_name: str = "university_library"
