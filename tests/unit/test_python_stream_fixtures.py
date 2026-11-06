from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.clients import proxy
from app.core.utils.request_id import reset_request_id, set_request_id

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/protocol/stream-v1.json"
CASES = json.loads(FIXTURES.read_text())


@pytest.fixture(autouse=True)
def isolated_request_id():
    token = set_request_id(None)
    try:
        yield
    finally:
        reset_request_id(token)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_stream_fixture_matches_python(case: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.errors.time.time", lambda: 1700000000)
    normalized = proxy._normalize_sse_event_block(case["block"])
    for expected in case["expected"]:
        text, kind = proxy._normalize_stream_payload_for_http_block(
            normalized, enforce_openai_sdk_contract=expected["sdk"]
        )
        assert (text, kind) == (expected["text"], expected["event_type"])
