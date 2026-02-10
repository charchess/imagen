"""
Tests for Story 1.2: Standardized Error Response Format

AC #1: All errors follow {"error": {"code", "message", "detail", "status"}} format
AC #2: Pydantic validation → INVALID_PARAMETERS 422
AC #3: GET /v1/status/{unknown_id} → JOB_NOT_FOUND 404
AC #4: Queue full → QUEUE_FULL 503
"""
from unittest.mock import MagicMock, patch


def _assert_error_envelope(resp, expected_code, expected_status):
    """Validate error envelope structure and values."""
    assert resp.status_code == expected_status
    body = resp.json()
    assert "error" in body, f"Response missing 'error' key: {body}"
    error = body["error"]
    assert error["code"] == expected_code
    assert "message" in error
    assert "detail" in error
    assert error["status"] == expected_status


class TestAC1_ErrorEnvelopeFormat:
    """AC #1: All errors follow standardized envelope format."""

    def test_validation_error_has_envelope(self, client):
        """Validation errors use the error envelope."""
        resp = client.post("/v1/generate", json={})
        body = resp.json()
        assert "error" in body
        error = body["error"]
        for field in ("code", "message", "detail", "status"):
            assert field in error, f"Missing '{field}' in error envelope"

    def test_http_status_matches_envelope_status(self, client):
        """HTTP status code equals envelope's status field."""
        resp = client.post("/v1/generate", json={})
        body = resp.json()
        assert resp.status_code == body["error"]["status"]

    def test_not_found_has_envelope(self, client):
        """404 errors use the error envelope."""
        resp = client.get("/v1/download/nonexistent_file.png")
        body = resp.json()
        assert "error" in body
        assert body["error"]["status"] == 404


class TestAC2_ValidationError:
    """AC #2: Pydantic validation → INVALID_PARAMETERS with 422."""

    def test_missing_required_field(self, client):
        resp = client.post("/v1/generate", json={})
        _assert_error_envelope(resp, "INVALID_PARAMETERS", 422)

    def test_detail_contains_validation_info(self, client):
        resp = client.post("/v1/generate", json={})
        error = resp.json()["error"]
        assert len(str(error["detail"])) > 0


class TestAC3_JobNotFound:
    """AC #3: GET /v1/status/{unknown_id} → JOB_NOT_FOUND 404."""

    def test_unknown_job_returns_not_found(self, client):
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.status = "PENDING"
        mock_result.result = None
        with patch("app.api.AsyncResult", return_value=mock_result):
            resp = client.get("/v1/status/nonexistent-job")
        _assert_error_envelope(resp, "JOB_NOT_FOUND", 404)


class TestAC4_QueueFull:
    """AC #4: Queue full → QUEUE_FULL 503."""

    def test_full_queue_returns_503(self, client):
        mock_inspector = MagicMock()
        mock_inspector.active.return_value = {"w1": [{}] * 100}
        mock_inspector.scheduled.return_value = {}
        with patch("app.api.celery_app") as mock_celery:
            mock_celery.control.inspect.return_value = mock_inspector
            resp = client.post("/v1/generate", json={"prompt": "test"})
        _assert_error_envelope(resp, "QUEUE_FULL", 503)
