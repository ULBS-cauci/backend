import re
from typing import List

from app.schemas.chat_schemas import Message

# ---------------------------------------------------------------------------
# Pre-compiled signal patterns — English + Romanian
# ---------------------------------------------------------------------------

# Strong: query starts with a subject pronoun that likely refers to prior context
_SUBJECT_PRONOUN_START = re.compile(
    r"^(it|its|they|them|their|this|that|these|those|he|she|his|her"
    # Romanian subject / demonstrative pronouns
    r"|el|ea|ei|ele|asta|ăsta|ăia|alea|acesta|aceasta|aceștia|acestea|acela|aceea|aceia|acelea)\b",
    re.IGNORECASE,
)

# Strong: explicit back-references to something said earlier
_BACK_REFERENCE = re.compile(
    r"\b("
    # English
    r"you mentioned|you said|as you|as mentioned|as explained|as described|the above|the previous|from before|like you said|earlier you"
    # Romanian
    r"|ai menționat|ai spus|cum ai zis|cum ai explicat|cum ai descris|cele de mai sus|cel de dinainte|cea de dinainte|după cum ai"
    r")\b",
    re.IGNORECASE,
)

# Strong: bare question word with nothing else meaningful
_BARE_QUESTION_WORD = re.compile(
    r"^("
    # English
    r"why|how|when|where|who|which|what"
    # Romanian
    r"|de ce|cum|când|unde|cine|care|ce"
    r")[?!.\s]*$",
    re.IGNORECASE,
)

# Moderate: continuation discourse markers at the start
_CONTINUATION_START = re.compile(
    r"^("
    # English
    r"also[,\s]|furthermore|moreover|additionally|besides[,\s]|and |but |however|what about|what else|any other|anything else|more about"
    # Romanian
    r"|de asemenea|în plus|dar |totuși|mai mult|ce altceva|ce mai|și |ori "
    r")",
    re.IGNORECASE,
)

# Moderate: definite reference to an unnamed concept
# English: "the <concept>" — Romanian: concept with definite enclitic suffix
_DEFINITE_UNNAMED_CONCEPT = re.compile(
    r"\b("
    # English: "the + concept noun"
    r"the (?:method|algorithm|formula|concept|approach|technique|example|solution|answer|result|output|process|function|equation|idea|reason|difference|similarity|issue|problem|topic|subject|step|rule|theorem|proof|definition)"
    # Romanian: noun with definite enclitic suffix
    r"|metoda|algoritmul|formula|conceptul|abordarea|tehnica|exemplul|soluția|soluţia|răspunsul|rezultatul|procesul|funcția|funcţia|ecuația|ecuaţia|ideea|motivul|diferența|diferenţa|problema|subiectul|pasul|regula|teorema|demonstrația|definiția"
    r")\b",
    re.IGNORECASE,
)

# Counter: query opens with a standalone/topic-introduction phrase
_STANDALONE_OPENER = re.compile(
    r"^("
    # English
    r"explain|define|what is|what are|how does|how do|tell me about|describe|can you explain|please explain|i want to know|what does|give me|show me"
    # Romanian
    r"|explică|definește|ce este|ce sunt|cum funcționează|spune-mi despre|descrie|poți explica|vreau să știu|ce înseamnă|arată-mi|oferă-mi"
    r")\b",
    re.IGNORECASE,
)

# Pronoun anywhere in a short (4-5 word) query
_PRONOUN_IN_SHORT = re.compile(
    r"\b(it|they|this|that|these|those|el|ea|asta|acesta|aceasta|ei|ele)\b",
    re.IGNORECASE,
)

# Stop words excluded from lexical overlap (EN + RO)
_STOP_WORDS = {
    # English
    "the", "and", "for", "are", "was", "but", "not", "you", "this", "that",
    "with", "have", "from", "they", "will", "been", "has", "had", "its",
    "what", "how", "why", "can", "does", "did", "about", "also",
    # Romanian
    "și", "sau", "dar", "că", "cu", "din", "în", "la", "pe", "de", "ce",
    "mai", "nu", "este", "sunt", "era", "fi", "se", "le", "lui", "lor",
}

_MAX_HISTORY_FOR_OVERLAP = 2


def _token_overlap_ratio(query: str, history: List[Message]) -> float:
    """Fraction of query content-words that also appear in the last 2 messages."""
    recent = history[-_MAX_HISTORY_FOR_OVERLAP:]
    recent_tokens = {
        w.lower()
        for m in recent
        for w in re.findall(r"\b[a-zA-ZăâîșțĂÂÎȘȚ]{3,}\b", m.content)
    }
    query_tokens = {
        w.lower()
        for w in re.findall(r"\b[a-zA-ZăâîșțĂÂÎȘȚ]{3,}\b", query)
    } - _STOP_WORDS
    if not query_tokens:
        return 0.0
    return len(query_tokens & recent_tokens) / len(query_tokens)


def is_context_dependent(history: List[Message], query: str) -> bool:
    """
    Returns True if *query* likely depends on *history* and needs LLM condensation.
    Returns False if the query is self-contained and can go straight to retrieval.

    Uses a weighted multi-signal scorer with no LLM calls (~0.1 ms).
    Supports both English and Romanian.
    """
    if not history:
        return False

    q = query.strip()
    words = q.split()
    word_count = len(words)
    score = 0

    # Strong signals (+3)
    if word_count <= 3:
        score += 3
    if _SUBJECT_PRONOUN_START.match(q):
        score += 3
    if _BACK_REFERENCE.search(q):
        score += 3
    if _BARE_QUESTION_WORD.match(q):
        score += 3

    # Moderate signals (+2)
    if _CONTINUATION_START.match(q):
        score += 2
    if _DEFINITE_UNNAMED_CONCEPT.search(q):
        score += 2
    if word_count <= 10 and _PRONOUN_IN_SHORT.search(q):
        score += 2

    # Weak signal (+1)
    if _token_overlap_ratio(q, history) > 0.40:
        score += 1

    # Counter-signals (−2)
    if _STANDALONE_OPENER.match(q):
        score -= 2
    if word_count > 12:
        score -= 2

    return score >= 2
