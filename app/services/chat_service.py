import uuid
from typing import AsyncIterator, List, Optional
from sqlmodel import select, desc, asc
from sqlmodel.ext.asyncio.session import AsyncSession
import datetime
import logging

logger = logging.getLogger("uvicorn.error")

from app.data_access.interfaces.llm import LLMInterface
from app.schemas.chat_schemas import Conversation, Message, MessageSender
from app.schemas.llm_schemas import ChatMessage, MessageRole
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface

from fastapi import HTTPException, status

TUTOR_SYSTEM_PROMPT = (
    "You are a university tutor for the AI Tutor platform. "
    "Help students understand concepts clearly and concisely. "
    "If you are not sure about something, say so."
)

class ChatService:
    def __init__(
        self, 
        vector_db: VectorDBInterface, 
        embedding_client: EmbeddingInterface,
        llm_client: LLMInterface,
        db_session: AsyncSession
    ):
        self.vector_db = vector_db
        self.embedding_client = embedding_client
        self.llm_client = llm_client
        self.db_session = db_session
        
        
    async def create_conversation(self, user_id: uuid.UUID) -> Conversation:
        conversation = Conversation(user_id=user_id, title="New Conversation_" + datetime.datetime.now().isoformat())
        self.db_session.add(conversation)
        await self.db_session.flush()
        await self.db_session.refresh(conversation)
        return conversation

    async def get_user_conversations(self, user_id: uuid.UUID) -> List[Conversation]:
        stmt = select(Conversation).where(Conversation.user_id == user_id).order_by(desc(Conversation.updated_at))
        result = await self.db_session.exec(stmt)
        return list(result.all())

    async def get_conversation_for_user(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Conversation]:
        conversation = await self.db_session.get(Conversation, conversation_id)
        if conversation and conversation.user_id == user_id:
            return conversation
        return None

    async def get_conversation_messages(self, conversation_id: uuid.UUID) -> List[Message]:
        stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(asc(Message.created_at))
        result = await self.db_session.exec(stmt)
        return list(result.all())

    async def ask_stream(self, query: str, user_id: uuid.UUID, conversation_id: Optional[uuid.UUID] = None) -> AsyncIterator[str]:
        # 1. Ensure conversation exists
        if not conversation_id:
            title = query[:50] + "..." if len(query) > 50 else query
            conversation = Conversation(user_id=user_id, title=title)
            self.db_session.add(conversation)
            await self.db_session.flush()
            await self.db_session.refresh(conversation)
            conversation_id = conversation.id
        else:
            conversation = await self.get_conversation_for_user(conversation_id, user_id)
            if not conversation:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")
            
            # Update timestamp
            conversation.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            self.db_session.add(conversation)
            await self.db_session.flush()

        # 2. Extract history and build context
        history = await self.get_conversation_messages(conversation_id)
        
        messages = [ChatMessage(role=MessageRole.SYSTEM, content=TUTOR_SYSTEM_PROMPT)]
        for msg in history:
            role = MessageRole.USER if msg.sender == MessageSender.USER else MessageRole.ASSISTANT
            messages.append(ChatMessage(role=role, content=msg.content))
        
        context = await self._get_context(query, collection_name="university_library")
        if context:
            logger.info(f"Retrieved context for question '{query}': {context}")
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content="Here are some relevant documents from the university library that might help you answer the question:"))  
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=context))
        logger.info(f"a trecut de retrieve")
        # Add new query
        messages.append(ChatMessage(role=MessageRole.USER, content=query))
        
        # Save user message to database
        user_message = Message(
            conversation_id=conversation_id,
            sender=MessageSender.USER,
            content=query
        )
        self.db_session.add(user_message)
        await self.db_session.flush()
        # Commit midway to ensure user message is visible even if generation fails or takes long
        await self.db_session.commit()

        # 3. Stream from LLM
        chunks = []
        async for chunk in self.llm_client.stream(messages):
            chunks.append(chunk)
            yield chunk
        full_answer = "".join(chunks)

        # 4. Save AI final response
        ai_message = Message(
            conversation_id=conversation_id,
            sender=MessageSender.AI,
            content=full_answer
        )
        self.db_session.add(ai_message)
        await self.db_session.commit()

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
