from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func

from app.schemas.time_schema import TimestampSchema


# ---------------------------------------------------------
# 1. THE BASE (Shared fields)
# ---------------------------------------------------------
class MaterialBase(SQLModel):
    course_id: uuid.UUID = Field(foreign_key="courses.id")
    file_name: str = Field(max_length=255)
    file_type: Optional[str] = Field(default=None, max_length=50)
    vector_namespace: Optional[str] = Field(default=None, max_length=255)


# ---------------------------------------------------------
# 2. THE DB ENTITY
# ---------------------------------------------------------
class Material(MaterialBase, TimestampSchema, table=True):
    __tablename__ = "materials"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    uploaded_by: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    object_storage_key: Optional[str] = Field(default=None, max_length=2048)


# ---------------------------------------------------------
# 3. THE INPUT DTOs
# ---------------------------------------------------------
class MaterialCreate(MaterialBase):
    pass


# ---------------------------------------------------------
# 4. THE OUTPUT DTO
# ---------------------------------------------------------
class MaterialPublic(MaterialBase):
    id: uuid.UUID
    uploaded_by: Optional[uuid.UUID]
    object_storage_key: Optional[str]
    created_at: datetime
    preview_url: Optional[str] = None
