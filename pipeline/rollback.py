"""Rollback helper — resets feedback statuses for a reverted pipeline release.

Given a merge-commit hash (of the form ``Merge agent/<branch>: <summary>``),
this module:

1. Parses the agent branch name out of the commit message.
2. Searches ``pipeline/data/runs/`` for a run JSON whose deploy branch matches.
3. Resets the feedback references found in that JSON from ``done`` back to
   ``pending``, so the pipeline will pick them up again on the next run.

CLI usage
---------
    python -m pipeline.rollback <merge-commit-hash>
    python -m pipeline.rollback <merge-commit-hash> --db-url sqlite:///path/to/db
    python -m pipeline.rollback <merge-commit-hash> --dry-run   # preview only
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Pattern that matches merge commit messages created by the deployer agent.
_MERGE_MSG_RE = re.compile(r"^Merge (agent/[0-9a-f]+):")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def get_commit_message(commit_hash: str, repo_path: str = ".") -> str:
    """Return the subject line of *commit_hash*."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%s", commit_hash],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"git log failed for {commit_hash!r}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def parse_agent_branch(commit_message: str) -> Optional[str]:
    """Extract the agent branch name from a deployer merge commit message.

    Returns ``None`` if the message doesn't match the expected pattern.
    """
    m = _MERGE_MSG_RE.match(commit_message)
    return m.group(1) if m else None


def find_run_json(branch_name: str, runs_dir: Path) -> Optional[Path]:
    """Return the path to the run JSON whose deploy branch matches *branch_name*.

    Searches all ``*.json`` files in *runs_dir* and returns the first match,
    or ``None`` if no match is found.
    """
    if not runs_dir.is_dir():
        return None
    for json_path in sorted(runs_dir.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        deploy = payload.get("deploy") or {}
        if deploy.get("branch") == branch_name:
            return json_path
    return None


def extract_references(run_json_path: Path) -> list[str]:
    """Return the feedback reference list from a run JSON file."""
    payload = json.loads(run_json_path.read_text())
    return payload.get("references", [])


def reset_feedback_to_pending(
    references: list[str],
    db_url: str,
    *,
    dry_run: bool = False,
) -> int:
    """Reset the given feedback references from ``done`` to ``pending``.

    Only rows that are currently ``done`` are touched.  Returns the number of
    rows actually updated.
    """
    if not references:
        return 0

    # Import lazily so the module can be imported without the full backend
    # stack available (e.g. during unit tests with a mock DB).
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Inline import to avoid circular imports at module level.
    import sys as _sys
    _project_root = str(Path(__file__).resolve().parents[1])
    if _project_root not in _sys.path:
        _sys.path.insert(0, _project_root)

    from backend.app.database import Base
    from backend.app.models import Feedback, FeedbackStatus

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        rows = (
            session.query(Feedback)
            .filter(
                Feedback.reference.in_(references),
                Feedback.status == FeedbackStatus.done,
            )
            .all()
        )
        if dry_run:
            return len(rows)
        for row in rows:
            row.status = FeedbackStatus.pending
            row.agent_notes = (
                (row.agent_notes or "") + " [rolled back]"
            ).strip()
        session.commit()
        return len(rows)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# High-level rollback DB step
# ---------------------------------------------------------------------------


def rollback_db_for_commit(
    commit_hash: str,
    *,
    repo_path: str = ".",
    db_url: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Identify the feedback refs for *commit_hash* and reset them to pending.

    Returns a result dict with keys:
      - ``branch``      : agent branch name parsed from the commit (or None)
      - ``run_json``    : path to the matched run JSON (or None)
      - ``references``  : list of feedback refs found
      - ``reset_count`` : number of DB rows actually updated
      - ``warning``     : human-readable warning if matching failed, else None
    """
    result: dict = {
        "branch": None,
        "run_json": None,
        "references": [],
        "reset_count": 0,
        "warning": None,
    }

    # 1. Parse branch from commit message.
    try:
        msg = get_commit_message(commit_hash, repo_path=repo_path)
    except ValueError as exc:
        result["warning"] = str(exc)
        return result

    branch = parse_agent_branch(msg)
    result["branch"] = branch
    if branch is None:
        result["warning"] = (
            f"Commit {commit_hash[:12]} does not look like an agent merge "
            f"(message: {msg!r}). DB not updated."
        )
        return result

    # 2. Find matching run JSON.
    runs_dir = Path(repo_path) / "pipeline" / "data" / "runs"
    json_path = find_run_json(branch, runs_dir)
    if json_path is None:
        result["warning"] = (
            f"No run JSON found for branch {branch!r} in {runs_dir}. "
            "DB not updated — you may need to reset feedback statuses manually."
        )
        return result

    result["run_json"] = str(json_path)

    # 3. Extract and reset references.
    refs = extract_references(json_path)
    result["references"] = refs
    if not refs:
        result["warning"] = (
            f"Run JSON {json_path.name} contains no feedback references. "
            "DB not updated."
        )
        return result

    if db_url is None:
        from pipeline.config import PIPELINE_CONFIG
        db_url = PIPELINE_CONFIG["db_url"]

    count = reset_feedback_to_pending(refs, db_url, dry_run=dry_run)
    result["reset_count"] = count
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Reset feedback statuses for a reverted pipeline release. "
            "Expects the hash of the merge commit that was reverted."
        ),
    )
    parser.add_argument(
        "commit_hash",
        metavar="COMMIT",
        help="Hash of the agent merge commit that was reverted.",
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository root (default: current directory).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="SQLAlchemy database URL (default: from PIPELINE_CONFIG).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be reset without making any DB changes.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    result = rollback_db_for_commit(
        args.commit_hash,
        repo_path=args.repo_path,
        db_url=args.db_url,
        dry_run=args.dry_run,
    )

    if result["warning"]:
        print(f"warning: {result['warning']}", file=sys.stderr)

    branch = result["branch"] or "(unknown)"
    refs = result["references"]
    count = result["reset_count"]
    run_json = result["run_json"] or "(not found)"

    print(f"  Agent branch : {branch}")
    print(f"  Run JSON     : {run_json}")
    print(f"  References   : {', '.join(refs) if refs else '(none)'}")
    if args.dry_run:
        print(f"  Would reset  : {count} feedback row(s) to 'pending'")
    else:
        print(f"  Reset        : {count} feedback row(s) to 'pending'")

    # Exit 0 even if there was a warning — the git revert already succeeded.
    sys.exit(0)


if __name__ == "__main__":
    main()
