"""API tests for the feedback endpoints (Phase 2.2 of the CI/CD plan)."""

from unittest.mock import patch


# ---------------------------------------------------------------------------
# POST /api/feedback
# ---------------------------------------------------------------------------


class TestCreateFeedback:
    def test_valid_submission_returns_201_with_reference_and_pending_status(self, client):
        resp = client.post("/api/feedback", json={"content": "Add fish to the water"})
        assert resp.status_code == 201
        body = resp.json()
        assert "reference" in body
        assert body["reference"].startswith("LW-")
        assert body["status"] == "pending"

    def test_empty_content_is_rejected(self, client):
        resp = client.post("/api/feedback", json={"content": ""})
        assert resp.status_code == 422

    def test_missing_content_field_is_rejected(self, client):
        resp = client.post("/api/feedback", json={})
        assert resp.status_code == 422

    def test_very_long_content_is_handled_gracefully(self, client):
        long_text = "x" * 5000
        resp = client.post("/api/feedback", json={"content": long_text})
        # The schema enforces max_length=2000, so this should be rejected
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/feedback
# ---------------------------------------------------------------------------


class TestListFeedback:
    def test_returns_all_submissions_newest_first(self, client):
        refs = []
        for msg in ["First", "Second", "Third"]:
            resp = client.post("/api/feedback", json={"content": msg})
            refs.append(resp.json()["reference"])

        resp = client.get("/api/feedback")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 3

        # Newest first — Third was created last
        assert items[0]["reference"] == refs[2]
        assert items[1]["reference"] == refs[1]
        assert items[2]["reference"] == refs[0]

    def test_status_filter_returns_only_matching_items(self, client, db_session):
        # Create two items
        client.post("/api/feedback", json={"content": "Item A"})
        client.post("/api/feedback", json={"content": "Item B"})

        # Manually mark one as done via the database
        from app.models import Feedback, FeedbackStatus

        fb = db_session.query(Feedback).filter(Feedback.reference == "LW-001").first()
        fb.status = FeedbackStatus.done
        db_session.commit()

        # Filter for done items only
        resp = client.get("/api/feedback", params={"status": "done"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["reference"] == "LW-001"
        assert items[0]["status"] == "done"

        # Filter for pending — should return only the other item
        resp = client.get("/api/feedback", params={"status": "pending"})
        items = resp.json()
        assert len(items) == 1
        assert items[0]["reference"] == "LW-002"


# ---------------------------------------------------------------------------
# GET /api/feedback/{reference}
# ---------------------------------------------------------------------------


class TestGetFeedbackByReference:
    def test_retrieve_existing_submission_by_reference(self, client):
        create_resp = client.post(
            "/api/feedback", json={"content": "Make herbivores faster"}
        )
        ref = create_resp.json()["reference"]

        resp = client.get(f"/api/feedback/{ref}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reference"] == ref
        assert body["content"] == "Make herbivores faster"
        assert body["status"] == "pending"

    def test_non_existent_reference_returns_404(self, client):
        resp = client.get("/api/feedback/LW-999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reference number generation
# ---------------------------------------------------------------------------


class TestReferenceGeneration:
    def test_references_are_sequential(self, client):
        refs = []
        for i in range(5):
            resp = client.post(
                "/api/feedback", json={"content": f"Feedback item {i}"}
            )
            refs.append(resp.json()["reference"])

        assert refs == ["LW-001", "LW-002", "LW-003", "LW-004", "LW-005"]

    def test_references_are_unique(self, client):
        refs = set()
        for i in range(10):
            resp = client.post(
                "/api/feedback", json={"content": f"Feedback item {i}"}
            )
            refs.add(resp.json()["reference"])

        assert len(refs) == 10


# ---------------------------------------------------------------------------
# Embedding integration (section 2.3)
# ---------------------------------------------------------------------------


class TestFeedbackEmbeddingIntegration:
    """Verify that feedback submission triggers embedding generation."""

    def test_store_embedding_called_with_reference_and_content(
        self, client, _mock_store_embedding
    ):
        content = "Add fish to the water"
        resp = client.post("/api/feedback", json={"content": content})
        assert resp.status_code == 201

        ref = resp.json()["reference"]
        _mock_store_embedding.assert_called_once_with(ref, content)

    def test_submission_succeeds_when_embedding_fails(self, client):
        with patch(
            "app.router_feedback.store_feedback_embedding", return_value=False
        ):
            resp = client.post(
                "/api/feedback", json={"content": "Embedding will fail"}
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["reference"].startswith("LW-")
        assert body["status"] == "pending"

    def test_submission_succeeds_when_embedding_raises(self, client):
        with patch(
            "app.router_feedback.store_feedback_embedding",
            side_effect=Exception("Ollama exploded"),
        ):
            resp = client.post(
                "/api/feedback", json={"content": "Boom"}
            )

        # The submission must succeed even if the embedding layer throws.
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_embedding_receives_correct_content_for_multiple_submissions(
        self, client, _mock_store_embedding
    ):
        client.post("/api/feedback", json={"content": "First feedback"})
        client.post("/api/feedback", json={"content": "Second feedback"})

        assert _mock_store_embedding.call_count == 2
        calls = _mock_store_embedding.call_args_list
        assert calls[0].args == ("LW-001", "First feedback")
        assert calls[1].args == ("LW-002", "Second feedback")
