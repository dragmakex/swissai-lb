import json

import pytest

from app.modules.swissai.policy import KEY_PROBE_MODEL, key_probe_authenticated


def rejection(message: str, error_type: str = "invalid_request_error") -> bytes:
    return json.dumps({"error": {"type": error_type, "message": message}}).encode()


def test_probe_accepts_only_the_observed_authenticated_model_rejection() -> None:
    assert key_probe_authenticated(404, rejection(f"Model '{KEY_PROBE_MODEL}' not found. See /v1/models."))


@pytest.mark.parametrize("status", [200, 301, 400, 401, 403, 429, 500, 503])
def test_other_status_is_not_authentication_proof(status: int) -> None:
    assert not key_probe_authenticated(status, rejection(f"Model '{KEY_PROBE_MODEL}' not found."))


@pytest.mark.parametrize(
    "body",
    [
        b"Not Found",
        b"{}",
        b'{"error":null}',
        b'{"error":{"type":"invalid_request_error","message":42}}',
        rejection("Not Found"),
        rejection("Model 'another-model' not found."),
        rejection(f"Model '{KEY_PROBE_MODEL}' not found.", "authentication_error"),
    ],
)
def test_unknown_body_is_not_authentication_proof(body: bytes) -> None:
    assert not key_probe_authenticated(404, body)
