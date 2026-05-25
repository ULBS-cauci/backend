from typing import Optional
from datetime import datetime
import uuid
from enum import Enum
from sqlmodel import SQLModel, Field
from pydantic import BaseModel

from app.schemas.time_schema import TimeSchema, TimestampSchema

class MessageSender(str, Enum): 
    USER = "User"
    SYSTEM = "System"
    AI = "AI"

# ==========================================
# OUTPUT FORMAT  (lookup / reference table)
# ==========================================
class OutputFormatBase(SQLModel):
    name: str = Field(unique=True, max_length=100)
    description: Optional[str] = Field(default=None)


class OutputFormat(OutputFormatBase, TimestampSchema, table=True):
    __tablename__ = "output_formats"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class OutputFormatCreate(OutputFormatBase):
    pass


class OutputFormatPublic(OutputFormatBase):
    id: uuid.UUID
    created_at: datetime


# ==========================================
# CHAT CONVERSATION
# ==========================================
class ConversationBase(SQLModel):
    user_id: uuid.UUID = Field(foreign_key="users.id")
    course_id: Optional[uuid.UUID] = Field(default=None, foreign_key="courses.id")
    title: str = Field(default="New Conversation", max_length=255)

class Conversation(ConversationBase, TimeSchema, table=True):
    __tablename__ = "conversations"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

class ConversationCreate(ConversationBase):
    pass

class ConversationPublic(ConversationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

# ==========================================
# MESSAGE
# ==========================================
class MessageBase(SQLModel):
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id")
    sender: MessageSender
    content: str  # maps to TEXT in PostgreSQL (no max_length)
    output_format_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="output_formats.id"
    )

class Message(MessageBase, TimestampSchema, table=True):
    __tablename__ = "messages"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

class MessagePublic(MessageBase):
    id: uuid.UUID
    created_at: datetime

class MessageCreate(SQLModel):
    conversation_id: Optional[uuid.UUID] = None
    content: str = Field(..., min_length=5, description="The content of the message.")
    output_format_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional FK to output_formats — specifies the desired response format.",
    )

# ==========================================
# ATTACHMENT
# ==========================================
class AttachmentBase(SQLModel):
    message_id: uuid.UUID = Field(foreign_key="messages.id")
    file_name: str = Field(max_length=255)
    
class Attachment(AttachmentBase, TimestampSchema, table=True):
    __tablename__ = "attachments"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    object_storage_key: str = Field(max_length=2048) # Replaces file_url

class AttachmentPublic(AttachmentBase):
    id: uuid.UUID
    object_storage_key: str
    created_at: datetime

# ==========================================
# SHARED LINK
# ==========================================
class SharedLinkBase(SQLModel):
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id")
    token: str = Field(unique=True, max_length=64)
    expires_at: Optional[datetime] = Field(default=None)

class SharedLink(SharedLinkBase, TimestampSchema, table=True):
    __tablename__ = "shared_links"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

class SharedLinkPublic(SharedLinkBase):
    id: uuid.UUID
    created_at: datetime


