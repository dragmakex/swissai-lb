"""Provider policy, independent of HTTP routes and dashboard types."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.utils.time import to_utc_naive, utcnow

SECRET = re.compile(r"sk-(?:rc|sailb|clb)-[A-Za-z0-9_.-]+")
SENSITIVE = {"authorization", "api_key", "apikey", "token", "secret", "password", "access_token", "refresh_token"}


class PoolSettings(BaseModel):
    strategy: Literal["least_inflight", "round_robin", "fill_first", "single_key"] = "least_inflight"
    single_key_id: str | None = None
    default_max_concurrency: int = Field(4, ge=1, le=1000)
    first_byte_timeout_seconds: float = Field(30, ge=0.05, le=600)
    admission_timeout_seconds: float = Field(10, ge=0, le=300)
    max_queue_size: int = Field(128, ge=0, le=10000)

    @model_validator(mode="after")
    def single_key_is_explicit(self):
        if self.strategy == "single_key" and not self.single_key_id:
            raise ValueError("Single key routing requires a selected SwissAI key")
        return self


KEY_PROBE_MODEL = "__swissai_lb_auth_probe__"


class _ProbeError(BaseModel):
    type: Literal["invalid_request_error"]
    message: str


class _ProbeRejection(BaseModel):
    error: _ProbeError


def key_probe_authenticated(status: int, body: bytes) -> bool:
    if status != 404:
        return False
    try:
        rejection = _ProbeRejection.model_validate_json(body)
    except ValueError:
        return False
    return rejection.error.message.startswith(f"Model '{KEY_PROBE_MODEL}' not found.")


@dataclass(frozen=True)
class Failure:
    reason: str
    retry: bool = False
    cooldown: float = 0
    invalid: bool = False
    provider_wide: bool = False


def retry_after(value: str | None, now: datetime | None = None) -> float:
    seconds = 30.0
    if value:
        try:
            seconds = float(value)
        except ValueError:
            try:
                seconds = (to_utc_naive(parsedate_to_datetime(value)) - (now or utcnow())).total_seconds()
            except (ValueError, TypeError, OverflowError):
                pass
    if not math.isfinite(seconds):
        seconds = 30.0
    return max(1.0, min(86400.0, seconds))


def classify(status: int, retry_header: str | None, failures: int = 0) -> Failure:
    if status == 401:
        return Failure("invalid_credential", retry=True, invalid=True)
    if status == 429:
        return Failure("rate_limited", retry=True, cooldown=retry_after(retry_header))
    if status == 408:
        return Failure("upstream_timeout", retry=True, cooldown=10)
    if status in {500, 502, 503, 504}:
        return Failure("upstream_server_error", retry=True, cooldown=min(30, 2 ** min(failures, 5)))
    # No fixture-backed SwissAI credential-specific 403 code is known yet.
    return Failure("upstream_rejected")


def redact(value, known: tuple[str, ...] = ()):
    if isinstance(value, dict):
        return {k: "[redacted]" if k.lower() in SENSITIVE else redact(v, known) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, known) for v in value]
    if isinstance(value, str):
        for secret in known:
            value = value.replace(secret, "[redacted]")
        return SECRET.sub("[redacted]", value)
    return value


def sanitized_error(body: bytes, status: int, secret: str) -> dict:
    try:
        data = json.loads(body)
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return {
                "error": redact(
                    {
                        "message": error["message"][:4096],
                        "type": error.get("type", "upstream_error"),
                        "code": error.get("code", "upstream_error"),
                        "param": error.get("param"),
                    },
                    (secret,),
                )
            }
    except (ValueError, UnicodeError):
        pass
    return error_payload("upstream_error", f"SwissAI returned HTTP {status}")


def error_payload(code: str, message: str) -> dict:
    return {"error": {"message": message, "type": "upstream_error", "code": code, "param": None}}


def usage_from(data: dict) -> dict[str, int | None]:
    usage = data.get("usage")
    if not isinstance(usage, dict) and isinstance(data.get("response"), dict):
        usage = data["response"].get("usage")
    if not isinstance(usage, dict):
        return {}

    def count(value):
        return value if type(value) is int and value >= 0 else None

    input_details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or usage.get("completion_tokens_details") or {}
    return {
        "input_tokens": count(usage.get("input_tokens", usage.get("prompt_tokens"))),
        "output_tokens": count(usage.get("output_tokens", usage.get("completion_tokens"))),
        "cached_input_tokens": count(input_details.get("cached_tokens")) if isinstance(input_details, dict) else None,
        "reasoning_tokens": count(output_details.get("reasoning_tokens")) if isinstance(output_details, dict) else None,
    }
