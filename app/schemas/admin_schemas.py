from typing import Optional
from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func


# ==========================================
# SYSTEM PROMPT
# ==========================================
class SystemPromptBase(SQLModel):
    title: Optional[str] = Field(default=None, max_length=255)
    content: str


class SystemPrompt(SystemPromptBase, table=True):
    __tablename__ = "system_prompts"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    author_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        )
    )


class SystemPromptPublic(SystemPromptBase):
    id: uuid.UUID
    author_id: uuid.UUID
    created_at: datetime


# ==========================================
# LLM TIPS
# ==========================================
class LlmTipBase(SQLModel):
    title: str = Field(max_length=255)
    description: str
    example_prompt: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None, max_length=100)


class LlmTip(LlmTipBase, table=True):
    __tablename__ = "llm_tips"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        )
    )


class LlmTipPublic(LlmTipBase):
    id: uuid.UUID
    created_at: datetime
