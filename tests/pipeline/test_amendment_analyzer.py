"""Tests for the constitutional amendment analyzer."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from pipeline.utils.amendment_analyzer import (  # noqa: E402
    _load_proposals,
    _render_concerns_md,
    analyze_and_propose,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_run_json(
    refs: list[str],
    summary: str,
    outcome: str = "deploy_failed",
    pipeline_stdout: str = "",
    minutes_ago: int = 0,
) -> dict:
    """Build a synthetic run JSON dict."""
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y-%m-%dT%H-%M-%SZ")
    return {
        "timestamp": ts_str,
        "references": refs,
        "summary": summary,
        "outcome": outcome,
        "writer": None,
        "reviewer": None,
        "deploy": {
            "branch": "agent/test",
            "deployed": False,
            "pipeline_stdout": pipeline_stdout,
            "pipeline_stderr": "",
        },
    }


PYTEST_ESSENTIAL_FAIL = """\
=== Step 5/9: Essential Tests (Backend) ===
FAILED tests/essential/test_api_essentials.py::TestHealthCheck::test_health_endpoint_returns_ok
"""

PYTEST_PIPELINE_FAIL = """\
=== Step 8/9: Pipeline Tests ===
FAILED tests/pipeline/test_registry.py::test_all_agents_have_name
"""


# ── Tests ─────────────────────────────────────────────────────────────


class TestLoadProposals:
    def test_returns_empty_for_missing_file(self, tmp_path):
        result = _load_proposals(str(tmp_path / "nope.json"))
        assert result == []

    def test_returns_empty_for_corrupt_file(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        result = _load_proposals(str(bad))
        assert result == []

    def test_loads_existing_proposals(self, tmp_path):
        f = tmp_path / "proposals.json"
        data = [{"id": "amend-001", "status": "pending"}]
        f.write_text(json.dumps(data))
        result = _load_proposals(str(f))
        assert len(result) == 1
        assert result[0]["id"] == "amend-001"


class TestRenderConcernsMd:
    def test_renders_no_proposals(self, tmp_path):
        md_path = str(tmp_path / "concerns.md")
        _render_concerns_md([], md_path)
        content = Path(md_path).read_text()
        assert "No pending amendment proposals" in content

    def test_renders_pending_proposal(self, tmp_path):
        md_path = str(tmp_path / "concerns.md")
        proposals = [{
            "id": "amend-20260321-001",
            "status": "pending",
            "test_file": "tests/essential/test_api_essentials.py",
            "test_name": "TestHealthCheck::test_health_endpoint_returns_ok",
            "category": "essential",
            "distinct_task_count": 3,
            "first_seen": "2026-03-10",
            "last_seen": "2026-03-21",
            "error_snippet": "assert 404 == 200",
            "failing_task_summaries": ["Task A", "Task B"],
        }]
        _render_concerns_md(proposals, md_path)
        content = Path(md_path).read_text()
        assert "amend-20260321-001" in content
        assert "essential" in content
        assert "Task A" in content

    def test_skips_dismissed_proposals(self, tmp_path):
        md_path = str(tmp_path / "concerns.md")
        proposals = [{
            "id": "amend-001",
            "status": "dismissed",
            "test_file": "tests/essential/foo.py",
            "test_name": "bar",
            "category": "essential",
            "distinct_task_count": 5,
            "first_seen": "2026-03-10",
            "last_seen": "2026-03-21",
        }]
        _render_concerns_md(proposals, md_path)
        content = Path(md_path).read_text()
        assert "No pending amendment proposals" in content


class TestAnalyzeAndPropose:
    def _write_runs(self, runs_dir: Path, runs: list[dict]):
        runs_dir.mkdir(parents=True, exist_ok=True)
        for i, run in enumerate(runs):
            ts = run.get("timestamp", f"2026-03-21T00-{i:02d}-00Z")
            ref = run["references"][0] if run["references"] else "unknown"
            path = runs_dir / f"{ts}_{ref}.json"
            path.write_text(json.dumps(run))

    def test_no_proposals_below_threshold(self, tmp_path):
        runs_dir = tmp_path / "runs"
        # Only 2 distinct tasks fail the same test — below threshold of 3.
        runs = [
            _make_run_json(["LW-001"], "Task A", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-002"], "Task B", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        result = analyze_and_propose(
            str(runs_dir),
            str(tmp_path / "proposals.json"),
            str(tmp_path / "concerns.md"),
            threshold=3,
        )
        assert result == []

    def test_creates_proposal_at_threshold(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs = [
            _make_run_json(["LW-001"], "Task A", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-002"], "Task B", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-003"], "Task C", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        result = analyze_and_propose(
            str(runs_dir),
            str(tmp_path / "proposals.json"),
            str(tmp_path / "concerns.md"),
            threshold=3,
        )
        assert len(result) == 1
        p = result[0]
        assert p["test_file"] == "tests/essential/test_api_essentials.py"
        assert p["status"] == "pending"
        assert p["distinct_task_count"] == 3
        assert p["category"] == "essential"

    def test_same_task_retries_count_as_one(self, tmp_path):
        runs_dir = tmp_path / "runs"
        # Same refs (LW-001) fails 3 times — only 1 distinct task.
        runs = [
            _make_run_json(["LW-001"], "Task A retry 1", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-001"], "Task A retry 2", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-001"], "Task A retry 3", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        result = analyze_and_propose(
            str(runs_dir),
            str(tmp_path / "proposals.json"),
            str(tmp_path / "concerns.md"),
            threshold=3,
        )
        assert result == []

    def test_dismissed_proposals_not_recreated(self, tmp_path):
        runs_dir = tmp_path / "runs"
        proposals_path = tmp_path / "proposals.json"

        runs = [
            _make_run_json(["LW-001"], "A", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-002"], "B", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-003"], "C", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        # Pre-seed a dismissed proposal.
        dismissed = [{
            "id": "amend-old-001",
            "status": "dismissed",
            "test_file": "tests/essential/test_api_essentials.py",
            "test_name": "TestHealthCheck::test_health_endpoint_returns_ok",
        }]
        proposals_path.write_text(json.dumps(dismissed))

        result = analyze_and_propose(
            str(runs_dir),
            str(proposals_path),
            str(tmp_path / "concerns.md"),
            threshold=3,
        )
        assert result == []

    def test_ignores_successful_runs(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs = [
            _make_run_json(["LW-001"], "A", outcome="done", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-002"], "B", outcome="done", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-003"], "C", outcome="done", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        result = analyze_and_propose(
            str(runs_dir),
            str(tmp_path / "proposals.json"),
            str(tmp_path / "concerns.md"),
            threshold=3,
        )
        assert result == []

    def test_ignores_non_protected_test_failures(self, tmp_path):
        runs_dir = tmp_path / "runs"
        other_fail = "=== Step 7/9: Backend Tests ===\nFAILED tests/backend/test_api.py::TestFoo::test_bar\n"
        runs = [
            _make_run_json(["LW-001"], "A", pipeline_stdout=other_fail),
            _make_run_json(["LW-002"], "B", pipeline_stdout=other_fail),
            _make_run_json(["LW-003"], "C", pipeline_stdout=other_fail),
        ]
        self._write_runs(runs_dir, runs)

        result = analyze_and_propose(
            str(runs_dir),
            str(tmp_path / "proposals.json"),
            str(tmp_path / "concerns.md"),
            threshold=3,
        )
        assert result == []

    def test_concerns_md_created(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs = [
            _make_run_json(["LW-001"], "A", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-002"], "B", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-003"], "C", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        concerns_path = tmp_path / "concerns.md"
        analyze_and_propose(
            str(runs_dir),
            str(tmp_path / "proposals.json"),
            str(concerns_path),
            threshold=3,
        )
        assert concerns_path.exists()
        content = concerns_path.read_text()
        assert "Pending Amendment Proposals" in content
        assert "test_api_essentials.py" in content

    def test_proposals_json_persisted(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs = [
            _make_run_json(["LW-001"], "A", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-002"], "B", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-003"], "C", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        proposals_path = tmp_path / "proposals.json"
        analyze_and_propose(
            str(runs_dir),
            str(proposals_path),
            str(tmp_path / "concerns.md"),
            threshold=3,
        )
        saved = json.loads(proposals_path.read_text())
        assert len(saved) == 1
        assert saved[0]["status"] == "pending"

    def test_updates_existing_pending_proposal(self, tmp_path):
        runs_dir = tmp_path / "runs"
        proposals_path = tmp_path / "proposals.json"

        runs = [
            _make_run_json(["LW-001"], "A", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-002"], "B", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-003"], "C", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
            _make_run_json(["LW-004"], "D", pipeline_stdout=PYTEST_ESSENTIAL_FAIL),
        ]
        self._write_runs(runs_dir, runs)

        # First run creates the proposal.
        analyze_and_propose(
            str(runs_dir), str(proposals_path),
            str(tmp_path / "concerns.md"), threshold=3,
        )

        # Second run should update, not duplicate.
        result = analyze_and_propose(
            str(runs_dir), str(proposals_path),
            str(tmp_path / "concerns.md"), threshold=3,
        )
        assert result == []  # No NEW proposals
        saved = json.loads(proposals_path.read_text())
        assert len(saved) == 1
        assert saved[0]["distinct_task_count"] == 4

    def test_empty_runs_dir(self, tmp_path):
        result = analyze_and_propose(
            str(tmp_path / "nonexistent"),
            str(tmp_path / "proposals.json"),
            str(tmp_path / "concerns.md"),
        )
        assert result == []
