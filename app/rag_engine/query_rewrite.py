from typing import List

from app.schemas.chat_schemas import Message, MessageSender
from app.schemas.llm_schemas import ChatMessage, MessageRole

CONDENSATION_SYSTEM_PROMPT = (
    "You are a search-query rewriter for a university course assistant.\n"
    "\n"
    "Task: given a conversation history and a follow-up question, produce a SHORT standalone "
    "search query for a vector knowledge base. The query will retrieve course material "
    "chunks — it is NOT an answer.\n"
    "\n"
    "Rules:\n"
    "1. BREVITY — output at most 15 words. Search queries are short.\n"
    "2. PRONOUN RESOLUTION ONLY — replace pronouns and implicit references "
    "(\"it\", \"this\", \"they\", \"the above\", \"that concept\") with the specific "
    "noun from the conversation. That is the ONLY information to take from the history.\n"
    "3. NO ANSWER BLEED — do NOT copy vocabulary, phrases, or details from the Tutor's "
    "previous responses into the query. Tutor turns are shown only to identify what nouns "
    "pronouns refer to.\n"
    "4. PRESERVE INTENT — keep the student's original question intent unchanged.\n"
    "5. If the question already names its subject (no unresolved references), output it unchanged.\n"
    "6. Output ONLY the rewritten question — no prefix, no explanation.\n"
    "7. Respond in the same language as the follow-up question."
)

_TUTOR_MSG_CONDENSATION_LIMIT = 120


def build_condensation_messages(history: List[Message], follow_up: str) -> List[ChatMessage]:
    parts = []
    for msg in history:
        if msg.sender == MessageSender.USER:
            parts.append(f"Student: {msg.content}")
        else:
            text = msg.content
            if len(text) > _TUTOR_MSG_CONDENSATION_LIMIT:
                text = text[:_TUTOR_MSG_CONDENSATION_LIMIT].rsplit(" ", 1)[0] + "…"
            parts.append(f"Tutor: {text}")
    history_text = "\n".join(parts)
    user_content = f"Conversation history:\n{history_text}\n\nFollow-up question: {follow_up}"
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=CONDENSATION_SYSTEM_PROMPT),
        ChatMessage(role=MessageRole.USER, content=user_content),
    ]
