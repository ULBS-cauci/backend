import uuid
from typing import AsyncIterator, List, Optional
from sqlmodel import select, desc, asc
from sqlmodel.ext.asyncio.session import AsyncSession
import datetime

from app.data_access.interfaces.llm import LLMInterface
from app.schemas.chat_schemas import ChatSession, Message, MessageSender
from app.schemas.llm_schemas import ChatMessage, MessageRole

TUTOR_SYSTEM_PROMPT = (
    "You are a university tutor for the AI Tutor platform. "
    "Help students understand concepts clearly and concisely. "
    "If you are not sure about something, say so."
)

class ChatService:
    def __init__(self, llm: LLMInterface, db: AsyncSession):
        self._llm = llm
        self._db = db

    async def get_user_sessions(self, user_id: uuid.UUID) -> List[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.updated_at))
        result = await self._db.exec(stmt)
        return list(result.all())

    async def get_session_for_user(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Optional[ChatSession]:
        session = await self._db.get(ChatSession, conversation_id)
        if session and session.user_id == user_id:
            return session
        return None

    async def get_session_messages(self, conversation_id: uuid.UUID) -> List[Message]:
        stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(asc(Message.created_at))
        result = await self._db.exec(stmt)
        return list(result.all())

    async def ask_stream(self, query: str, user_id: uuid.UUID, conversation_id: Optional[uuid.UUID] = None) -> AsyncIterator[str]:
        # 1. Ensure conversation exists
        if not conversation_id:
            title = query[:50] + "..." if len(query) > 50 else query
            session = ChatSession(user_id=user_id, title=title)
            self._db.add(session)
            await self._db.flush()
            await self._db.refresh(session)
            conversation_id = session.id
        else:
            session = await self.get_session_for_user(conversation_id, user_id)
            if not session:
                raise ValueError("Conversation not found or unauthorized")
            
            # Update timestamp
            session.updated_at = datetime.datetime.now(datetime.timezone.utc)
            self._db.add(session)
            await self._db.flush()

        # 2. Extract history and build context
        history = await self.get_session_messages(conversation_id)
        
        messages = [ChatMessage(role=MessageRole.SYSTEM, content=TUTOR_SYSTEM_PROMPT)]
        for msg in history:
            role = MessageRole.USER if msg.sender == MessageSender.USER else MessageRole.ASSISTANT
            messages.append(ChatMessage(role=role, content=msg.content))
        
        # Add new query
        messages.append(ChatMessage(role=MessageRole.USER, content=query))
        
        # Save user message to database
        user_message = Message(
            conversation_id=conversation_id,
            sender=MessageSender.USER,
            content=query
        )
        self._db.add(user_message)
        await self._db.flush()
        # Commit midway to ensure user message is visible even if generation fails or takes long
        await self._db.commit()

        # 3. Stream from LLM
        chunks = []
        async for chunk in self._llm.stream(messages):
            chunks.append(chunk)
            yield chunk
        full_answer = "".join(chunks)

        # 4. Save AI final response
        ai_message = Message(
            conversation_id=conversation_id,
            sender=MessageSender.AI,
            content=full_answer
        )
        self._db.add(ai_message)
        await self._db.commit()
