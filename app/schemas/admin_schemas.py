from typing import Optional
from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field

from app.schemas.time_schema import TimestampSchema


# ==========================================
# TIP CATEGORY  (lookup / reference table)
# ==========================================
class TipCategoryBase(SQLModel):
    name: str = Field(unique=True, max_length=100)


class TipCategory(TipCategoryBase, TimestampSchema, table=True):
    __tablename__ = "tip_categories"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class TipCategoryCreate(TipCategoryBase):
    pass


class TipCategoryPublic(TipCategoryBase):
    id: uuid.UUID
    created_at: datetime


# ==========================================
# SYSTEM PROMPT
# ==========================================
class SystemPromptBase(SQLModel):
    title: Optional[str] = Field(default=None, max_length=255)
    content: str  # maps to TEXT in PostgreSQL (no max_length)


class SystemPrompt(SystemPromptBase, TimestampSchema, table=True):
    __tablename__ = "system_prompts"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    author_id: uuid.UUID = Field(foreign_key="users.id")


class SystemPromptPublic(SystemPromptBase):
    id: uuid.UUID
    author_id: uuid.UUID
    created_at: datetime


class SystemPromptSummary(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None


# ==========================================
# LLM TIPS
# ==========================================
class LlmTipBase(SQLModel):
    title: str = Field(max_length=255)
    description: str  # maps to TEXT in PostgreSQL (no max_length)
    example_prompt: Optional[str] = Field(default=None)  # TEXT
    category_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="tip_categories.id"
    )


class LlmTip(LlmTipBase, TimestampSchema, table=True):
    __tablename__ = "llm_tips"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class LlmTipPublic(LlmTipBase):
    id: uuid.UUID
    created_at: datetime
