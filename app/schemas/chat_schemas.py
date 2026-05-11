from typing import Optional
from datetime import datetime, timezone
import uuid
from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func
from pydantic import BaseModel

class MessageSender(str, Enum): 
    USER = "User"
    SYSTEM = "System"
    AI = "AI"

# ==========================================
# CHAT SESSION
# ==========================================
class ChatSessionBase(SQLModel):
    user_id: uuid.UUID = Field(foreign_key="users.id")
    course_id: Optional[uuid.UUID] = Field(default=None, foreign_key="courses.id")
    title: str = Field(default="New Conversation", max_length=255)

class ChatSession(ChatSessionBase, table=True):
    __tablename__ = "conversations"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )

class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSessionPublic(ChatSessionBase):
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

class Message(MessageBase, table=True):
    __tablename__ = "messages"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

class MessagePublic(MessageBase):
    id: uuid.UUID
    created_at: datetime

# ==========================================
# ATTACHMENT
# ==========================================
class AttachmentBase(SQLModel):
    message_id: uuid.UUID = Field(foreign_key="messages.id")
    file_name: str = Field(max_length=255)
    
class Attachment(AttachmentBase, table=True):
    __tablename__ = "attachments"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    object_storage_key: str = Field(max_length=2048) # Replaces file_url
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

class AttachmentPublic(AttachmentBase):
    id: uuid.UUID
    object_storage_key: str
    created_at: datetime

# ==========================================
# SHARED LINK
# ==========================================
class SharedLinkBase(SQLModel): #
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id")
    token: str = Field(unique=True, max_length=64) # 
    expires_at: Optional[datetime] = Field(default=None)

class SharedLink(SharedLinkBase, table=True):
    __tablename__ = "shared_links"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

class SharedLinkPublic(SharedLinkBase):
    id: uuid.UUID
    created_at: datetime

class AskRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=5,
        description="The student's question to be answered by the LLM.",
    )

class ChatRequest(BaseModel):
    message: str
    collection_name: str = "university_library"
