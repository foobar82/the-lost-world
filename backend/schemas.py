from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from models import FeedbackStatus


class FeedbackCreate(BaseModel):
    content: str


class FeedbackResponse(BaseModel):
    id: int
    reference: str
    content: str
    status: FeedbackStatus
    agent_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeedbackSubmitResponse(BaseModel):
    reference: str
    status: FeedbackStatus
