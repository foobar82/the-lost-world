"""Tests for SPA catch-all path containment (REVIEW.md §3.3).

The serve_spa route must resolve paths and verify they stay within the
static directory to prevent directory traversal attacks.
"""

import sys
from pathlib import Path

import pytest

# Ensure the backend package is importable.
_repo_root = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, _repo_root)
sys.path.insert(0, str(Path(_repo_root) / "backend"))


@pytest.fixture()
def static_dir(tmp_path):
    """Create a fake static directory with an index.html and a nested file."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>SPA</html>")
    (static / "assets").mkdir()
    (static / "assets" / "app.js").write_text("console.log('app')")

    # Place a secret file *outside* the static directory to verify traversal
    # is blocked.
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")

    return static


@pytest.fixture()
def spa_client(static_dir):
    """Build a minimal FastAPI app with the SPA catch-all pointing at static_dir."""
    from fastapi import FastAPI
    from starlette.responses import FileResponse
    from starlette.testclient import TestClient

    app = FastAPI()
    _static_path = static_dir

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file = (_static_path / full_path).resolve()
        if file.is_file() and file.is_relative_to(_static_path.resolve()):
            return FileResponse(file)
        return FileResponse(_static_path / "index.html")

    with TestClient(app) as client:
        yield client


class TestSpaPathContainment:
    def test_legitimate_file_is_served(self, spa_client):
        resp = spa_client.get("/assets/app.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text

    def test_unknown_path_returns_index_html(self, spa_client):
        resp = spa_client.get("/some/spa/route")
        assert resp.status_code == 200
        assert "SPA" in resp.text

    def test_dot_dot_traversal_returns_index_html(self, spa_client):
        """Path traversal via .. must not leak files outside the static dir."""
        resp = spa_client.get("/../secret.txt")
        assert resp.status_code == 200
        assert "TOP SECRET" not in resp.text
        assert "SPA" in resp.text

    def test_encoded_dot_dot_traversal_returns_index_html(self, spa_client):
        """Percent-encoded traversal sequences must also be blocked."""
        resp = spa_client.get("/%2e%2e/secret.txt")
        assert resp.status_code == 200
        assert "TOP SECRET" not in resp.text
        assert "SPA" in resp.text

    def test_deep_traversal_returns_index_html(self, spa_client):
        """Multiple levels of .. must be blocked."""
        resp = spa_client.get("/assets/../../secret.txt")
        assert resp.status_code == 200
        assert "TOP SECRET" not in resp.text
        assert "SPA" in resp.text
