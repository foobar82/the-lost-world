import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the backend package is importable from the repo-root tests/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_engine(tmp_path):
    """Create a fresh SQLite database in a temporary directory for each test."""
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Provide a SQLAlchemy session bound to the temporary test database."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine):
    """
    Provide a Starlette TestClient whose requests use the temporary database
    instead of the production one.
    """
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
