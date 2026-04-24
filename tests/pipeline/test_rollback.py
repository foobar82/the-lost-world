"""Tests for pipeline.rollback — the DB rollback helper."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.rollback import (  # noqa: E402
    extract_references,
    find_run_json,
    get_commit_message,
    parse_agent_branch,
    rollback_db_for_commit,
)


# ---------------------------------------------------------------------------
# parse_agent_branch
# ---------------------------------------------------------------------------


class TestParseAgentBranch:
    def test_valid_message(self):
        msg = "Merge agent/abc12345: Add dark mode toggle"
        assert parse_agent_branch(msg) == "agent/abc12345"

    def test_valid_message_min_hex(self):
        msg = "Merge agent/00000000: something"
        assert parse_agent_branch(msg) == "agent/00000000"

    def test_non_merge_message(self):
        assert parse_agent_branch("Initial commit") is None

    def test_human_merge_message(self):
        assert parse_agent_branch("Merge pull request #5 from feature/x") is None

    def test_empty_string(self):
        assert parse_agent_branch("") is None

    def test_partial_match_not_at_start(self):
        # Pattern must match at start of string
        assert parse_agent_branch("fixup Merge agent/abc12345: blah") is None


# ---------------------------------------------------------------------------
# find_run_json
# ---------------------------------------------------------------------------


class TestFindRunJson:
    def test_finds_matching_json(self, tmp_path):
        payload = {
            "references": ["LW-001"],
            "deploy": {"branch": "agent/abc12345", "deployed": True},
        }
        (tmp_path / "2025-01-01T00-00-00Z_LW-001.json").write_text(
            json.dumps(payload)
        )
        result = find_run_json("agent/abc12345", tmp_path)
        assert result is not None
        assert result.name == "2025-01-01T00-00-00Z_LW-001.json"

    def test_returns_none_when_no_match(self, tmp_path):
        payload = {"deploy": {"branch": "agent/xxxxxx"}}
        (tmp_path / "run.json").write_text(json.dumps(payload))
        assert find_run_json("agent/abc12345", tmp_path) is None

    def test_returns_none_when_dir_missing(self, tmp_path):
        missing_dir = tmp_path / "nonexistent"
        assert find_run_json("agent/abc12345", missing_dir) is None

    def test_skips_invalid_json(self, tmp_path):
        (tmp_path / "bad.json").write_text("not json {{{")
        assert find_run_json("agent/abc12345", tmp_path) is None

    def test_handles_missing_deploy_key(self, tmp_path):
        (tmp_path / "run.json").write_text(json.dumps({"references": ["LW-001"]}))
        assert find_run_json("agent/abc12345", tmp_path) is None


# ---------------------------------------------------------------------------
# extract_references
# ---------------------------------------------------------------------------


class TestExtractReferences:
    def test_extracts_references(self, tmp_path):
        payload = {"references": ["LW-001", "LW-002"]}
        p = tmp_path / "run.json"
        p.write_text(json.dumps(payload))
        assert extract_references(p) == ["LW-001", "LW-002"]

    def test_returns_empty_list_when_missing(self, tmp_path):
        p = tmp_path / "run.json"
        p.write_text(json.dumps({}))
        assert extract_references(p) == []


# ---------------------------------------------------------------------------
# rollback_db_for_commit — integration-style with mocks
# ---------------------------------------------------------------------------


def _make_run_json(tmp_path: Path, branch: str, refs: list[str]) -> None:
    """Write a minimal run JSON to tmp_path/pipeline/data/runs/."""
    runs_dir = tmp_path / "pipeline" / "data" / "runs"
    runs_dir.mkdir(parents=True)
    payload = {
        "references": refs,
        "deploy": {"branch": branch, "deployed": True},
    }
    (runs_dir / "2025-01-01T00-00-00Z_LW-001.json").write_text(
        json.dumps(payload)
    )


class TestRollbackDbForCommit:
    def test_happy_path(self, tmp_path):
        branch = "agent/abc12345"
        refs = ["LW-001", "LW-002"]
        _make_run_json(tmp_path, branch, refs)

        with patch("pipeline.rollback.get_commit_message") as mock_msg, \
             patch("pipeline.rollback.reset_feedback_to_pending") as mock_reset:
            mock_msg.return_value = f"Merge {branch}: some feature"
            mock_reset.return_value = 2

            result = rollback_db_for_commit(
                "deadbeef",
                repo_path=str(tmp_path),
                db_url="sqlite:///:memory:",
            )

        assert result["branch"] == branch
        assert result["references"] == refs
        assert result["reset_count"] == 2
        assert result["warning"] is None
        mock_reset.assert_called_once_with(
            refs, "sqlite:///:memory:", dry_run=False
        )

    def test_non_agent_commit_returns_warning(self, tmp_path):
        with patch("pipeline.rollback.get_commit_message") as mock_msg:
            mock_msg.return_value = "Regular commit message"
            result = rollback_db_for_commit(
                "deadbeef",
                repo_path=str(tmp_path),
                db_url="sqlite:///:memory:",
            )
        assert result["branch"] is None
        assert result["warning"] is not None
        assert result["reset_count"] == 0

    def test_missing_run_json_returns_warning(self, tmp_path):
        # runs/ dir exists but has no matching JSON
        (tmp_path / "pipeline" / "data" / "runs").mkdir(parents=True)

        with patch("pipeline.rollback.get_commit_message") as mock_msg:
            mock_msg.return_value = "Merge agent/abc12345: feature"
            result = rollback_db_for_commit(
                "deadbeef",
                repo_path=str(tmp_path),
                db_url="sqlite:///:memory:",
            )
        assert result["run_json"] is None
        assert result["warning"] is not None
        assert result["reset_count"] == 0

    def test_empty_references_in_json_returns_warning(self, tmp_path):
        _make_run_json(tmp_path, "agent/abc12345", [])

        with patch("pipeline.rollback.get_commit_message") as mock_msg:
            mock_msg.return_value = "Merge agent/abc12345: feature"
            result = rollback_db_for_commit(
                "deadbeef",
                repo_path=str(tmp_path),
                db_url="sqlite:///:memory:",
            )
        assert result["references"] == []
        assert result["warning"] is not None
        assert result["reset_count"] == 0

    def test_dry_run_flag_passed_through(self, tmp_path):
        _make_run_json(tmp_path, "agent/abc12345", ["LW-001"])

        with patch("pipeline.rollback.get_commit_message") as mock_msg, \
             patch("pipeline.rollback.reset_feedback_to_pending") as mock_reset:
            mock_msg.return_value = "Merge agent/abc12345: feature"
            mock_reset.return_value = 1

            rollback_db_for_commit(
                "deadbeef",
                repo_path=str(tmp_path),
                db_url="sqlite:///:memory:",
                dry_run=True,
            )

        mock_reset.assert_called_once_with(
            ["LW-001"], "sqlite:///:memory:", dry_run=True
        )

    def test_git_error_returns_warning(self, tmp_path):
        with patch("pipeline.rollback.get_commit_message") as mock_msg:
            mock_msg.side_effect = ValueError("git log failed")
            result = rollback_db_for_commit(
                "badhash",
                repo_path=str(tmp_path),
                db_url="sqlite:///:memory:",
            )
        assert result["warning"] is not None
        assert "git log failed" in result["warning"]


# ---------------------------------------------------------------------------
# reset_feedback_to_pending — DB integration test
# ---------------------------------------------------------------------------


class TestResetFeedbackToPending:
    """Integration test against a real SQLite database (file-based so connections share state)."""

    def _setup_db(self, tmp_path):
        """Return (db_url, engine) populated with a few Feedback rows."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from backend.app.database import Base
        from backend.app.models import Feedback, FeedbackStatus

        db_file = tmp_path / "test.db"
        db_url = f"sqlite:///{db_file}"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        for ref, status in [
            ("LW-001", FeedbackStatus.done),
            ("LW-002", FeedbackStatus.done),
            ("LW-003", FeedbackStatus.pending),
            ("LW-004", FeedbackStatus.in_progress),
        ]:
            fb = Feedback(reference=ref, content=f"Content for {ref}", status=status)
            session.add(fb)
        session.commit()
        session.close()
        return db_url, engine

    def test_resets_only_done_rows(self, tmp_path):
        from sqlalchemy.orm import sessionmaker

        from backend.app.models import Feedback, FeedbackStatus
        from pipeline.rollback import reset_feedback_to_pending

        db_url, engine = self._setup_db(tmp_path)
        Session = sessionmaker(bind=engine)

        count = reset_feedback_to_pending(
            ["LW-001", "LW-002", "LW-003", "LW-004"], db_url
        )
        # Only LW-001 and LW-002 were 'done'; LW-003 was already pending,
        # LW-004 was in_progress — neither should be touched.
        assert count == 2

        session = Session()
        statuses = {
            fb.reference: fb.status
            for fb in session.query(Feedback).all()
        }
        session.close()
        assert statuses["LW-001"] == FeedbackStatus.pending
        assert statuses["LW-002"] == FeedbackStatus.pending
        assert statuses["LW-003"] == FeedbackStatus.pending
        assert statuses["LW-004"] == FeedbackStatus.in_progress

    def test_dry_run_does_not_modify_db(self, tmp_path):
        from sqlalchemy.orm import sessionmaker

        from backend.app.models import Feedback, FeedbackStatus
        from pipeline.rollback import reset_feedback_to_pending

        db_url, engine = self._setup_db(tmp_path)
        Session = sessionmaker(bind=engine)

        count = reset_feedback_to_pending(["LW-001"], db_url, dry_run=True)
        assert count == 1  # 1 row *would* be reset

        session = Session()
        fb = session.query(Feedback).filter_by(reference="LW-001").one()
        assert fb.status == FeedbackStatus.done  # unchanged
        session.close()

    def test_empty_references_returns_zero(self):
        from pipeline.rollback import reset_feedback_to_pending
        assert reset_feedback_to_pending([], "sqlite:///:memory:") == 0
