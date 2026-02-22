from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import FeedbackStatus


class FeedbackCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    content: str
    status: FeedbackStatus
    agent_notes: str | None
    created_at: datetime
    updated_at: datetime


class FeedbackCreatedResponse(BaseModel):
    reference: str
    status: FeedbackStatus
