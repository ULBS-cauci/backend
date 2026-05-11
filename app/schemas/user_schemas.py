from typing import Optional
from datetime import datetime, timezone
import uuid
from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func

class UserRole(str, Enum):
    STUDENT = "Student"
    PROFESSOR = "Professor"
    ADMIN = "Admin"

# ---------------------------------------------------------
# 1. THE BASE (Shared fields - Never used directly)
# ---------------------------------------------------------
class UserBase(SQLModel):
    email: str = Field(index=True, unique=True, max_length=255)
    first_name: str = Field(max_length=127)
    last_name: str = Field(max_length=127)
    role: UserRole = Field(default=UserRole.STUDENT) #TODO: Revisit default role assignment logic in the future

# ---------------------------------------------------------
# 2. THE DB ENTITY (Strictly for the database layer)
# ---------------------------------------------------------
class User(UserBase, table=True):
    __tablename__ = "users"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: Optional[datetime] = Field(default=None, 
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: Optional[datetime] = Field(default=None, 
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )

# ---------------------------------------------------------
# 3. THE INPUT DTOs (What the user is allowed to send)
# ---------------------------------------------------------
class UserCreate(UserBase):
    password: str 

class UserUpdate(SQLModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None

# ---------------------------------------------------------
# 4. THE OUTPUT DTO (What the API is allowed to return)
# ---------------------------------------------------------
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
