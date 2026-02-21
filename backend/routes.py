from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Feedback, FeedbackStatus
from schemas import FeedbackCreate, FeedbackResponse, FeedbackSubmitResponse

router = APIRouter()


def generate_reference(db: Session) -> str:
    """Generate the next sequential reference number (LW-001, LW-002, etc.)."""
    last = db.query(Feedback).order_by(Feedback.id.desc()).first()
    next_num = (last.id + 1) if last else 1
    return f"LW-{next_num:03d}"


@router.post("/feedback", response_model=FeedbackSubmitResponse)
def submit_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    reference = generate_reference(db)
    db_feedback = Feedback(reference=reference, content=feedback.content)
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return FeedbackSubmitResponse(reference=db_feedback.reference, status=db_feedback.status)


@router.get("/feedback", response_model=list[FeedbackResponse])
def list_feedback(
    status: Optional[FeedbackStatus] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Feedback)
    if status:
        query = query.filter(Feedback.status == status)
    return query.order_by(Feedback.created_at.desc()).all()


@router.get("/feedback/{reference}", response_model=FeedbackResponse)
def get_feedback(reference: str, db: Session = Depends(get_db)):
    feedback = db.query(Feedback).filter(Feedback.reference == reference).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback
