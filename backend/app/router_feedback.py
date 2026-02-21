from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .database import get_db
from .models import Feedback, FeedbackStatus
from .schemas import FeedbackCreate, FeedbackCreatedResponse, FeedbackResponse

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackCreatedResponse, status_code=201)
def create_feedback(body: FeedbackCreate, db: Session = Depends(get_db)):
    feedback = Feedback(
        reference="",  # placeholder until we have the auto-generated id
        content=body.content,
        status=FeedbackStatus.pending,
    )
    db.add(feedback)
    db.flush()  # assigns feedback.id from the autoincrement sequence
    feedback.reference = f"LW-{feedback.id:03d}"
    db.commit()
    db.refresh(feedback)
    return FeedbackCreatedResponse(reference=feedback.reference, status=feedback.status)


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(
    status: FeedbackStatus | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Feedback)
    if status is not None:
        query = query.filter(Feedback.status == status)
    return query.order_by(Feedback.created_at.desc()).all()


@router.get("/{reference}", response_model=FeedbackResponse)
def get_feedback(reference: str, db: Session = Depends(get_db)):
    feedback = db.query(Feedback).filter(Feedback.reference == reference).first()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback
