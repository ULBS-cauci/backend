from typing import List

from app.schemas.llm_schemas import ChatMessage, MessageRole

TITLE_SYSTEM_PROMPT = (
    "You generate a short, descriptive title for a conversation from the student's "
    "first question. Rules:\n"
    "- Use a 'Topic: aspect' form when the question targets a specific aspect of a "
    "topic (definition, example, difference, usage); otherwise use a plain topic phrase.\n"
    "- Start with a capital letter.\n"
    "- Write the title in the same language as the question.\n"
    "- Keep it concise (at most ~6 words). No final punctuation, no quotes.\n"
    "- Output only the title, nothing else.\n\n"
    "Examples:\n"
    "Question: ce inseamna arbori binari\nTitle: Arbori binari: Definiție\n"
    "Question: cum sortez o listă în python\nTitle: Sortare liste: Python\n"
    "Question: care e diferența dintre stivă și coadă\nTitle: Stivă vs coadă: Diferențe"
)


def build_title_messages(query: str) -> List[ChatMessage]:
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=TITLE_SYSTEM_PROMPT),
        ChatMessage(role=MessageRole.USER, content=f"Question: {query}\nTitle:"),
    ]
