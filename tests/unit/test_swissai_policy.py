from datetime import datetime

import pytest

from app.modules.swissai.observations import MAX_IDENTIFIERS, Observations
from app.modules.swissai.policy import classify, redact, retry_after, usage_from


@pytest.mark.parametrize(
    "header,expected", [("0", 1), ("99999999", 86400), ("nan", 30), ("inf", 30), ("bad", 30), (None, 30)]
)
def test_retry_after_is_always_bounded(header, expected):
    assert retry_after(header) == expected


def test_retry_after_http_date():
    assert retry_after("Thu, 01 Jan 2026 00:01:00 GMT", datetime(2026, 1, 1)) == 60


def test_unknown_403_and_client_errors_are_not_rotated():
    for status in (400, 403, 404, 409, 422):
        assert not classify(status, None).retry


def test_missing_usage_stays_unknown_and_zero_survives():
    assert usage_from({}) == {}
    assert usage_from({"usage": {"input_tokens": 0}}) == {
        "input_tokens": 0,
        "output_tokens": None,
        "cached_input_tokens": None,
        "reasoning_tokens": None,
    }


def test_responses_usage_is_nested_and_sse_chunks_can_split_utf8():
    observed = Observations(True)
    body = (
        'data: {"type":"response.completed","response":{"id":"resp_α",'
        '"usage":{"input_tokens":0,"output_tokens":3}}}\r\n\r\n'
    ).encode()
    for byte in body:
        observed.feed(bytes([byte]))
    observed.close()
    assert observed.usage["input_tokens"] == 0
    assert observed.usage["output_tokens"] == 3
    assert observed.identifiers == {"resp_α"}


def test_sse_frame_bound_is_enforced():
    observed = Observations(True)
    with pytest.raises(ValueError):
        observed.feed(b"data:" + b"x" * (1024 * 1024))


def test_secret_redaction_is_recursive_and_handles_nonpattern_secrets():
    actual = "arbitrary-credential-from-upstream"
    secret = "sk-rc-never-log-this-credential"
    value = {"Authorization": "Bearer " + secret, "nested": [{"api_key": actual}, "echo " + actual]}
    assert secret not in str(redact(value, (actual,)))
    assert actual not in str(redact(value, (actual,)))


def test_stream_observations_use_only_terminal_usage_and_keep_model_output_separate():
    observed = Observations(True)
    observed.feed(b'data: {"type":"response.created","response":{"id":"resp_a","usage":{"input_tokens":99}}}\n\n')
    assert observed.usage == {} and not observed.has_output
    observed.feed(b'data: {"type":"response.output_text.delta","delta":"Hello","usage":{"input_tokens":88}}\n\n')
    assert observed.has_output and observed.usage == {}
    observed.feed(b'data: {"type":"response.completed","response":{"id":"resp_a"}}\n\n')
    assert observed.usage == {}
    observed.inspect({"id": "resp_background", "status": "queued", "usage": {"input_tokens": 0}})
    assert observed.usage == {}


def test_chat_usage_is_terminal_and_role_only_chunks_are_not_tokens():
    observed = Observations(False)
    observed.feed(
        b'data: {"choices":[{"delta":{"role":"assistant","content":""},"finish_reason":null}],'
        b'"usage":{"prompt_tokens":10}}\n\n'
    )
    assert observed.usage == {} and not observed.has_output
    observed.feed(b'data: {"choices":[{"delta":{"tool_calls":[{"function":{"name":"search","arguments":""}}]}}]}\n\n')
    assert observed.has_output
    observed.feed(b'data: {"choices":[],"usage":{"prompt_tokens":0,"completion_tokens":0}}\n\n')
    assert observed.usage["input_tokens"] == observed.usage["output_tokens"] == 0


def test_owner_metadata_is_bounded_and_never_accepts_a_credential():
    observed = Observations(True)
    for index in range(MAX_IDENTIFIERS):
        observed.inspect({"id": f"resp_{index}"})
    with pytest.raises(ValueError, match="Too many"):
        observed.inspect({"id": "resp_overflow"})
    assert len(observed.identifiers) == MAX_IDENTIFIERS
    secret = "sk-rc-test-only-owner-secret"
    with pytest.raises(ValueError, match="Credential-like") as raised:
        Observations(True).inspect({"id": secret})
    assert secret not in str(raised.value)


def test_malformed_event_discriminators_do_not_crash_metadata_inspection():
    observed = Observations(True)
    observed.feed(b'data: {"type":[],"response":{"status":{},"usage":{"input_tokens":1}}}\n\n')
    assert observed.usage == {} and not observed.has_output
