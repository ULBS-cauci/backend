from typing import List, Optional
from datetime import datetime, timezone
import uuid
from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func, JSON
from pydantic import BaseModel

from app.schemas.time_schema import TimeSchema, TimestampSchema
from app.schemas.source_schemas import SourceReference

class MessageSender(str, Enum): 
    USER = "User"
    SYSTEM = "System"
    AI = "AI"

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
    content: str
    output_type_requested: Optional[str] = Field(default=None, max_length=100)

class Message(MessageBase, TimestampSchema, table=True):
    __tablename__ = "messages"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sources: Optional[list] = Field(default=None, sa_column=Column(JSON, nullable=True))

class MessageCreate(SQLModel):
    conversation_id: Optional[uuid.UUID] = None
    content: str = Field(..., min_length=5, description="The content of the message.")
    output_type_requested: Optional[str] = Field(default=None, max_length=100)
    attachment_ids: List[uuid.UUID] = Field(default_factory=list)

# ==========================================
# ATTACHMENT
# ==========================================
class AttachmentBase(SQLModel):
    file_name: str = Field(max_length=255)
    
class Attachment(AttachmentBase, TimestampSchema, table=True):
    __tablename__ = "attachments"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    message_id: Optional[uuid.UUID] = Field(default=None, foreign_key="messages.id")
    object_storage_key: str = Field(max_length=2048)

class AttachmentPublic(SQLModel):
    id: uuid.UUID
    file_name: str
    created_at: datetime

class MessagePublic(MessageBase):
    id: uuid.UUID
    created_at: datetime
    attachments: List[AttachmentPublic] = Field(default_factory=list)
    sources: Optional[List[SourceReference]] = None

# ==========================================
# SHARED LINK
# ==========================================
class SharedLinkBase(SQLModel): #
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id")
    token: str = Field(unique=True, max_length=64) # 
    expires_at: Optional[datetime] = Field(default=None)

class SharedLink(SharedLinkBase, TimestampSchema, table=True):
    __tablename__ = "shared_links"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

class SharedLinkPublic(SharedLinkBase):
    id: uuid.UUID
    created_at: datetime


