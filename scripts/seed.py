"""
Database seeder for the RAG AI Tutor backend.

Usage (from backend/ directory with venv activated):
    python -m scripts.seed                        # mock mode — idempotent, no files needed
    python -m scripts.seed --reset                # truncate all tables then seed
    python -m scripts.seed --dry-run              # preview without DB changes
    python -m scripts.seed --embed                # embed PDFs from scripts/seed_materials/
    python -m scripts.seed --embed path/to/pdfs  # embed PDFs from a custom folder
    python -m scripts.seed --reset --embed        # wipe, then seed + embed
    python -m scripts.seed --embed --dry-run      # preview what embed would do

Modes
─────
  Mock mode (default): creates Material DB records with realistic filenames but no actual
  files in MinIO and no vectors in Qdrant. Fast, no external services required beyond Postgres.

  Embed mode (--embed): reads real PDF files from a folder, runs them through the full
  FileService pipeline (text extraction → chunking → dense+sparse embedding → Qdrant upsert
  → MinIO upload → Material DB record). Requires Ollama, Qdrant, and MinIO to be running.
  Only 2 randomly chosen professor courses receive materials.

Prerequisites:
    docker-compose up -d                      (Postgres, Qdrant, MinIO)
    uvicorn app.main:app                      (creates DB tables via SQLModel.metadata.create_all)
    pip install -r requirements.txt           (includes fastembed, sentence-transformers, FlagEmbedding)
"""

# ── sys.path fix ─────────────────────────────────────────────────────────────
# Must come before any app.* import so Python can find the app package.
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── stdlib imports ────────────────────────────────────────────────────────────
import argparse
import asyncio
import base64
import hashlib
import logging
import random
import secrets
import uuid
from typing import Any

# ── app imports ───────────────────────────────────────────────────────────────
# Import schema models directly — do NOT import from app.main (triggers lifespan
# side-effects: model downloads, MinIO init, SQLModel.metadata.create_all, etc.)
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.dependencies import _get_async_engine
from app.core.config import MINIO_MATERIALS_BUCKET, QDRANT_MATERIALS_COLLECTION

from app.schemas.admin_schemas import LlmTip, SystemPrompt, TipCategory
from app.schemas.chat_schemas import (
    Attachment,  # noqa: F401 — imported so SQLModel registers the table
    Conversation,
    Message,
    MessageSender,
    SharedLink,
)
from app.schemas.course_schemas import Course
from app.schemas.knowledge_schemas import Material
from app.schemas.user_schemas import User, UserRole, UserSetting

# ── logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")

# Silence noisy third-party loggers that fire on every HTTP request/chunk.
# httpx logs every POST to Ollama's /api/embeddings — one per text chunk.
# fastembed/transformers log model-loading progress we don't need here.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("fastembed").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)

# ── UploadFile shim ───────────────────────────────────────────────────────────


class _SeederUploadFile:
    """
    Minimal shim that satisfies the parts of fastapi.UploadFile used by FileService:
      - .filename  (str)
      - await .read()  (bytes)

    Avoids a direct starlette import whose constructor signature has changed across versions.
    """

    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


# ── password hashing (stdlib PBKDF2 — no passlib/bcrypt required) ────────────


def hash_password(plain: str) -> str:
    """Hash using PBKDF2-HMAC-SHA256 (stdlib only). Format is self-describing."""
    salt: bytes = secrets.token_bytes(16)
    iterations: int = 260_000
    dk: bytes = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}"
        f"${base64.b64encode(salt).decode()}"
        f"${base64.b64encode(dk).decode()}"
    )


# ── seed UUID constants ───────────────────────────────────────────────────────


class SeedIDs:
    """Fixed UUIDs for all seed records — enables idempotency via session.get()."""

    # ── Users ─────────────────────────────────────────────────────────────────
    ADMIN = uuid.UUID("00000000-0000-0000-0000-000000000003")
    PROF = uuid.UUID(
        "123e4567-e89b-12d3-a456-426614174001"
    )  # professor — owns the seeded catalog courses
    STUDENT = uuid.UUID("00000000-0000-0000-0000-000000000001")  # dummy dev user

    # ── Courses ───────────────────────────────────────────────────────────────
    DEV_COURSE = uuid.UUID(
        "00000000-0000-0000-0000-000000000002"
    )  # course held by the dummy dev student
    COURSE_1 = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    COURSE_2 = uuid.UUID("00000000-0000-0000-0000-000000000010")
    COURSE_3 = uuid.UUID("00000000-0000-0000-0000-000000000011")
    COURSE_4 = uuid.UUID("00000000-0000-0000-0000-000000000012")
    COURSE_5 = uuid.UUID("00000000-0000-0000-0000-000000000013")
    COURSE_6 = uuid.UUID("00000000-0000-0000-0000-000000000014")
    COURSE_7 = uuid.UUID("00000000-0000-0000-0000-000000000015")
    COURSE_8 = uuid.UUID("00000000-0000-0000-0000-000000000016")
    COURSE_9 = uuid.UUID("00000000-0000-0000-0000-000000000017")
    COURSE_10 = uuid.UUID("00000000-0000-0000-0000-000000000018")
    COURSE_11 = uuid.UUID("00000000-0000-0000-0000-000000000019")
    COURSE_12 = uuid.UUID("00000000-0000-0000-0000-00000000001a")

    # ── Materials (mock mode — fixed UUIDs for idempotency) ───────────────────
    MAT_1 = uuid.UUID("00000000-0000-0000-0000-000000000020")
    MAT_2 = uuid.UUID("00000000-0000-0000-0000-000000000021")
    MAT_3 = uuid.UUID("00000000-0000-0000-0000-000000000022")
    MAT_4 = uuid.UUID("00000000-0000-0000-0000-000000000023")
    MAT_5 = uuid.UUID("00000000-0000-0000-0000-000000000024")
    MAT_6 = uuid.UUID("00000000-0000-0000-0000-000000000025")
    MAT_7 = uuid.UUID("00000000-0000-0000-0000-000000000026")
    MAT_8 = uuid.UUID("00000000-0000-0000-0000-000000000027")
    MAT_9 = uuid.UUID("00000000-0000-0000-0000-000000000028")
    MAT_10 = uuid.UUID("00000000-0000-0000-0000-000000000029")
    MAT_11 = uuid.UUID("00000000-0000-0000-0000-00000000002a")
    MAT_12 = uuid.UUID("00000000-0000-0000-0000-00000000002b")

    # ── Conversations ─────────────────────────────────────────────────────────
    CONV_1 = uuid.UUID("00000000-0000-0000-0000-000000000030")
    CONV_2 = uuid.UUID("00000000-0000-0000-0000-000000000031")

    # ── Messages (3 per conversation) ─────────────────────────────────────────
    MSG_1_1 = uuid.UUID("00000000-0000-0000-0000-000000000040")
    MSG_1_2 = uuid.UUID("00000000-0000-0000-0000-000000000041")
    MSG_1_3 = uuid.UUID("00000000-0000-0000-0000-000000000042")
    MSG_2_1 = uuid.UUID("00000000-0000-0000-0000-000000000043")
    MSG_2_2 = uuid.UUID("00000000-0000-0000-0000-000000000044")
    MSG_2_3 = uuid.UUID("00000000-0000-0000-0000-000000000045")

    # ── Shared links ──────────────────────────────────────────────────────────
    LINK_1 = uuid.UUID("00000000-0000-0000-0000-000000000050")
    LINK_2 = uuid.UUID("00000000-0000-0000-0000-000000000051")

    # ── System prompts ────────────────────────────────────────────────────────
    SPROMPT_1 = uuid.UUID("00000000-0000-0000-0000-000000000060")
    SPROMPT_2 = uuid.UUID("00000000-0000-0000-0000-000000000061")
    SPROMPT_3 = uuid.UUID("00000000-0000-0000-0000-000000000062")
    SPROMPT_4 = uuid.UUID("00000000-0000-0000-0000-000000000063")
    SPROMPT_5 = uuid.UUID("00000000-0000-0000-0000-000000000064")
    SPROMPT_6 = uuid.UUID("00000000-0000-0000-0000-000000000065")
    SPROMPT_7 = uuid.UUID("00000000-0000-0000-0000-000000000066")

    # ── LLM tips ──────────────────────────────────────────────────────────────
    TIP_1 = uuid.UUID("00000000-0000-0000-0000-000000000070")
    TIP_2 = uuid.UUID("00000000-0000-0000-0000-000000000071")
    TIP_3 = uuid.UUID("00000000-0000-0000-0000-000000000072")
    TIP_4 = uuid.UUID("00000000-0000-0000-0000-000000000073")
    TIP_5 = uuid.UUID("00000000-0000-0000-0000-000000000074")

    # ── Tip categories ────────────────────────────────────────────────────────
    CAT_1 = uuid.UUID("00000000-0000-0000-0000-000000000080")  # Prompting Strategy
    CAT_2 = uuid.UUID("00000000-0000-0000-0000-000000000081")  # Learning Technique
    CAT_3 = uuid.UUID("00000000-0000-0000-0000-000000000082")  # Context Usage


# ── reset: reverse FK order ───────────────────────────────────────────────────

_TRUNCATE_ORDER: list[str] = [
    "user_settings",  # references users + system_prompts; no children
    "attachments",
    "shared_links",
    "messages",
    "output_formats",  # referenced by messages.output_format_id
    "conversations",
    "materials",
    "system_prompts",
    "llm_tips",
    "tip_categories",  # referenced by llm_tips.category_id
    "courses",
    "users",
]


async def do_reset(session: AsyncSession, dry_run: bool) -> None:
    """Truncate all tables in reverse FK order so constraints are never violated."""
    logger.warning("--reset: truncating all tables...")
    for table in _TRUNCATE_ORDER:
        if dry_run:
            logger.info("DRY-RUN  TRUNCATE %s", table)
            continue
        await session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        logger.info("TRUNCATED  %s", table)
    if not dry_run:
        await session.commit()
        logger.info("Reset complete.")


# ── generic idempotency helper ────────────────────────────────────────────────


async def _upsert(
    session: AsyncSession,
    model_class: type,
    record_id: uuid.UUID,
    instance: Any,
    dry_run: bool,
    label: str,
) -> Any:
    """
    Insert `instance` if no row with `record_id` exists yet, otherwise return existing.
    In dry-run mode nothing is written; the unsaved instance is returned so downstream
    seeders can still reference its fixed UUID safely.
    """
    existing = await session.get(model_class, record_id)
    if existing is not None:
        logger.info("SKIP    %-16s id=%s", label, record_id)
        return existing
    if dry_run:
        logger.info("DRY-RUN %-16s id=%s  — would insert", label, record_id)
        return instance
    session.add(instance)
    await session.flush()
    await session.refresh(instance)
    logger.info("INSERT  %-16s id=%s", label, record_id)
    return instance


# ── seed data ─────────────────────────────────────────────────────────────────

SEED_USERS: list[dict[str, Any]] = [
    {
        "id": SeedIDs.ADMIN,
        "email": "admin@aitutor.edu",
        "first_name": "Alice",
        "last_name": "Admin",
        "role": UserRole.ADMIN,
        "password": "admin1234",
    },
    {
        "id": SeedIDs.PROF,
        # Professor who owns the seeded catalog courses (see SEED_COURSES)
        "email": "prof.smith@aitutor.edu",
        "first_name": "John",
        "last_name": "Smith",
        "role": UserRole.PROFESSOR,
        "password": "prof1234",
    },
    {
        "id": SeedIDs.STUDENT,
        # UUID and email must match get_current_user() in dependencies.py
        "email": "dummy@student.com",
        "first_name": "Dummy",
        "last_name": "Student",
        "role": UserRole.STUDENT,
        "password": "student1234",
    },
]

SEED_COURSES: list[dict[str, Any]] = [
    # ── Course held by the dummy student (gives the dev user data for the "Show mine" filter) ───
    {
        "id": SeedIDs.DEV_COURSE,
        "title": "Dev Course",
        "description": "Sample course owned by the dummy dev student.",
        "held_by": SeedIDs.STUDENT,  # the dummy dev user injected by get_current_user()
    },
    # ── Professor courses ─────────────────────────────────────────────────────
    {
        "id": SeedIDs.COURSE_1,
        "title": "Introduction to Artificial Intelligence",
        "description": (
            "Foundations of AI: search, knowledge representation, "
            "machine learning, and neural networks."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_2,
        "title": "Data Structures and Algorithms",
        "description": (
            "Complexity analysis, sorting, trees, graphs, and dynamic programming."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_3,
        "title": "Machine Learning Fundamentals",
        "description": (
            "Supervised and unsupervised learning, model evaluation, "
            "regularization, and ensemble methods."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_4,
        "title": "Computer Networks",
        "description": (
            "OSI model, TCP/IP stack, routing protocols, congestion control, "
            "and network security basics."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_5,
        "title": "Operating Systems",
        "description": (
            "Process management, scheduling algorithms, memory management, "
            "file systems, and concurrency."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_6,
        "title": "Database Systems",
        "description": (
            "Relational model, SQL, normalization, indexing, transactions, "
            "and introduction to NoSQL."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_7,
        "title": "Software Engineering",
        "description": (
            "Requirements engineering, agile methodologies, design patterns, "
            "testing strategies, and DevOps."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_8,
        "title": "Computer Architecture",
        "description": (
            "Digital logic, CPU design, instruction set architecture, "
            "pipelining, memory hierarchy, and I/O."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_9,
        "title": "Discrete Mathematics",
        "description": (
            "Logic, sets, relations, functions, combinatorics, graph theory, "
            "and proof techniques."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_10,
        "title": "Linear Algebra for Computer Science",
        "description": (
            "Vectors, matrices, linear transformations, eigenvalues, "
            "and applications in graphics and ML."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_11,
        "title": "Web Development",
        "description": (
            "HTML/CSS, JavaScript, REST APIs, frontend frameworks, "
            "server-side rendering, and deployment."
        ),
        "held_by": SeedIDs.PROF,
    },
    {
        "id": SeedIDs.COURSE_12,
        "title": "Cybersecurity Fundamentals",
        "description": (
            "Threat modeling, cryptography, network security, web vulnerabilities, "
            "and secure coding practices."
        ),
        "held_by": SeedIDs.PROF,
    },
]

# ── Mock material titles ──────────────────────────────────────────────────────
# Each tuple: (fixed UUID, filename).
# Course assignment is determined at runtime by _pick_two_courses().

SEED_MATERIAL_TITLES: list[tuple[uuid.UUID, str]] = [
    (SeedIDs.MAT_1, "lecture01_intro_to_ai.pdf"),
    (SeedIDs.MAT_2, "lecture02_search_algorithms.pdf"),
    (SeedIDs.MAT_3, "lecture03_knowledge_representation.pdf"),
    (SeedIDs.MAT_4, "lecture04_machine_learning_basics.pdf"),
    (SeedIDs.MAT_5, "lecture05_neural_networks.pdf"),
    (SeedIDs.MAT_6, "sorting_and_searching_notes.pdf"),
    (SeedIDs.MAT_7, "graph_theory_and_traversals.pdf"),
    (SeedIDs.MAT_8, "dynamic_programming_techniques.pdf"),
    (SeedIDs.MAT_9, "os_process_scheduling.pdf"),
    (SeedIDs.MAT_10, "database_normalization_and_sql.pdf"),
    (SeedIDs.MAT_11, "network_protocols_overview.pdf"),
    (SeedIDs.MAT_12, "cybersecurity_fundamentals.pdf"),
]

SEED_CONVERSATIONS: list[dict[str, Any]] = [
    {
        "id": SeedIDs.CONV_1,
        "user_id": SeedIDs.STUDENT,
        "course_id": SeedIDs.COURSE_1,
        "title": "Explain backpropagation to me",
    },
    {
        "id": SeedIDs.CONV_2,
        "user_id": SeedIDs.STUDENT,
        "course_id": SeedIDs.COURSE_2,
        "title": "How does quicksort work?",
    },
]

SEED_MESSAGES: list[dict[str, Any]] = [
    # ── Conversation 1: AI course ─────────────────────────────────────────────
    {
        "id": SeedIDs.MSG_1_1,
        "conversation_id": SeedIDs.CONV_1,
        "sender": MessageSender.USER,
        "content": "Can you explain what backpropagation is in neural networks?",
        "output_format_id": None,
    },
    {
        "id": SeedIDs.MSG_1_2,
        "conversation_id": SeedIDs.CONV_1,
        "sender": MessageSender.AI,
        "content": (
            "Backpropagation is the algorithm used to train neural networks. "
            "It computes the gradient of the loss function with respect to each weight "
            "using the chain rule of calculus, then updates weights in the direction "
            "that reduces the loss."
        ),
        "output_format_id": None,
    },
    {
        "id": SeedIDs.MSG_1_3,
        "conversation_id": SeedIDs.CONV_1,
        "sender": MessageSender.USER,
        "content": "What is the vanishing gradient problem?",
        "output_format_id": None,
    },
    # ── Conversation 2: DSA course ────────────────────────────────────────────
    {
        "id": SeedIDs.MSG_2_1,
        "conversation_id": SeedIDs.CONV_2,
        "sender": MessageSender.USER,
        "content": "How does quicksort partition the array?",
        "output_format_id": None,
    },
    {
        "id": SeedIDs.MSG_2_2,
        "conversation_id": SeedIDs.CONV_2,
        "sender": MessageSender.AI,
        "content": (
            "Quicksort selects a pivot and rearranges the array so that all elements "
            "less than the pivot come before it and all greater elements come after. "
            "It then recursively sorts the two sub-arrays. Average case is O(n log n)."
        ),
        "output_format_id": None,
    },
    {
        "id": SeedIDs.MSG_2_3,
        "conversation_id": SeedIDs.CONV_2,
        "sender": MessageSender.USER,
        "content": "What is the worst case for quicksort and how can we avoid it?",
        "output_format_id": None,
    },
]

SEED_SHARED_LINKS: list[dict[str, Any]] = [
    {
        "id": SeedIDs.LINK_1,
        "conversation_id": SeedIDs.CONV_1,
        "token": "seed-conv1-aitutor-static-token-abc123",  # ≤ 64 chars
        "expires_at": None,
    },
    {
        "id": SeedIDs.LINK_2,
        "conversation_id": SeedIDs.CONV_2,
        "token": "seed-conv2-aitutor-static-token-xyz789",
        "expires_at": None,
    },
]

SEED_SYSTEM_PROMPTS: list[dict[str, Any]] = [
    {
        "id": SeedIDs.SPROMPT_1,
        "title": "Default Tutor Prompt",
        "content": (
            "You are a university-level AI tutor. Your goal is to help students understand "
            "course material clearly. Always explain concepts step by step. If you are unsure, "
            "say so explicitly. Cite specific parts of the uploaded course materials when relevant."
        ),
        "author_id": SeedIDs.ADMIN,
    },
    {
        "id": SeedIDs.SPROMPT_2,
        "title": "Socratic Tutor Prompt",
        "content": (
            "You are a Socratic tutor. Instead of giving direct answers, guide the student to "
            "discover the answer themselves by asking targeted questions. Encourage critical thinking. "
            "Only provide direct answers when the student is genuinely stuck after several attempts."
        ),
        "author_id": SeedIDs.ADMIN,
    },
    {
        "id": SeedIDs.SPROMPT_3,
        "title": "Explain Simply",
        "content": (
            "Explain concepts in plain, everyday language as if teaching a motivated beginner. "
            "Avoid jargon; when a technical term is unavoidable, define it immediately. Use at "
            "least one concrete real-world analogy per concept and keep sentences short. Base "
            "every explanation on the provided course materials."
        ),
        "author_id": SeedIDs.ADMIN,
    },
    {
        "id": SeedIDs.SPROMPT_4,
        "title": "Step-by-Step Solver",
        "content": (
            "Break every answer into clearly numbered steps. Show your reasoning for each step "
            "before moving on, and state which concept or formula justifies it. Do not skip "
            "intermediate steps, even obvious ones. End with a one-line summary of the result. "
            "Stay grounded in the course materials."
        ),
        "author_id": SeedIDs.ADMIN,
    },
    {
        "id": SeedIDs.SPROMPT_5,
        "title": "Concise Mode",
        "content": (
            "Be brief and direct. Lead with the answer in one or two sentences, then add at most "
            "a few bullet points of supporting detail. No preamble, no repetition. If the course "
            "materials do not cover the question, say so immediately."
        ),
        "author_id": SeedIDs.ADMIN,
    },
    {
        "id": SeedIDs.SPROMPT_6,
        "title": "Deep Dive",
        "content": (
            "Give a rigorous, detailed explanation. Include formal definitions, why the concept "
            "matters, how it connects to related topics in the course, common pitfalls, and edge "
            "cases. Use examples from the course materials wherever possible."
        ),
        "author_id": SeedIDs.ADMIN,
    },
]

SEED_TIP_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": SeedIDs.CAT_1,
        "name": "Prompting Strategy",
    },
    {
        "id": SeedIDs.CAT_2,
        "name": "Learning Technique",
    },
    {
        "id": SeedIDs.CAT_3,
        "name": "Context Usage",
    },
]

SEED_LLM_TIPS: list[dict[str, Any]] = [
    {
        "id": SeedIDs.TIP_1,
        "title": "Be Specific in Your Questions",
        "description": (
            "The more context you give the AI about what you already know and where you are "
            "confused, the better the answer will be."
        ),
        "example_prompt": (
            "I understand that backpropagation uses the chain rule, but I don't understand how "
            "the gradient flows backwards through a ReLU. Can you explain just that step?"
        ),
        "category_id": SeedIDs.CAT_1,  # Prompting Strategy
    },
    {
        "id": SeedIDs.TIP_2,
        "title": "Ask for Step-by-Step Explanations",
        "description": (
            "For complex algorithms or proofs, ask the AI to walk through the logic one step "
            "at a time rather than giving a high-level summary."
        ),
        "example_prompt": (
            "Can you walk me through quicksort step by step on the array [3, 1, 4, 1, 5, 9]?"
        ),
        "category_id": SeedIDs.CAT_1,  # Prompting Strategy
    },
    {
        "id": SeedIDs.TIP_3,
        "title": "Request Multiple Analogies",
        "description": (
            "If the first explanation does not click, ask the AI for an analogy or a different "
            "way to think about the concept."
        ),
        "example_prompt": (
            "Can you explain the attention mechanism in transformers using a real-world analogy?"
        ),
        "category_id": SeedIDs.CAT_2,  # Learning Technique
    },
    {
        "id": SeedIDs.TIP_4,
        "title": "Test Your Understanding",
        "description": (
            "After getting an explanation, ask the AI to give you a short quiz or a practice "
            "problem to verify you understood the concept."
        ),
        "example_prompt": (
            "Now that you have explained dynamic programming, give me a practice problem "
            "at medium difficulty."
        ),
        "category_id": SeedIDs.CAT_2,  # Learning Technique
    },
    {
        "id": SeedIDs.TIP_5,
        "title": "Reference the Course Material",
        "description": (
            "Mention specific lecture numbers or topics from your course when asking questions "
            "to help the AI retrieve the most relevant context."
        ),
        "example_prompt": (
            "Based on the Lecture 3 material on graph traversal, can you explain why BFS is "
            "preferred over DFS for shortest-path problems?"
        ),
        "category_id": SeedIDs.CAT_3,  # Context Usage
    },
]


# ── helpers ───────────────────────────────────────────────────────────────────


def _pick_two_courses(all_courses: list[Course]) -> tuple[Course, Course]:
    """
    Select exactly 2 distinct professor-held courses at random.
    The Dev Course is excluded because it is held by the dummy student and is
    not intended to receive real academic materials.
    Falls back gracefully if fewer than 2 professor courses exist.
    """
    eligible = [c for c in all_courses if c.id != SeedIDs.DEV_COURSE]
    if len(eligible) < 2:
        raise RuntimeError(
            f"Need at least 2 professor courses to assign materials, got {len(eligible)}."
        )
    course_a, course_b = random.sample(eligible, 2)
    return course_a, course_b


# ── seeder functions ──────────────────────────────────────────────────────────


async def seed_users(session: AsyncSession, dry_run: bool) -> list[User]:
    results: list[User] = []
    for data in SEED_USERS:
        user_data = dict(data)
        user_data["hashed_password"] = hash_password(user_data.pop("password"))
        instance = User(**user_data)
        saved = await _upsert(session, User, data["id"], instance, dry_run, "User")
        results.append(saved)
    return results


async def seed_courses(
    session: AsyncSession, dry_run: bool, _users: list[User]
) -> list[Course]:
    results: list[Course] = []
    for data in SEED_COURSES:
        instance = Course(**data)
        saved = await _upsert(session, Course, data["id"], instance, dry_run, "Course")
        results.append(saved)
    return results


# ── material seeding: mock mode ───────────────────────────────────────────────


async def seed_materials_mock(
    session: AsyncSession,
    dry_run: bool,
    courses: list[Course],
) -> list[Material]:
    """
    Create Material DB records with realistic filenames but no actual file data.
    Assigns materials across exactly 2 randomly chosen professor courses:
      - Even-indexed titles  → courses[0]
      - Odd-indexed titles   → courses[1]
    Idempotent: fixed UUIDs mean existing records are skipped on re-run.
    """
    course_a, course_b = _pick_two_courses(courses)
    logger.info(
        "Mock materials: assigning to courses '%s' and '%s'",
        course_a.title,
        course_b.title,
    )

    results: list[Material] = []
    for i, (mat_id, filename) in enumerate(SEED_MATERIAL_TITLES):
        assigned_course = course_a if i % 2 == 0 else course_b
        instance = Material(
            id=mat_id,
            course_id=assigned_course.id,
            file_name=filename,
            file_type="pdf",
            vector_namespace=QDRANT_MATERIALS_COLLECTION,
            uploaded_by=SeedIDs.PROF,
            object_storage_key=None,  # DB record only
        )
        saved = await _upsert(session, Material, mat_id, instance, dry_run, "Material")
        results.append(saved)
    return results


# ── material seeding: embed mode ──────────────────────────────────────────────


async def seed_materials_embed(
    session: AsyncSession,
    embed_folder: Path,
    courses: list[Course],
    dry_run: bool,
) -> list[Any]:
    """
    Read every PDF from `embed_folder`, run it through the full FileService pipeline
    (text extraction → chunking → dense+sparse embedding → Qdrant upsert → MinIO upload),
    and write a Material DB record. Exactly 2 courses receive materials.

    Material UUIDs are generated by FileService (not fixed), so embed mode is NOT
    idempotent by default — use --reset before re-embedding.
    """
    pdf_files = sorted(embed_folder.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in %s — skipping embed.", embed_folder)
        return []

    course_a, course_b = _pick_two_courses(courses)
    logger.info(
        "Embed mode: %d PDF(s) found. Assigning to courses '%s' and '%s'.",
        len(pdf_files),
        course_a.title,
        course_b.title,
    )

    if dry_run:
        for i, pdf in enumerate(pdf_files):
            target = course_a if i % 2 == 0 else course_b
            logger.info("DRY-RUN  embed %-40s → course '%s'", pdf.name, target.title)
        return []

    # ── Wire up FileService using the cached private factories ────────────────
    # These are the same @lru_cache singletons the running app uses.
    from concurrent.futures import ThreadPoolExecutor

    from app.api.dependencies import (
        _get_bgem3_sparse_encoder,
        _get_docling_converter,
        _get_markdown_splitter,
        _get_minio_client,
        make_ingestion_embedding,
        make_ingestion_object_storage,
        make_ingestion_vector_db,
    )
    from app.services.file_service import FileService

    logger.info(
        "Initialising sparse encoder (BGE-M3, ~570 MB download on first use)..."
    )
    await asyncio.to_thread(
        _get_bgem3_sparse_encoder
    )  # pre-warm lru_cache; first call downloads ~570 MB

    executor = ThreadPoolExecutor(max_workers=2)
    minio = _get_minio_client()
    await minio.connect()
    try:
        await minio.create_bucket(MINIO_MATERIALS_BUCKET)

        file_service = FileService(
            object_storage=minio,
            db=session,
            executor=executor,
            make_ingestion_object_storage=make_ingestion_object_storage,
            make_ingestion_embedding=make_ingestion_embedding,
            make_ingestion_vector_db=make_ingestion_vector_db,
            get_ingestion_sparse_encoder=_get_bgem3_sparse_encoder,
            get_ingestion_document_converter=_get_docling_converter,
            get_ingestion_text_splitter=_get_markdown_splitter,
        )

        results = []
        for i, pdf_path in enumerate(pdf_files):
            target_course = course_a if i % 2 == 0 else course_b
            content = pdf_path.read_bytes()
            upload_file = _SeederUploadFile(pdf_path.name, content)

            logger.info(
                "EMBED    %-40s → course '%s'", pdf_path.name, target_course.title
            )
            try:
                # FileService does its own session.commit() per file — intentional.
                material = await file_service.upload_and_index(
                    upload_file,  # type: ignore[arg-type]  — satisfies the duck-type contract
                    course_id=target_course.id,
                    user_id=SeedIDs.PROF,
                )
                logger.info("EMBEDDED %-40s id=%s", pdf_path.name, material.id)
                results.append(material)
            except Exception as exc:
                logger.error("FAILED   %-40s — %s", pdf_path.name, exc)

        return results
    finally:
        await minio.close()
        executor.shutdown(wait=True)


# ── material dispatcher ───────────────────────────────────────────────────────


async def seed_materials(
    session: AsyncSession,
    dry_run: bool,
    courses: list[Course],
    embed_folder: Path | None,
) -> list[Any]:
    """Route to mock or embed mode depending on whether embed_folder is set."""
    if embed_folder is not None:
        return await seed_materials_embed(session, embed_folder, courses, dry_run)
    return await seed_materials_mock(session, dry_run, courses)


# ── remaining seeders ─────────────────────────────────────────────────────────


async def seed_conversations(
    session: AsyncSession,
    dry_run: bool,
    _users: list[User],
    _courses: list[Course],
) -> list[Conversation]:
    results: list[Conversation] = []
    for data in SEED_CONVERSATIONS:
        instance = Conversation(**data)
        saved = await _upsert(
            session, Conversation, data["id"], instance, dry_run, "Conversation"
        )
        results.append(saved)
    return results


async def seed_messages(
    session: AsyncSession, dry_run: bool, _convs: list[Conversation]
) -> list[Message]:
    results: list[Message] = []
    for data in SEED_MESSAGES:
        instance = Message(**data)
        saved = await _upsert(
            session, Message, data["id"], instance, dry_run, "Message"
        )
        results.append(saved)
    return results


async def seed_shared_links(
    session: AsyncSession, dry_run: bool, _convs: list[Conversation]
) -> list[SharedLink]:
    results: list[SharedLink] = []
    for data in SEED_SHARED_LINKS:
        instance = SharedLink(**data)
        saved = await _upsert(
            session, SharedLink, data["id"], instance, dry_run, "SharedLink"
        )
        results.append(saved)
    return results


async def seed_system_prompts(
    session: AsyncSession, dry_run: bool, _users: list[User]
) -> list[SystemPrompt]:
    results: list[SystemPrompt] = []
    for data in SEED_SYSTEM_PROMPTS:
        instance = SystemPrompt(**data)
        saved = await _upsert(
            session, SystemPrompt, data["id"], instance, dry_run, "SystemPrompt"
        )
        results.append(saved)
    return results


async def seed_tip_categories(
    session: AsyncSession, dry_run: bool
) -> list[TipCategory]:
    results: list[TipCategory] = []
    for data in SEED_TIP_CATEGORIES:
        instance = TipCategory(**data)
        saved = await _upsert(
            session, TipCategory, data["id"], instance, dry_run, "TipCategory"
        )
        results.append(saved)
    return results


async def seed_llm_tips(session: AsyncSession, dry_run: bool) -> list[LlmTip]:
    results: list[LlmTip] = []
    for data in SEED_LLM_TIPS:
        instance = LlmTip(**data)
        saved = await _upsert(session, LlmTip, data["id"], instance, dry_run, "LlmTip")
        results.append(saved)
    return results


# ── orchestrator ──────────────────────────────────────────────────────────────


async def run_seed(
    dry_run: bool,
    reset: bool,
    embed_folder: Path | None,
) -> None:
    """Open a single async session, optionally reset, then seed all entities."""
    engine = _get_async_engine()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        if reset:
            await do_reset(session, dry_run)

        # FK-safe insertion order: parents before children
        users = await seed_users(session, dry_run)
        courses = await seed_courses(session, dry_run, users)
        # Materials may commit internally (embed mode) — must run before other
        # flushed-but-not-committed records accumulate in the session.
        await seed_materials(session, dry_run, courses, embed_folder)
        conversations = await seed_conversations(session, dry_run, users, courses)
        await seed_messages(session, dry_run, conversations)
        await seed_shared_links(session, dry_run, conversations)
        await seed_system_prompts(session, dry_run, users)
        await seed_tip_categories(session, dry_run)
        await seed_llm_tips(session, dry_run)

        if not dry_run:
            await session.commit()
            logger.info("Seed complete — all records committed.")
        else:
            logger.info("Dry-run complete — no changes written.")

    await engine.dispose()


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the RAG AI Tutor database with baseline data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate all tables in reverse FK order before seeding.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print what would be inserted without touching the database.",
    )
    parser.add_argument(
        "--embed",
        nargs="?",
        const=str(_BACKEND_DIR / "scripts" / "seed_materials"),
        default=None,  # value when flag is absent entirely
        metavar="FOLDER",
        help=(
            "Embed real PDFs into Qdrant+MinIO and create Material records. "
            "FOLDER defaults to scripts/seed_materials/ when omitted. "
            "Requires Ollama, Qdrant, and MinIO to be running."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    embed_folder: Path | None = None
    if args.embed is not None:
        embed_folder = Path(args.embed)
        if not embed_folder.is_absolute():
            # Resolve relative paths against the backend/ directory
            embed_folder = _BACKEND_DIR / embed_folder
        if not embed_folder.exists():
            raise SystemExit(
                f"Embed folder does not exist: {embed_folder}\n"
                f"Create it and place PDF files inside, then re-run."
            )
        logger.info("Embed mode: reading PDFs from %s", embed_folder)
    else:
        logger.info(
            "Mock mode: creating placeholder Material records (no actual files)."
        )

    if args.dry_run:
        logger.info("DRY-RUN mode — no DB changes will be made.")

    asyncio.run(
        run_seed(dry_run=args.dry_run, reset=args.reset, embed_folder=embed_folder)
    )


if __name__ == "__main__":
    main()
