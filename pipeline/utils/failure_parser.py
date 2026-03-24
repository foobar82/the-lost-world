"""Parse CI/CD pipeline output to identify which tests failed.

The pipeline script (scripts/pipeline.sh) runs numbered steps with headers
like ``=== Step 4/9: Essential Tests (Frontend) ===``.  This module parses
the combined stdout/stderr to extract structured information about each
individual test failure.

No LLM calls — pure regex parsing.
"""

import re

# Regex for pipeline step headers emitted by scripts/pipeline.sh.
_STEP_HEADER_RE = re.compile(r"=== (Step \d+/\d+: .+?) ===")

# Pytest FAILED line:  FAILED tests/essential/test_api_essentials.py::TestHealthCheck::test_health_endpoint_returns_ok
_PYTEST_FAILED_RE = re.compile(
    r"FAILED\s+(tests/\S+\.py)::(\S+)"
)

# Vitest FAIL line (appears in summary):  FAIL  tests/essential/test_app_essentials.tsx > App essentials > renders without crashing
_VITEST_FAIL_RE = re.compile(
    r"FAIL\s+(tests/\S+\.tsx?)\s+>\s+(.+)"
)

# Vitest AssertionError block sometimes names the file differently.
_VITEST_ASSERT_RE = re.compile(
    r"AssertionError.*?(?:at|in)\s+(tests/\S+\.tsx?)",
)


def _classify(test_file: str) -> str:
    """Classify a test file path as 'essential', 'pipeline', or 'other'."""
    if test_file.startswith("tests/essential/"):
        return "essential"
    if test_file.startswith("tests/pipeline/"):
        return "pipeline"
    return "other"


def _extract_error_snippet(text: str, match_pos: int, max_len: int = 200) -> str:
    """Extract a short error snippet around a match position."""
    start = max(0, match_pos - 100)
    end = min(len(text), match_pos + max_len)
    snippet = text[start:end].strip()
    # Try to find an assertion or error line within the snippet.
    for line in snippet.splitlines():
        line = line.strip()
        if any(kw in line for kw in ("AssertionError", "AssertionError", "assert ", "Error:", "Expected", "Received")):
            return line[:max_len]
    return snippet[:max_len]


def parse_test_failures(stdout: str, stderr: str) -> list[dict]:
    """Parse pipeline output and return structured test failure information.

    Parameters
    ----------
    stdout : str
        Captured stdout from ``scripts/pipeline.sh``.
    stderr : str
        Captured stderr from ``scripts/pipeline.sh``.

    Returns
    -------
    list[dict]
        Each dict contains:
        - ``test_file``: relative path to the test file
        - ``test_name``: test function/class name
        - ``pipeline_step``: which pipeline step header preceded the failure
        - ``category``: ``"essential"``, ``"pipeline"``, or ``"other"``
        - ``error_snippet``: short excerpt of the error message
    """
    combined = stdout + "\n" + stderr
    failures: list[dict] = []
    seen: set[tuple[str, str]] = set()

    # Find all step headers and their positions to determine which step
    # a failure belongs to.
    step_spans: list[tuple[str, int]] = []
    for m in _STEP_HEADER_RE.finditer(combined):
        step_spans.append((m.group(1), m.start()))

    def _find_step(pos: int) -> str:
        """Return the step header active at a given position."""
        current_step = ""
        for step_name, step_pos in step_spans:
            if step_pos <= pos:
                current_step = step_name
            else:
                break
        return current_step

    # Pytest failures.
    for m in _PYTEST_FAILED_RE.finditer(combined):
        test_file = m.group(1)
        test_name = m.group(2)
        key = (test_file, test_name)
        if key in seen:
            continue
        seen.add(key)
        failures.append({
            "test_file": test_file,
            "test_name": test_name,
            "pipeline_step": _find_step(m.start()),
            "category": _classify(test_file),
            "error_snippet": _extract_error_snippet(combined, m.start()),
        })

    # Vitest failures.
    for m in _VITEST_FAIL_RE.finditer(combined):
        test_file = m.group(1)
        test_name = m.group(2).strip()
        key = (test_file, test_name)
        if key in seen:
            continue
        seen.add(key)
        failures.append({
            "test_file": test_file,
            "test_name": test_name,
            "pipeline_step": _find_step(m.start()),
            "category": _classify(test_file),
            "error_snippet": _extract_error_snippet(combined, m.start()),
        })

    return failures
