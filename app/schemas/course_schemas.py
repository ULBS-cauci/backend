from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlmodel import SQLModel, Field

# ---------------------------------------------------------
# 1. THE BASE (Shared fields)
# ---------------------------------------------------------
class CourseBase(SQLModel):
    title: str = Field(max_length=255)
    description: Optional[str] = Field(default=None)

# ---------------------------------------------------------
# 2. THE DB ENTITY
# ---------------------------------------------------------
class Course(CourseBase, table=True):
    __tablename__ = "courses"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_by: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
