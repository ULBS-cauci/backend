from typing import AsyncIterator

from app.data_access.interfaces.llm import LLMInterface
from app.schemas.llm_schemas import ChatMessage, MessageRole
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface

TUTOR_SYSTEM_PROMPT = (
    "You are a university tutor for the AI Tutor platform. "
    "Help students understand concepts clearly and concisely. "
    "If you're not sure about something, say so."
)

class ChatService:
    def __init__(
        self, 
        vector_db: VectorDBInterface, 
        embedding_client: EmbeddingInterface,
        llm_client: LLMInterface
    ):
        self.vector_db = vector_db
        self.embedding_client = embedding_client
        self.llm_client = llm_client

    async def ask_stream(self, query: str) -> AsyncIterator[str]:
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=TUTOR_SYSTEM_PROMPT),
            ChatMessage(role=MessageRole.USER, content=query),
        ]
        async for chunk in self.llm_client.stream(messages):
            yield chunk


    async def _get_context(self, question: str, collection_name: str) -> str:
        """Private method to retrieve relevant context from the vector database based on the question."""
        query_vector = await self.embedding_client.embed_text(question)
        search_results = await self.vector_db.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3
        )

        if not search_results:
            return ""
        
        return "\n---\n".join([res.chunk.text for res in search_results])
