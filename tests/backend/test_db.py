"""Database tests for the feedback table (Phase 2.3 of the CI/CD plan)."""

from sqlalchemy import inspect, create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Feedback, FeedbackStatus


# ---------------------------------------------------------------------------
# Schema integrity
# ---------------------------------------------------------------------------


class TestSchemaIntegrity:
    def test_feedback_table_has_all_expected_columns(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("feedback")}

        expected = {
            "id",
            "reference",
            "content",
            "status",
            "agent_notes",
            "created_at",
            "updated_at",
        }
        assert expected == columns

    def test_status_field_accepts_all_valid_values(self, db_session):
        valid_statuses = [
            FeedbackStatus.pending,
            FeedbackStatus.in_progress,
            FeedbackStatus.done,
            FeedbackStatus.rejected,
        ]
        for i, status in enumerate(valid_statuses):
            fb = Feedback(
                reference=f"TEST-{i:03d}",
                content=f"Test {status.value}",
                status=status,
            )
            db_session.add(fb)

        db_session.commit()

        stored = db_session.query(Feedback).all()
        stored_statuses = {fb.status for fb in stored}
        assert stored_statuses == set(valid_statuses)


# ---------------------------------------------------------------------------
# Data persistence
# ---------------------------------------------------------------------------


class TestDataPersistence:
    def test_submission_survives_database_close_and_reopen(self, tmp_path):
        db_path = tmp_path / "persist_test.db"
        url = f"sqlite:///{db_path}"

        # Create and populate
        engine1 = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine1)
        Session1 = sessionmaker(bind=engine1)
        session1 = Session1()
        session1.add(
            Feedback(
                reference="LW-001",
                content="Persistence check",
                status=FeedbackStatus.pending,
            )
        )
        session1.commit()
        session1.close()
        engine1.dispose()

        # Reopen from scratch
        engine2 = create_engine(url, connect_args={"check_same_thread": False})
        Session2 = sessionmaker(bind=engine2)
        session2 = Session2()
        fb = session2.query(Feedback).filter(Feedback.reference == "LW-001").first()

        assert fb is not None
        assert fb.content == "Persistence check"
        assert fb.status == FeedbackStatus.pending

        session2.close()
        engine2.dispose()
