from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class TimestampSchema(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class TimeSchema(TimestampSchema):
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))