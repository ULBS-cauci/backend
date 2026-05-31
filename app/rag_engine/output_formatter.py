from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class OutputFormatSpec:
    name: str          # MUST equal output_formats.name seeded in scripts/seed.py
    fence_tag: str     # fenced-code language the LLM emits / frontend renders
    prompt_fragment: str


_INFO_CARDS = OutputFormatSpec(
    name="info_cards", fence_tag="infocard",
    prompt_fragment="""\
INFO CARDS — distil key concepts.
Emit one fenced code block tagged `infocard` per concept (several allowed, interleaved with brief prose).
Inside the fence put a SINGLE JSON object and nothing else:
{"title":"concept name","summary":"1-2 sentence plain explanation","points":["optional supporting point","..."]}
Example:
```infocard
{"title":"Gradient Descent","summary":"An iterative method that nudges parameters down the loss gradient.","points":["Step size set by the learning rate","Can stall in local minima"]}
```
Emit ONLY valid JSON inside the fence.""",
)

_QUIZ = OutputFormatSpec(
    name="quiz", fence_tag="quiz",
    prompt_fragment="""\
QUIZ — test understanding.
Emit one fenced code block tagged `quiz` per question (several allowed). Inside put a SINGLE JSON object.
Choose the "kind" that fits and include exactly its fields:
- true_false: {"kind":"true_false","question":"...","answer":true,"explanation":"..."}
- free_text:  {"kind":"free_text","question":"...","answer":"expected answer","explanation":"..."}
- multiple_choice: {"kind":"multiple_choice","question":"...","options":{"A":"...","B":"...","C":"...","D":"..."},"answer":"B","explanation":"..."}  (answer is one of A,B,C,D)
Example:
```quiz
{"kind":"multiple_choice","question":"Which activation best avoids vanishing gradients?","options":{"A":"Sigmoid","B":"Tanh","C":"ReLU","D":"Softmax"},"answer":"C","explanation":"ReLU keeps a constant gradient of 1 for positive inputs."}
```
Emit ONLY valid JSON inside the fence.""",
)

_DIAGRAM = OutputFormatSpec(
    name="diagram", fence_tag="mermaid",
    prompt_fragment="""\
DIAGRAM — when a visual structure (flow, hierarchy, sequence, or entity schema) helps.
Emit a fenced code block tagged `mermaid` containing ONLY valid Mermaid syntax.

HARD RULES — any violation produces a render error for the student:
1. Edge labels (`-->|label|`) must have NO commas and be ≤ 25 characters.
   WRONG: A -->|id, name, email| B   RIGHT: A --> B (list attributes in the node instead)
2. For entities/schemas with attributes use `classDiagram`, not `flowchart`.
3. Keep the diagram under ~15 nodes for readability.
4. No attribute lists as edge labels — ever.

Use `flowchart TD` for processes/flows, `sequenceDiagram` for step-by-step interactions,
`classDiagram` for data models with attributes.

Example — process:
```mermaid
flowchart TD
  User -->|asks| RAG
  RAG -->|searches| VectorDB
  RAG -->|prompts| LLM
  LLM -->|streams answer| User
```

Example — data model:
```mermaid
classDiagram
  class User {
    +int id
    +string email
    +string role
  }
  class Course {
    +int id
    +string title
  }
  User --> Course : enrolls in
```""",
)

OUTPUT_FORMAT_SPECS: Dict[str, OutputFormatSpec] = {
    s.name: s for s in (_INFO_CARDS, _QUIZ, _DIAGRAM)
}

_BASE = (
    "You may enrich your answer with structured blocks in addition to normal markdown prose. "
    "When you use a block, follow its schema EXACTLY and emit it as a fenced code block with the "
    "given language tag. You may interleave multiple blocks with prose. Use a block only when it "
    "genuinely helps the student."
)
_AUTO = (
    "Choose whichever of the following block formats best fit the question and the retrieved "
    "context. Use plain prose when none apply."
)


def build_output_format_prompt(format_names: List[str], *, auto: bool = False) -> str:
    """Compose the SYSTEM instruction for the requested format(s).

    Single requested format today → one-element list. Combinations / AUTO (future) →
    multi-element list with auto=True. Returns "" when nothing structured is requested.
    """
    fragments = [
        OUTPUT_FORMAT_SPECS[n].prompt_fragment
        for n in format_names
        if n in OUTPUT_FORMAT_SPECS
    ]
    if not fragments:
        return ""
    return (_AUTO if auto else _BASE) + "\n\n" + "\n\n".join(fragments)
