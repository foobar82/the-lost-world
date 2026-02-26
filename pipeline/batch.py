"""Batch orchestrator — runs the daily agent pipeline.

Steps:
  1. Load config, check budget
  2. Get pending submissions from SQLite
  3. Backfill any missing embeddings
  4. Cluster → prioritise → for each task: write → review (retry loop) → deploy
  5. Update submission statuses throughout
  6. Log summary
"""

import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure the project root is importable.
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.app.models import Feedback, FeedbackStatus  # noqa: E402
from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.budget import check_budget  # noqa: E402
from pipeline.config import PIPELINE_CONFIG  # noqa: E402
from pipeline.registry import AGENTS  # noqa: E402
from pipeline.utils.embeddings import store_feedback_embedding  # noqa: E402

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────


def _get_db_session(db_url: str) -> Session:
    """Create a one-off SQLAlchemy session for the batch run."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine)()


def _get_pending_submissions(session: Session) -> list[Feedback]:
    """Return all feedback rows with status 'pending'."""
    return (
        session.query(Feedback)
        .filter(Feedback.status == FeedbackStatus.pending)
        .order_by(Feedback.created_at)
        .all()
    )


def _update_status(
    session: Session,
    references: list[str],
    status: FeedbackStatus,
    agent_notes: str | None = None,
) -> None:
    """Bulk-update the status (and optionally agent_notes) for a list of references."""
    rows = session.query(Feedback).filter(Feedback.reference.in_(references)).all()
    for row in rows:
        row.status = status
        if agent_notes is not None:
            row.agent_notes = agent_notes
    session.commit()


def _backfill_embeddings(
    submissions: list[Feedback], ollama_url: str,
) -> int:
    """Generate embeddings for any submissions that are missing from ChromaDB.

    Returns the number of embeddings successfully backfilled.
    """
    backfilled = 0
    for fb in submissions:
        ok = store_feedback_embedding(fb.reference, fb.content, ollama_url=ollama_url)
        if ok:
            backfilled += 1
    return backfilled


# ── main batch logic ──────────────────────────────────────────────────


def run_batch(  # noqa: C901 — orchestration is inherently sequential
    config: dict | None = None,
    agents: dict | None = None,
    session: Session | None = None,
) -> dict:
    """Execute a single batch run.

    Parameters
    ----------
    config : dict, optional
        Override ``PIPELINE_CONFIG`` (useful for tests).
    agents : dict, optional
        Override the default agent registry (useful for tests).
    session : Session, optional
        Provide an existing DB session (useful for tests).

    Returns
    -------
    dict
        Summary of the batch run.
    """
    cfg = config or PIPELINE_CONFIG
    agent_map = agents or AGENTS
    owns_session = session is None

    summary = {
        "tasks_attempted": 0,
        "tasks_completed": 0,
        "tasks_failed": 0,
        "total_tokens": 0,
        "budget_remaining": {},
        "details": [],
    }

    # ── 1. Check budget ──────────────────────────────────────────────
    budget = check_budget()
    if not budget["allowed"]:
        logger.warning("Budget exceeded — aborting batch. %s", budget)
        summary["budget_remaining"] = budget
        return summary

    # ── 2. Get pending submissions ───────────────────────────────────
    if owns_session:
        session = _get_db_session(cfg.get("db_url", PIPELINE_CONFIG["db_url"]))

    pending = _get_pending_submissions(session)
    if not pending:
        logger.info("No pending submissions — nothing to do")
        summary["budget_remaining"] = budget
        if owns_session:
            session.close()
        return summary

    logger.info("Found %d pending submission(s)", len(pending))

    # ── 3. Backfill missing embeddings ───────────────────────────────
    ollama_url = cfg.get("ollama_url", PIPELINE_CONFIG["ollama_url"])
    backfilled = _backfill_embeddings(pending, ollama_url)
    if backfilled:
        logger.info("Backfilled %d embedding(s)", backfilled)

    # ── 4. Cluster ───────────────────────────────────────────────────
    pending_refs = [fb.reference for fb in pending]
    cluster_input = AgentInput(data=pending_refs, context=cfg)
    cluster_output: AgentOutput = agent_map["cluster"].run(cluster_input)

    if not cluster_output.success:
        logger.error("Cluster agent failed: %s", cluster_output.message)
        summary["budget_remaining"] = check_budget()
        if owns_session:
            session.close()
        return summary

    clusters = cluster_output.data.get("clusters", [])
    summary["total_tokens"] += cluster_output.tokens_used

    # ── 5. Prioritise ────────────────────────────────────────────────
    prioritise_input = AgentInput(data=clusters, context=cfg)
    prioritise_output: AgentOutput = agent_map["prioritise"].run(prioritise_input)
    summary["total_tokens"] += prioritise_output.tokens_used

    tasks = prioritise_output.data.get("tasks", [])
    if not tasks:
        logger.info("No tasks after prioritisation")
        summary["budget_remaining"] = check_budget()
        if owns_session:
            session.close()
        return summary

    # ── 6. Process each task: write → review → deploy ────────────────
    max_retries = cfg.get("max_writer_retries", PIPELINE_CONFIG["max_writer_retries"])

    for task in tasks:
        # Re-check budget before each expensive task.
        budget = check_budget()
        if not budget["allowed"]:
            logger.warning("Budget exhausted mid-batch — stopping")
            break

        task_refs = task.get("references", [])
        task_detail = {
            "references": task_refs,
            "summary": task.get("summary", ""),
            "outcome": "pending",
            "tokens": 0,
        }
        summary["tasks_attempted"] += 1

        # Mark in-progress.
        _update_status(session, task_refs, FeedbackStatus.in_progress)

        # ── Write → Review retry loop ────────────────────────────────
        approved = False
        writer_data = None
        reviewer_feedback = None
        attempts = 0

        while attempts <= max_retries:
            attempts += 1

            # Writer
            writer_context = dict(cfg)
            if reviewer_feedback:
                writer_context["reviewer_feedback"] = reviewer_feedback

            writer_input = AgentInput(data=task, context=writer_context)
            writer_output: AgentOutput = agent_map["write"].run(writer_input)
            summary["total_tokens"] += writer_output.tokens_used
            task_detail["tokens"] += writer_output.tokens_used

            if not writer_output.success:
                logger.error("Writer failed (attempt %d): %s",
                             attempts, writer_output.message)
                break

            writer_data = writer_output.data

            # Reviewer
            reviewer_input = AgentInput(data=writer_data, context=cfg)
            reviewer_output: AgentOutput = agent_map["review"].run(reviewer_input)
            summary["total_tokens"] += reviewer_output.tokens_used
            task_detail["tokens"] += reviewer_output.tokens_used

            if not reviewer_output.success:
                logger.error("Reviewer failed (attempt %d): %s",
                             attempts, reviewer_output.message)
                break

            verdict = reviewer_output.data.get("verdict", "reject")
            if verdict == "approve":
                approved = True
                break

            # Rejected — feed comments back to the writer for retry.
            reviewer_feedback = reviewer_output.data.get("comments", "")
            logger.info("Reviewer rejected (attempt %d/%d): %s",
                        attempts, max_retries + 1, reviewer_feedback[:200])

        # ── Deploy or roll back ──────────────────────────────────────
        if approved and writer_data:
            deploy_input = AgentInput(data=writer_data, context=cfg)
            deploy_output: AgentOutput = agent_map["deploy"].run(deploy_input)
            summary["total_tokens"] += deploy_output.tokens_used
            task_detail["tokens"] += deploy_output.tokens_used

            if deploy_output.success:
                _update_status(
                    session, task_refs, FeedbackStatus.done,
                    agent_notes=writer_data.get("summary", "Completed by agent pipeline"),
                )
                task_detail["outcome"] = "done"
                summary["tasks_completed"] += 1
                logger.info("Task completed: %s", task.get("summary", "")[:100])
            else:
                # Deployment failed — leave as pending to retry tomorrow.
                _update_status(session, task_refs, FeedbackStatus.pending,
                               agent_notes=f"Deploy failed: {deploy_output.message}")
                task_detail["outcome"] = "deploy_failed"
                summary["tasks_failed"] += 1
                logger.warning("Deploy failed: %s", deploy_output.message)
        else:
            # Review never approved — leave as pending.
            notes = f"Review rejected after {attempts} attempt(s)"
            if reviewer_feedback:
                notes += f": {reviewer_feedback[:200]}"
            _update_status(session, task_refs, FeedbackStatus.pending,
                           agent_notes=notes)
            task_detail["outcome"] = "review_rejected"
            summary["tasks_failed"] += 1
            logger.warning("Task rejected after %d attempt(s): %s",
                           attempts, task.get("summary", "")[:100])

        summary["details"].append(task_detail)

    # ── 7. Final summary ─────────────────────────────────────────────
    summary["budget_remaining"] = check_budget()

    logger.info(
        "Batch complete — attempted: %d, completed: %d, failed: %d, "
        "tokens: %d, daily remaining: £%.2f, weekly remaining: £%.2f",
        summary["tasks_attempted"],
        summary["tasks_completed"],
        summary["tasks_failed"],
        summary["total_tokens"],
        summary["budget_remaining"]["daily_remaining"],
        summary["budget_remaining"]["weekly_remaining"],
    )

    if owns_session:
        session.close()

    return summary


# ── CLI entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    result = run_batch()
    print(f"\nBatch summary: {result}")
