from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import FeedbackStatus


class FeedbackCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    source: str = Field(default="user", max_length=32)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    content: str
    status: FeedbackStatus
    agent_notes: str | None
    source: str
    created_at: datetime
    updated_at: datetime


class FeedbackCreatedResponse(BaseModel):
    reference: str
    status: FeedbackStatus


class FeedbackQueueClearedResponse(BaseModel):
    deleted: int
