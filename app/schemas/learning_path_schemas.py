from typing import Any, List, Literal, Optional
from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from pydantic import BaseModel

from app.schemas.time_schema import TimeSchema


# ==========================================
# NESTED JSON PAYLOAD MODELS
# ==========================================
# The `modules` column stores a JSON array of these objects. They are plain Pydantic
# models (not tables) — validated at the API boundary on read, exactly like
# chat_schemas.QuizAnswer / SourceReference are for the messages.* JSON columns.
class LearningPathModule(BaseModel):
    id: str  # stable client-facing id (e.g. "m1"); used as the progress map key
    title: str
    objectives: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    material_ids: List[uuid.UUID] = Field(default_factory=list)
    suggested_action: Optional[Literal["ask_tutor", "generate_quiz"]] = None


# ==========================================
# 1. THE BASE (shared fields)
# ==========================================
class LearningPathBase(SQLModel):
    user_id: uuid.UUID = Field(foreign_key="users.id")
    course_id: uuid.UUID = Field(foreign_key="courses.id")
    title: str = Field(default="Learning Path", max_length=255)


# ==========================================
# 2. THE DB ENTITY
# ==========================================
class LearningPath(LearningPathBase, TimeSchema, table=True):
    __tablename__ = "learning_paths"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Dominant language of the course materials the path was generated in (English
    # name, e.g. "Romanian"); persisted so the UI can build prompts in that language.
    language: Optional[str] = Field(default=None, max_length=50)
    # Ordered list of LearningPathModule dicts (JSON, like Message.sources).
    modules: List[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    # Map of module.id -> completed flag. Reassign (don't mutate in place) before
    # add() so SQLAlchemy marks the JSON column dirty — same rule as Message.quiz_answers.
    progress: dict[str, bool] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


# ==========================================
# 3. THE INPUT DTOs
# ==========================================
class LearningPathGenerateRequest(BaseModel):
    course_id: uuid.UUID


class LearningPathProgressUpdate(BaseModel):
    module_id: str
    completed: bool


# ==========================================
# 4. THE OUTPUT DTO
# ==========================================
class LearningPathPublic(LearningPathBase):
    id: uuid.UUID
    language: Optional[str] = None
    modules: List[LearningPathModule]
    progress: dict[str, bool]
    created_at: datetime
    updated_at: datetime


# ==========================================
# SSE STREAM EVENT (generation progress)
# ==========================================
class LearningPathDoneEvent(BaseModel):
    type: Literal["learning_path_done"] = "learning_path_done"
    learning_path_id: str
