"""Tests for the CI/CD pipeline output failure parser."""

import sys
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from pipeline.utils.failure_parser import parse_test_failures  # noqa: E402


# ── Sample pipeline outputs ──────────────────────────────────────────

PYTEST_FAILURE_OUTPUT = """\
=== Step 5/9: Essential Tests (Backend) ===
============================= test session starts ==============================
collected 1 item

tests/essential/test_api_essentials.py F                                 [100%]

=================================== FAILURES ===================================
________ TestHealthCheck.test_health_endpoint_returns_ok ________

    def test_health_endpoint_returns_ok(self, client):
        resp = client.get("/api/health")
>       assert resp.status_code == 200
E       AssertionError: assert 404 == 200

tests/essential/test_api_essentials.py:107: AssertionError
=========================== short test summary info ============================
FAILED tests/essential/test_api_essentials.py::TestHealthCheck::test_health_endpoint_returns_ok
============================== 1 failed in 0.42s ===============================
"""

VITEST_FAILURE_OUTPUT = """\
=== Step 4/9: Essential Tests (Frontend) ===

 RUN  v4.0.18 /home/user/the-lost-world/frontend

 ❯ ../tests/essential/test_simulation_essentials.ts (1)
   ❯ Simulation essentials (1)
     × all entities stay within plateau bounds after 100 ticks

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

 FAIL  tests/essential/test_simulation_essentials.ts > Simulation essentials > all entities stay within plateau bounds after 100 ticks
AssertionError: expected -5 to be greater than or equal to 20

 Test Files  1 failed (1)
      Tests  1 failed (1)
"""

MULTI_FAILURE_OUTPUT = """\
=== Step 5/9: Essential Tests (Backend) ===
FAILED tests/essential/test_api_essentials.py::TestHealthCheck::test_health_endpoint_returns_ok
=== Step 8/9: Pipeline Tests ===
FAILED tests/pipeline/test_batch.py::TestRunBatch::test_empty_queue_returns_early
FAILED tests/pipeline/test_registry.py::test_all_agents_have_name
"""

PASSING_OUTPUT = """\
=== Step 4/9: Essential Tests (Frontend) ===
 ✓ tests/essential/test_simulation_essentials.ts (1)
=== Step 5/9: Essential Tests (Backend) ===
1 passed in 0.3s
=== Step 9/9: Build Frontend ===
=== All checks passed ===
"""

NON_ESSENTIAL_FAILURE = """\
=== Step 7/9: Backend Tests ===
FAILED tests/backend/test_api.py::TestCreateFeedback::test_create_feedback
"""


# ── Tests ─────────────────────────────────────────────────────────────


class TestParsePytestFailures:
    def test_extracts_single_pytest_failure(self):
        failures = parse_test_failures(PYTEST_FAILURE_OUTPUT, "")
        assert len(failures) == 1
        f = failures[0]
        assert f["test_file"] == "tests/essential/test_api_essentials.py"
        assert f["test_name"] == "TestHealthCheck::test_health_endpoint_returns_ok"
        assert f["category"] == "essential"
        assert f["pipeline_step"] == "Step 5/9: Essential Tests (Backend)"

    def test_error_snippet_present(self):
        failures = parse_test_failures(PYTEST_FAILURE_OUTPUT, "")
        assert failures[0]["error_snippet"]  # non-empty


class TestParseVitestFailures:
    def test_extracts_vitest_failure(self):
        failures = parse_test_failures(VITEST_FAILURE_OUTPUT, "")
        assert len(failures) == 1
        f = failures[0]
        assert f["test_file"] == "tests/essential/test_simulation_essentials.ts"
        assert "all entities stay within plateau bounds" in f["test_name"]
        assert f["category"] == "essential"
        assert f["pipeline_step"] == "Step 4/9: Essential Tests (Frontend)"


class TestMultipleFailures:
    def test_extracts_failures_across_steps(self):
        failures = parse_test_failures(MULTI_FAILURE_OUTPUT, "")
        assert len(failures) == 3
        files = {f["test_file"] for f in failures}
        assert "tests/essential/test_api_essentials.py" in files
        assert "tests/pipeline/test_batch.py" in files
        assert "tests/pipeline/test_registry.py" in files

    def test_categories_correct(self):
        failures = parse_test_failures(MULTI_FAILURE_OUTPUT, "")
        cats = {f["test_file"]: f["category"] for f in failures}
        assert cats["tests/essential/test_api_essentials.py"] == "essential"
        assert cats["tests/pipeline/test_batch.py"] == "pipeline"
        assert cats["tests/pipeline/test_registry.py"] == "pipeline"


class TestPassingOutput:
    def test_no_failures_when_passing(self):
        failures = parse_test_failures(PASSING_OUTPUT, "")
        assert failures == []


class TestNonEssentialFailures:
    def test_classifies_backend_tests_as_other(self):
        failures = parse_test_failures(NON_ESSENTIAL_FAILURE, "")
        assert len(failures) == 1
        assert failures[0]["category"] == "other"


class TestDeduplication:
    def test_same_test_not_reported_twice(self):
        doubled = PYTEST_FAILURE_OUTPUT + "\n" + PYTEST_FAILURE_OUTPUT
        failures = parse_test_failures(doubled, "")
        assert len(failures) == 1


class TestStderrHandling:
    def test_failures_in_stderr_also_parsed(self):
        failures = parse_test_failures("", PYTEST_FAILURE_OUTPUT)
        assert len(failures) == 1
        assert failures[0]["test_file"] == "tests/essential/test_api_essentials.py"
