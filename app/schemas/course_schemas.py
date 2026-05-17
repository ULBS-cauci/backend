from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func

from app.schemas.time_schema import TimeSchema

# ---------------------------------------------------------
# 1. THE BASE (Shared fields)
# ---------------------------------------------------------
class CourseBase(SQLModel):
    title: str = Field(max_length=255)
    description: Optional[str] = Field(default=None)

# ---------------------------------------------------------
# 2. THE DB ENTITY
# ---------------------------------------------------------
class Course(CourseBase, TimeSchema, table=True):
    __tablename__ = "courses"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    held_by: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")

# ---------------------------------------------------------
# 3. THE INPUT DTOs
# ---------------------------------------------------------
class CourseCreate(CourseBase):
    pass

class CourseUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None

# ---------------------------------------------------------
# 4. THE OUTPUT DTO
# ---------------------------------------------------------
class CoursePublic(CourseBase):
    id: uuid.UUID
    held_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
