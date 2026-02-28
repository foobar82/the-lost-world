import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

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


# In production, serve the built React frontend as static files.
# The deploy script sets LOST_WORLD_STATIC to the frontend dist directory.
_static_dir = os.environ.get("LOST_WORLD_STATIC")
if _static_dir:
    _static_path = Path(_static_dir)

    # Serve asset files (JS, CSS, images) under /assets
    app.mount("/assets", StaticFiles(directory=_static_path / "assets"), name="assets")

    # Catch-all: serve index.html for any non-API route (SPA client-side routing)
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file = (_static_path / full_path).resolve()
        if file.is_file() and file.is_relative_to(_static_path.resolve()):
            return FileResponse(file)
        return FileResponse(_static_path / "index.html")
