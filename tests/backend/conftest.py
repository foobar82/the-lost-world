import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure both the repo root (for the pipeline package) and the backend
# directory (for the app package) are importable from the tests/ directory.
_repo_root = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, _repo_root)
sys.path.insert(0, str(Path(_repo_root) / "backend"))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_engine(tmp_path):
    """Create a fresh SQLite database in a temporary directory for each test."""
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Provide a SQLAlchemy session bound to the temporary test database."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _mock_store_embedding():
    """Prevent real Ollama / ChromaDB calls during backend tests.

    The mock returns True (success) by default.  Individual tests can
    override this fixture or patch the function themselves when they need
    to inspect call arguments or simulate failures.
    """
    with patch(
        "app.router_feedback.store_feedback_embedding", return_value=True
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def _mock_filter_agent():
    """Prevent real Ollama calls from the filter agent during backend tests.

    By default the mock returns a 'safe' verdict.  Individual tests can
    override this fixture to simulate rejection.
    """
    from pipeline.agents.base import AgentOutput

    safe_output = AgentOutput(
        data={"verdict": "safe", "reason": ""},
        success=True,
        message="Mocked filter — passed",
        tokens_used=0,
    )
    with patch(
        "app.router_feedback.AGENTS",
        {"filter": type("MockAgent", (), {"run": lambda self, inp: safe_output})()},
    ) as mock:
        yield mock


@pytest.fixture()
def client(db_engine):
    """
    Provide a Starlette TestClient whose requests use the temporary database
    instead of the production one.
    """
    from starlette.testclient import TestClient

    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
