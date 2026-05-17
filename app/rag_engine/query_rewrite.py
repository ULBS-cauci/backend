from typing import List

from app.schemas.chat_schemas import Message, MessageSender
from app.schemas.llm_schemas import ChatMessage, MessageRole

CONDENSATION_SYSTEM_PROMPT = (
    "Given a conversation history and a follow-up question, rewrite the follow-up as a "
    "fully standalone question that can be understood without the conversation history. "
    "Output only the rewritten question, nothing else."
)


def build_condensation_messages(history: List[Message], follow_up: str) -> List[ChatMessage]:
    history_text = "\n".join(
        f"{'Student' if msg.sender == MessageSender.USER else 'Tutor'}: {msg.content}"
        for msg in history
    )
    user_content = f"Conversation history:\n{history_text}\n\nFollow-up question: {follow_up}"
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=CONDENSATION_SYSTEM_PROMPT),
        ChatMessage(role=MessageRole.USER, content=user_content),
    ]
