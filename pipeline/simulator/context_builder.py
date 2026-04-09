"""Context builder for the user emulation agent.

Assembles the three information sources the simulator uses to understand
the current state of the app:

1. Simulation source files — what entities and behaviours exist
2. Recent git log — what has changed recently
3. Recently completed feedback — what has already been requested and built

The simulator is constrained to what a real user can observe: frontend
rendering code and visible change history. It does not read backend
internals, pipeline logs, or test output.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Frontend files that describe what a user sees.
_SIMULATION_FILES = [
    "frontend/src/simulation/types.ts",
    "frontend/src/simulation/simulation.ts",
    "frontend/src/components/EcosystemCanvas.tsx",
]

# Character budget for source files — keeps prompt size manageable.
_MAX_SOURCE_CHARS = 8000


def build_context(repo_path: str, api_base_url: str) -> dict:
    """Return a dict with source_summary, recent_changes, recently_completed."""
    return {
        "source_summary": _read_simulation_source(repo_path),
        "recent_changes": _git_log(repo_path, n=15),
        "recently_completed": _fetch_done_feedback(api_base_url, limit=10),
    }


def _read_simulation_source(repo_path: str) -> str:
    """Read key frontend simulation files and return them as a labelled string."""
    root = Path(repo_path)
    sections: list[str] = []
    total_chars = 0

    for rel_path in _SIMULATION_FILES:
        path = root / rel_path
        if not path.exists():
            logger.debug("Simulation source file not found: %s", rel_path)
            continue

        content = path.read_text(encoding="utf-8")

        # Trim if we're approaching the budget.
        remaining = _MAX_SOURCE_CHARS - total_chars
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n... (truncated)"

        sections.append(f"### {rel_path}\n```\n{content}\n```")
        total_chars += len(content)

    if not sections:
        return "(No simulation source files found)"

    return "\n\n".join(sections)


def _git_log(repo_path: str, n: int = 15) -> str:
    """Return the last n git log entries as a plain string."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={n}", "--oneline", "--no-decorate"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        log = result.stdout.strip()
        return log if log else "(No git history found)"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.warning("Could not read git log from %s", repo_path)
        return "(Git log unavailable)"


def _fetch_done_feedback(api_base_url: str, limit: int = 10) -> str:
    """Fetch recently completed feedback items from the backend API."""
    url = f"{api_base_url}/api/feedback"
    try:
        response = httpx.get(
            url,
            params={"status": "done", "limit": limit},
            timeout=10,
        )
        response.raise_for_status()
        items = response.json()

        if not items:
            return "(No completed feedback items yet)"

        lines = []
        for item in items:
            ref = item.get("reference", "?")
            content = item.get("content", "")
            notes = item.get("agent_notes", "")
            line = f"- [{ref}] {content}"
            if notes:
                line += f" → {notes}"
            lines.append(line)

        return "\n".join(lines)

    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        logger.warning("Could not fetch done feedback from %s", url)
        return "(Completed feedback unavailable)"
