from typing import Optional
from datetime import datetime, timezone
import uuid
from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func

from app.schemas.time_schema import TimeSchema


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
    role: UserRole = Field(
        default=UserRole.STUDENT
    )  # TODO: Revisit default role assignment logic in the future


# ---------------------------------------------------------
# 2. THE DB ENTITY (Strictly for the database layer)
# ---------------------------------------------------------
class User(UserBase, TimeSchema, table=True):
    __tablename__ = "users"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str


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


# ---------------------------------------------------------
# USER SETTINGS (per-user global chat preferences)
# ---------------------------------------------------------
class UserSettingBase(SQLModel):
    custom_system_prompt: Optional[str] = None
    selected_system_prompt_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="system_prompts.id"
    )


class UserSetting(UserSettingBase, TimeSchema, table=True):
    __tablename__ = "user_settings"  # type: ignore
    user_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True)


class UserSettingUpdate(SQLModel):
    custom_system_prompt: Optional[str] = None
    selected_system_prompt_id: Optional[uuid.UUID] = None


class UserSettingPublic(UserSettingBase):
    user_id: uuid.UUID
    updated_at: datetime
