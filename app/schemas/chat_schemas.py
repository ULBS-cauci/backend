from typing import Optional
from datetime import datetime, timezone
import uuid
from enum import Enum
from sqlmodel import SQLModel, Field

class MessageRole(str, Enum): 
    USER = "User"
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    role: MessageRole
    content: str
    output_type_requested: Optional[str] = Field(default=None, max_length=100)

class Message(MessageBase, table=True):
    __tablename__ = "messages"  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SharedLinkPublic(SharedLinkBase):
    id: uuid.UUID
    created_at: datetime
