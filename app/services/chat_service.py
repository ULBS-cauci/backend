from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import IEmbeddingClient
from app.data_access.interfaces.llm import LLMInterface
from app.schemas.llm_schemas import ChatMessage, MessageRole

class ChatService:
    def __init__(
        self, 
        vector_db: VectorDBInterface, 
        embedding_client: IEmbeddingClient,
        llm_client: LLMInterface
    ):
        self.vector_db = vector_db
        self.embedding_client = embedding_client
        self.llm_client = llm_client

    async def answer_question(self, question: str, collection_name: str) -> str:
        query_vector = await self.embedding_client.embed_text(question)

        search_results = await self.vector_db.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3
        )

        context = "\n---\n".join([res.chunk.text for res in search_results])

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content="You are a helpful assistant for a university library. Use the provided context to answer questions accurately. If the context does not contain the answer, say you don't know. Always base your answer on the context and do not make assumptions."
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=f"Context: {context}\n\nQuestion: {question}"
            )
        ]

        answer = await self.llm_client.generate(messages)
        
        return answer