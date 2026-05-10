from typing import AsyncIterator

from app.data_access.interfaces.llm import LLMInterface
from app.schemas.llm_schemas import ChatMessage, MessageRole

TUTOR_SYSTEM_PROMPT = (
    "You are a university tutor for the AI Tutor platform. "
    "Help students understand concepts clearly and concisely. "
    "If you're not sure about something, say so."
)


class ChatService:
    def __init__(self, llm: LLMInterface):
        self._llm = llm

    async def ask_stream(self, query: str) -> AsyncIterator[str]:
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=TUTOR_SYSTEM_PROMPT),
            ChatMessage(role=MessageRole.USER, content=query),
        ]
        async for chunk in self._llm.stream(messages):
            yield chunk
