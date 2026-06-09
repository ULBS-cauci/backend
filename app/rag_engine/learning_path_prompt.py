"""Prompt builders for course-wide learning-path synthesis.

A learning path is a standalone synthesis artifact (not a per-message output format),
so it has its own system prompt and a strict whole-document JSON contract — it is
deliberately NOT part of output_formatter.OUTPUT_FORMAT_SPECS.
"""
from typing import List, Optional
import uuid

from app.schemas.llm_schemas import ChatMessage, MessageRole


# Synthesis system prompt. Reuses the ONLY-from-materials guardrail of the tutor prompt:
# every module must be grounded in the surveyed excerpts; no outside knowledge.
LEARNING_PATH_SYSTEM_PROMPT = (
    "You are a university curriculum designer for the ULBS AI Tutor platform. "
    "Using ONLY the course material excerpts provided below, design a structured, "
    "ordered learning path that takes a student from foundational concepts to advanced "
    "ones. Each module MUST be grounded in the provided materials — never introduce "
    "topics, facts, or modules that are not supported by the excerpts. "
    "Order modules by prerequisite dependency and increasing difficulty. "
    "Write all human-readable text (title, module titles, objectives, summaries) in the "
    "dominant language of the materials. "
    "Each material excerpt is wrapped in a <material id=\"...\" file=\"...\"> block; cite "
    "the materials a module is based on by putting their ids in that module's "
    "\"material_ids\" array (copy the id values verbatim). "
    "Respond with ONLY a single JSON object and NOTHING else (no prose, no code fence). "
    "The JSON object MUST have this exact shape:\n"
    "{\n"
    '  "title": "<short title for the whole path>",\n'
    '  "modules": [\n'
    "    {\n"
    '      "id": "m1",\n'
    '      "title": "<module title>",\n'
    '      "objectives": ["<learning objective>", "..."],\n'
    '      "summary": "<1-2 sentence summary of what this module covers>",\n'
    '      "material_ids": ["<material id>", "..."]\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Use sequential ids m1, m2, m3, ... for the modules. Produce between 4 and 10 modules."
)


def _sanitize_attr(s: str) -> str:
    """Escape a string for safe embedding inside an XML attribute in the prompt."""
    s = s.replace("\r", "").replace("\n", "")
    return (
        s.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_synthesis_messages(material_blocks: List[str]) -> List[ChatMessage]:
    """Build the synthesis messages from per-material <material> blocks."""
    survey = "\n\n".join(material_blocks)
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=LEARNING_PATH_SYSTEM_PROMPT),
        ChatMessage(
            role=MessageRole.USER,
            content=(
                "Here are the surveyed course materials. Design the learning path from "
                "them:\n\n" + survey
            ),
        ),
    ]


def build_material_block(material_id: uuid.UUID, file_name: str, body: str) -> str:
    """Wrap one material's surveyed content in an id-tagged <material> block."""
    return (
        f'<material id="{material_id}" file="{_sanitize_attr(file_name)}">\n'
        f"{body}\n"
        f"</material>"
    )


def parse_learning_path(raw: str) -> Optional[dict]:
    """Defensively extract the JSON object from the LLM output.

    Mirrors the raw_decode pattern in ChatService.grade_free_text_answer.
    Returns None if no valid JSON object could be parsed.
    """
    import json

    idx = raw.find("{")
    if idx == -1:
        return None
    try:
        decoded, _ = json.JSONDecoder().raw_decode(raw, idx)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None
