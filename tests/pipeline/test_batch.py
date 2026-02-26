"""Integration tests for the batch orchestrator.

All LLM calls are mocked — no real API credits are burned.
Each test gets a fresh in-memory SQLite database.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.database import Base  # noqa: E402
from backend.app.models import Feedback, FeedbackStatus  # noqa: E402
from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.batch import run_batch  # noqa: E402
from pipeline.config import PIPELINE_CONFIG  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _tmp_budget_file(tmp_path, monkeypatch):
    """Redirect budget persistence so tests never touch the real file."""
    budget_file = tmp_path / "budget.json"
    monkeypatch.setattr("pipeline.budget.BUDGET_FILE", budget_file)
    yield budget_file


@pytest.fixture()
def db_session(tmp_path):
    """Create a fresh SQLite database and return a session."""
    db_path = tmp_path / "test_batch.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def seed_pending(db_session):
    """Insert three pending feedback rows and return their references."""
    refs = []
    for i in range(1, 4):
        fb = Feedback(
            reference=f"LW-{i:03d}",
            content=f"Feedback item {i}",
            status=FeedbackStatus.pending,
        )
        db_session.add(fb)
        refs.append(fb.reference)
    db_session.commit()
    return refs


def _ok_budget():
    return {
        "daily_spent": 0.0,
        "daily_remaining": 2.0,
        "daily_cap": 2.0,
        "weekly_spent": 0.0,
        "weekly_remaining": 8.0,
        "weekly_cap": 8.0,
        "allowed": True,
    }


def _exhausted_budget():
    return {
        "daily_spent": 2.0,
        "daily_remaining": 0.0,
        "daily_cap": 2.0,
        "weekly_spent": 8.0,
        "weekly_remaining": 0.0,
        "weekly_cap": 8.0,
        "allowed": False,
    }


# ---------------------------------------------------------------------------
# Fake agents
# ---------------------------------------------------------------------------


class FakeCluster:
    name = "cluster"

    def __init__(self, clusters):
        self._clusters = clusters

    def run(self, input: AgentInput) -> AgentOutput:
        return AgentOutput(
            data={"clusters": self._clusters},
            success=True,
            message="Clustered",
            tokens_used=0,
        )


class FakePrioritiser:
    name = "prioritise"

    def __init__(self, tasks):
        self._tasks = tasks

    def run(self, input: AgentInput) -> AgentOutput:
        return AgentOutput(
            data={"tasks": self._tasks},
            success=True,
            message="Prioritised",
            tokens_used=10,
        )


class FakeWriter:
    name = "write"

    def __init__(self, outputs=None):
        """*outputs* is a list of AgentOutput to return on successive calls."""
        self._outputs = list(outputs or [])
        self._call_count = 0

    def run(self, input: AgentInput) -> AgentOutput:
        idx = min(self._call_count, len(self._outputs) - 1)
        self._call_count += 1
        return self._outputs[idx]


class FakeReviewer:
    name = "review"

    def __init__(self, verdicts=None):
        """*verdicts* is a list of verdict strings to return successively."""
        self._verdicts = list(verdicts or ["approve"])
        self._call_count = 0

    def run(self, input: AgentInput) -> AgentOutput:
        idx = min(self._call_count, len(self._verdicts) - 1)
        self._call_count += 1
        verdict = self._verdicts[idx]
        return AgentOutput(
            data={
                "verdict": verdict,
                "comments": "LGTM" if verdict == "approve" else "Needs work",
                "issues": [],
            },
            success=True,
            message=f"Review: {verdict}",
            tokens_used=50,
        )


class FakeDeployer:
    name = "deploy"

    def __init__(self, success=True):
        self._success = success

    def run(self, input: AgentInput) -> AgentOutput:
        return AgentOutput(
            data={"branch": "agent/abc123", "deployed": self._success},
            success=self._success,
            message="Deployed" if self._success else "Deploy failed",
            tokens_used=0,
        )


def _writer_ok(summary="Updated code"):
    return AgentOutput(
        data={
            "changes": [{"path": "src/main.py", "action": "modify",
                         "content": "print('updated')"}],
            "summary": summary,
            "reasoning": "Because tests asked for it",
        },
        success=True,
        message=f"Writer produced changes: {summary}",
        tokens_used=300,
    )


def _writer_fail():
    return AgentOutput(
        data={"changes": [], "summary": "", "reasoning": ""},
        success=False,
        message="Budget exhausted",
        tokens_used=0,
    )


def _make_agents(clusters, tasks, writer_outputs=None, reviewer_verdicts=None,
                 deploy_success=True):
    """Build a complete fake agent registry."""
    return {
        "filter": MagicMock(),  # Not used in batch
        "cluster": FakeCluster(clusters),
        "prioritise": FakePrioritiser(tasks),
        "write": FakeWriter(writer_outputs or [_writer_ok()]),
        "review": FakeReviewer(reviewer_verdicts or ["approve"]),
        "deploy": FakeDeployer(deploy_success),
    }


# ---------------------------------------------------------------------------
# Tests — happy path
# ---------------------------------------------------------------------------


class TestBatchHappyPath:
    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_full_pipeline_marks_submissions_done(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        """End-to-end: pending → cluster → prioritise → write → review → deploy → done."""
        mock_budget.return_value = _ok_budget()

        clusters = [{"references": seed_pending, "documents": ["Feedback item 1", "Feedback item 2", "Feedback item 3"]}]
        tasks = [{"references": seed_pending, "summary": "Improve something",
                  "documents": ["Feedback item 1", "Feedback item 2", "Feedback item 3"],
                  "cluster_size": 3}]

        agents = _make_agents(clusters, tasks)
        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert result["tasks_attempted"] == 1
        assert result["tasks_completed"] == 1
        assert result["tasks_failed"] == 0

        # All submissions should be marked 'done'.
        for ref in seed_pending:
            fb = db_session.query(Feedback).filter_by(reference=ref).one()
            assert fb.status == FeedbackStatus.done
            assert fb.agent_notes is not None

    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_summary_includes_token_count(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        mock_budget.return_value = _ok_budget()

        tasks = [{"references": seed_pending, "summary": "Task 1",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
        )
        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        # Prioritiser (10) + writer (300) + reviewer (50) = 360
        assert result["total_tokens"] == 360

    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_backfill_embeddings_called(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        mock_budget.return_value = _ok_budget()
        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
        )
        run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        # Called once per pending submission.
        assert mock_embed.call_count == len(seed_pending)


# ---------------------------------------------------------------------------
# Tests — budget exhausted
# ---------------------------------------------------------------------------


class TestBatchBudget:
    @patch("pipeline.batch.check_budget")
    def test_budget_exceeded_exits_immediately(self, mock_budget, db_session, seed_pending):
        mock_budget.return_value = _exhausted_budget()

        result = run_batch(config=PIPELINE_CONFIG, agents=None, session=db_session)

        assert result["tasks_attempted"] == 0
        assert result["tasks_completed"] == 0

        # Submissions should remain pending.
        for ref in seed_pending:
            fb = db_session.query(Feedback).filter_by(reference=ref).one()
            assert fb.status == FeedbackStatus.pending

    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_budget_exhausted_mid_batch_stops_processing(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        """When budget runs out between tasks, processing stops."""
        call_count = 0

        def _budget_side_effect():
            nonlocal call_count
            call_count += 1
            # First call (initial check): OK.  Second call (before task): exhausted.
            if call_count <= 1:
                return _ok_budget()
            return _exhausted_budget()

        mock_budget.side_effect = _budget_side_effect

        tasks = [
            {"references": [seed_pending[0]], "summary": "Task 1",
             "documents": [], "cluster_size": 1},
            {"references": [seed_pending[1]], "summary": "Task 2",
             "documents": [], "cluster_size": 1},
        ]
        agents = _make_agents(
            [{"references": seed_pending[:1], "documents": []},
             {"references": seed_pending[1:2], "documents": []}],
            tasks,
        )

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        # Budget ran out before any task could be processed.
        assert result["tasks_attempted"] == 0


# ---------------------------------------------------------------------------
# Tests — no pending submissions
# ---------------------------------------------------------------------------


class TestBatchNoPending:
    @patch("pipeline.batch.check_budget")
    def test_no_pending_exits_early(self, mock_budget, db_session):
        mock_budget.return_value = _ok_budget()

        result = run_batch(config=PIPELINE_CONFIG, agents=None, session=db_session)

        assert result["tasks_attempted"] == 0
        assert result["tasks_completed"] == 0


# ---------------------------------------------------------------------------
# Tests — review rejection and retry loop
# ---------------------------------------------------------------------------


class TestBatchReviewRetry:
    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_review_reject_then_approve_on_retry(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        """Reviewer rejects first, then approves on retry."""
        mock_budget.return_value = _ok_budget()

        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
            writer_outputs=[_writer_ok(), _writer_ok("Revised code")],
            reviewer_verdicts=["reject", "approve"],
        )

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert result["tasks_completed"] == 1
        # Writer called twice, reviewer called twice.
        assert agents["write"]._call_count == 2
        assert agents["review"]._call_count == 2

    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_review_rejects_all_retries_leaves_pending(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        """Reviewer rejects on every attempt — submissions stay pending."""
        mock_budget.return_value = _ok_budget()

        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
            writer_outputs=[_writer_ok(), _writer_ok(), _writer_ok()],
            reviewer_verdicts=["reject", "reject", "reject"],
        )

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert result["tasks_completed"] == 0
        assert result["tasks_failed"] == 1

        # max_writer_retries=2 means initial + 2 retries = 3 attempts.
        assert agents["write"]._call_count == 3
        assert agents["review"]._call_count == 3

        for ref in seed_pending:
            fb = db_session.query(Feedback).filter_by(reference=ref).one()
            assert fb.status == FeedbackStatus.pending
            assert "rejected" in fb.agent_notes.lower()

    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_reviewer_feedback_passed_to_writer_on_retry(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        """On retry, the reviewer's comments should appear in the writer's context."""
        mock_budget.return_value = _ok_budget()

        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]

        # Track what the writer receives.
        writer_contexts = []

        class SpyWriter:
            name = "write"
            _call_count = 0

            def run(self, input: AgentInput) -> AgentOutput:
                self._call_count += 1
                writer_contexts.append(input.context.copy())
                return _writer_ok()

        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
            reviewer_verdicts=["reject", "approve"],
        )
        agents["write"] = SpyWriter()

        run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        # First call: no reviewer feedback.
        assert "reviewer_feedback" not in writer_contexts[0]
        # Second call: reviewer feedback present.
        assert writer_contexts[1]["reviewer_feedback"] == "Needs work"


# ---------------------------------------------------------------------------
# Tests — deployment failure
# ---------------------------------------------------------------------------


class TestBatchDeployFailure:
    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_deploy_failure_leaves_submissions_pending(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        mock_budget.return_value = _ok_budget()

        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
            deploy_success=False,
        )

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert result["tasks_completed"] == 0
        assert result["tasks_failed"] == 1

        for ref in seed_pending:
            fb = db_session.query(Feedback).filter_by(reference=ref).one()
            assert fb.status == FeedbackStatus.pending
            assert "deploy failed" in fb.agent_notes.lower()


# ---------------------------------------------------------------------------
# Tests — writer failure
# ---------------------------------------------------------------------------


class TestBatchWriterFailure:
    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_writer_failure_leaves_pending(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        mock_budget.return_value = _ok_budget()

        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
            writer_outputs=[_writer_fail()],
        )

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert result["tasks_completed"] == 0
        assert result["tasks_failed"] == 1

        for ref in seed_pending:
            fb = db_session.query(Feedback).filter_by(reference=ref).one()
            assert fb.status == FeedbackStatus.pending


# ---------------------------------------------------------------------------
# Tests — cluster failure
# ---------------------------------------------------------------------------


class TestBatchClusterFailure:
    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_cluster_failure_exits_gracefully(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        mock_budget.return_value = _ok_budget()

        class FailCluster:
            name = "cluster"
            def run(self, input: AgentInput) -> AgentOutput:
                return AgentOutput(
                    data={"clusters": []}, success=False,
                    message="ChromaDB down", tokens_used=0,
                )

        agents = _make_agents([], [])
        agents["cluster"] = FailCluster()

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert result["tasks_attempted"] == 0


# ---------------------------------------------------------------------------
# Tests — multiple tasks
# ---------------------------------------------------------------------------


class TestBatchMultipleTasks:
    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_processes_multiple_tasks(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        """Two tasks: one succeeds, one fails deployment."""
        mock_budget.return_value = _ok_budget()

        clusters = [
            {"references": [seed_pending[0]], "documents": ["Feedback item 1"]},
            {"references": [seed_pending[1]], "documents": ["Feedback item 2"]},
        ]
        tasks = [
            {"references": [seed_pending[0]], "summary": "Task A",
             "documents": ["Feedback item 1"], "cluster_size": 1},
            {"references": [seed_pending[1]], "summary": "Task B",
             "documents": ["Feedback item 2"], "cluster_size": 1},
        ]

        # Deployer succeeds for task A, fails for task B.
        deploy_call = 0

        class AlternatingDeployer:
            name = "deploy"
            def run(self, input: AgentInput) -> AgentOutput:
                nonlocal deploy_call
                deploy_call += 1
                if deploy_call == 1:
                    return AgentOutput(
                        data={"branch": "agent/aaa", "deployed": True},
                        success=True, message="Deployed", tokens_used=0,
                    )
                return AgentOutput(
                    data={"branch": "agent/bbb", "deployed": False},
                    success=False, message="Pipeline failed", tokens_used=0,
                )

        agents = _make_agents(clusters, tasks,
                              writer_outputs=[_writer_ok("A"), _writer_ok("B")])
        agents["deploy"] = AlternatingDeployer()

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert result["tasks_attempted"] == 2
        assert result["tasks_completed"] == 1
        assert result["tasks_failed"] == 1

        fb_a = db_session.query(Feedback).filter_by(reference=seed_pending[0]).one()
        assert fb_a.status == FeedbackStatus.done

        fb_b = db_session.query(Feedback).filter_by(reference=seed_pending[1]).one()
        assert fb_b.status == FeedbackStatus.pending


# ---------------------------------------------------------------------------
# Tests — summary structure
# ---------------------------------------------------------------------------


class TestBatchSummary:
    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_summary_has_expected_keys(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        mock_budget.return_value = _ok_budget()

        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
        )

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        assert "tasks_attempted" in result
        assert "tasks_completed" in result
        assert "tasks_failed" in result
        assert "total_tokens" in result
        assert "budget_remaining" in result
        assert "details" in result
        assert isinstance(result["details"], list)
        assert len(result["details"]) == 1

        detail = result["details"][0]
        assert "references" in detail
        assert "outcome" in detail
        assert "tokens" in detail

    @patch("pipeline.batch.store_feedback_embedding", return_value=True)
    @patch("pipeline.batch.check_budget")
    def test_budget_remaining_in_summary(
        self, mock_budget, mock_embed, db_session, seed_pending,
    ):
        mock_budget.return_value = _ok_budget()
        tasks = [{"references": seed_pending, "summary": "Task",
                  "documents": [], "cluster_size": 3}]
        agents = _make_agents(
            [{"references": seed_pending, "documents": []}],
            tasks,
        )

        result = run_batch(config=PIPELINE_CONFIG, agents=agents, session=db_session)

        budget = result["budget_remaining"]
        assert "daily_remaining" in budget
        assert "weekly_remaining" in budget
        assert "allowed" in budget
