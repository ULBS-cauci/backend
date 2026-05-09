from typing import Optional
from datetime import datetime, timezone
import uuid
from enum import Enum
from sqlmodel import SQLModel, Field

# ==========================================
# SYSTEM PROMPT
# ==========================================
class SystemPromptBase(SQLModel):
    course_id: Optional[uuid.UUID] = Field(default=None, foreign_key="courses.id") # Allows for global prompts when null, or course-specific prompts when set
    title: Optional[str] = Field(default=None, max_length=255)
    content: str
    is_active: bool = Field(default=True)

class SystemPrompt(SystemPromptBase, table=True):
    __tablename__ = "system_prompts"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    author_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LlmTipPublic(LlmTipBase):
    id: uuid.UUID
    created_at: datetime
