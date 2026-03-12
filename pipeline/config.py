"""Pipeline configuration — all tuneable values in one place."""

import os
from pathlib import Path

# Resolve the database path relative to the project layout so the pipeline
# always connects to the same SQLite file the backend writes to, regardless
# of the working directory at invocation time.
_project_root = Path(__file__).resolve().parents[1]
_default_db_path = _project_root / "backend" / "lost_world.db"
_db_url = os.environ.get("DATABASE_URL", f"sqlite:///{_default_db_path}")

PIPELINE_CONFIG = {
    "daily_budget_gbp": 2.00,
    "weekly_budget_gbp": 8.00,
    "writer_model": "claude-sonnet-4-20250514",
    "reviewer_model": "claude-sonnet-4-20250514",
    "local_model": "llama3.1:8b",
    "embedding_model": "nomic-embed-text",
    "ollama_url": "http://localhost:11434",
    "max_writer_retries": 2,
    "repo_path": ".",  # Override per environment
    "contract_file": "contract.md",
    "db_url": _db_url,
    "cluster_distance_threshold": 0.35,
    "cluster_distance_metric": "cosine",
    "max_tasks_per_run": 2,
    "max_tasks_per_day": 4,
}
