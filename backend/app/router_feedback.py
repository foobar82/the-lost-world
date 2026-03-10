import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pipeline.agents.base import AgentInput
from pipeline.registry import AGENTS
from pipeline.utils.embeddings import store_feedback_embedding
from sqlalchemy.orm import Session

from .database import get_db
from .models import Feedback, FeedbackStatus
from .schemas import FeedbackCreate, FeedbackCreatedResponse, FeedbackQueueClearedResponse, FeedbackResponse

logger = logging.getLogger(__name__)

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

    # Run filter agent — if rejected, update status and return early.
    try:
        filter_result = AGENTS["filter"].run(
            AgentInput(data=body.content, context={})
        )
        if filter_result.data.get("verdict") == "reject":
            feedback.status = FeedbackStatus.rejected
            feedback.agent_notes = filter_result.data.get(
                "reason", "Rejected by safety filter"
            )
            db.commit()
            db.refresh(feedback)
            return FeedbackCreatedResponse(
                reference=feedback.reference, status=feedback.status
            )
    except Exception:
        # If the filter agent itself crashes, don't block the user.
        logger.exception(
            "Filter agent error for %s — continuing with submission",
            feedback.reference,
        )

    # Generate embedding via Ollama and store in ChromaDB.
    # Fire-and-forget: a failure here must never block the user submission.
    try:
        if not store_feedback_embedding(feedback.reference, body.content):
            logger.warning(
                "Embedding generation failed for %s — will backfill at batch time",
                feedback.reference,
            )
    except Exception:
        logger.exception(
            "Unexpected error generating embedding for %s", feedback.reference
        )

    return FeedbackCreatedResponse(reference=feedback.reference, status=feedback.status)


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(
    status: FeedbackStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Feedback)
    if status is not None:
        query = query.filter(Feedback.status == status)
    return query.order_by(Feedback.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{reference}", response_model=FeedbackResponse)
def get_feedback(reference: str, db: Session = Depends(get_db)):
    feedback = db.query(Feedback).filter(Feedback.reference == reference).first()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback


@router.delete("", response_model=FeedbackQueueClearedResponse)
def clear_feedback_queue(db: Session = Depends(get_db)):
    """Delete all feedback items from the queue.

    Useful for resetting the queue before an experiment.  All items are
    removed regardless of their current status.
    """
    deleted = db.query(Feedback).delete()
    db.commit()
    return FeedbackQueueClearedResponse(deleted=deleted)


@router.post("/{reference}/reactivate", response_model=FeedbackResponse)
def reactivate_feedback(reference: str, db: Session = Depends(get_db)):
    """Reset a ``done`` or ``rejected`` feedback item back to ``pending``.

    Useful for re-queuing items that were incorrectly marked as completed
    (e.g. during a dry run) or that need to be re-processed.
    """
    feedback = db.query(Feedback).filter(Feedback.reference == reference).first()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if feedback.status == FeedbackStatus.pending:
        return feedback
    if feedback.status == FeedbackStatus.in_progress:
        raise HTTPException(
            status_code=409,
            detail="Cannot reactivate feedback that is currently in progress",
        )
    feedback.status = FeedbackStatus.pending
    feedback.agent_notes = None
    db.commit()
    db.refresh(feedback)
    return feedback
