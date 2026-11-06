from __future__ import annotations

import pytest

from app.core.config.settings import Settings, warn_removed_settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "field",
    [
        "http_responses_session_bridge_operation_spool_format",
        "http_responses_session_bridge_operation_event_spool_max_bytes",
    ],
)
def test_swissai_does_not_expose_retired_bridge_settings(monkeypatch, field: str) -> None:
    name = "SWISSAI_LB_" + field.upper()
    monkeypatch.setenv(name, "ignored-test-value")
    assert not hasattr(Settings(_env_file=None), field)
    assert warn_removed_settings({name: "ignored-test-value"}) == [name]
