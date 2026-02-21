from datetime import datetime
from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class FeedbackResponse(BaseModel):
    id: int
    reference: str
    content: str
    status: str
    agent_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeedbackSubmitResponse(BaseModel):
    reference: str
    status: str
