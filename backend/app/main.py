from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .router_feedback import router as feedback_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="The Lost World Plateau", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feedback_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
