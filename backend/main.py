from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_db, get_session
from models import Feedback, FeedbackStatus
from schemas import FeedbackCreate, FeedbackResponse, FeedbackSubmitResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="The Lost World Plateau", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def generate_reference(session: AsyncSession) -> str:
    result = await session.execute(select(func.count(Feedback.id)))
    count = result.scalar_one()
    return f"LW-{count + 1:03d}"


@app.post("/api/feedback", response_model=FeedbackSubmitResponse)
async def create_feedback(
    body: FeedbackCreate,
    session: AsyncSession = Depends(get_session),
):
    reference = await generate_reference(session)
    feedback = Feedback(reference=reference, content=body.content)
    session.add(feedback)
    await session.commit()
    return FeedbackSubmitResponse(reference=feedback.reference, status=feedback.status.value)


@app.get("/api/feedback", response_model=list[FeedbackResponse])
async def list_feedback(
    status: FeedbackStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    query = select(Feedback).order_by(Feedback.created_at.desc())
    if status is not None:
        query = query.where(Feedback.status == status)
    result = await session.execute(query)
    return result.scalars().all()


@app.get("/api/feedback/{reference}", response_model=FeedbackResponse)
async def get_feedback(
    reference: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Feedback).where(Feedback.reference == reference))
    feedback = result.scalar_one_or_none()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback


# Serve frontend static files in production
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
