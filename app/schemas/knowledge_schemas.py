from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func

# ---------------------------------------------------------
# 1. THE BASE (Shared fields)
# ---------------------------------------------------------
class FileEntityBase(SQLModel):
    course_id: uuid.UUID = Field(foreign_key="courses.id")
    file_name: str = Field(max_length=255)
    file_type: Optional[str] = Field(default=None, max_length=50)
    vector_namespace: Optional[str] = Field(default=None, max_length=255)

# ---------------------------------------------------------
# 2. THE DB ENTITY
# ---------------------------------------------------------
class FileEntity(FileEntityBase, table=True):
    __tablename__ = "materials"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    uploaded_by: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    object_storage_key: Optional[str] = Field(default=None, max_length=2048)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

# ---------------------------------------------------------
# 3. THE INPUT DTOs
# ---------------------------------------------------------
class FileEntityCreate(FileEntityBase):
    pass

# ---------------------------------------------------------
# 4. THE OUTPUT DTO
# ---------------------------------------------------------
class FileEntityPublic(FileEntityBase):
    id: uuid.UUID
    uploaded_by: Optional[uuid.UUID]
    object_storage_key: Optional[str]
    created_at: datetime
