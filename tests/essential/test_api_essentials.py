# ESSENTIAL TESTS - Human-maintained only
# These tests validate contract.md invariants
# Agents must not modify these files
#
# Coverage notes:
#   - "POST /api/feedback returns reference and status" — ALREADY TESTED in
#     tests/backend/test_api.py (TestCreateFeedback). Skipped here.
#   - "GET /api/feedback returns a list" — ALREADY TESTED in
#     tests/backend/test_api.py (TestListFeedback). Skipped here.
#   - "GET /api/feedback/{reference} returns correct item" — ALREADY TESTED in
#     tests/backend/test_api.py (TestGetFeedbackByReference). Skipped here.
#   - "POST with empty content returns error (not 500)" — ALREADY TESTED in
#     tests/backend/test_api.py (test_empty_content_is_rejected → 422). Skipped.
#   - "Backend serves health check without errors" — NEW. No existing test
#     exercises the /api/health endpoint.

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Path setup — identical to tests/backend/conftest.py
# ---------------------------------------------------------------------------
_repo_root = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, _repo_root)
sys.path.insert(0, str(Path(_repo_root) / "backend"))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from pipeline.agents.base import AgentOutput  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _mock_store_embedding():
    with patch(
        "app.router_feedback.store_feedback_embedding", return_value=True
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_filter_agent():
    safe_output = AgentOutput(
        data={"verdict": "safe", "reason": ""},
        success=True,
        message="Mocked filter — passed",
        tokens_used=0,
    )
    with patch(
        "app.router_feedback.AGENTS",
        {"filter": type("MockAgent", (), {"run": lambda self, inp: safe_output})()},
    ):
        yield


@pytest.fixture()
def client(db_engine):
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


# ---------------------------------------------------------------------------
# Essential API tests
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Backend starts and serves the health endpoint without errors."""

    def test_health_endpoint_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
