"""One SwissAI routing owner, using upstream transport leases, client limits and request logs.

The ASGI response owns the complete logical request. It does not return an
unstarted streaming generator holding a lease. All exits (including cancelled
send, malformed errors and server shutdown) run the same cleanup boundary.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from datetime import timedelta

import aiohttp
from fastapi import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Send

from app.core.clients.http import lease_model_source_session, refresh_http_client_after_network_failure
from app.core.clock import clock_for, scheduler_for
from app.core.config.dashboard_overrides import with_dashboard_overrides
from app.core.config.settings import get_settings
from app.core.crypto import TokenEncryptor
from app.core.utils.request_id import ensure_request_scope_id
from app.core.utils.shared_future import (
    _await_cleanup_deferring_cancellation,
    _await_result_deferring_cancellation,
    wait_on_shared_future,
)
from app.core.utils.time import utcnow
from app.db.session import get_background_session
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.api_keys.service import ApiKeyData, ApiKeysService, ApiKeyUsageReservationData
from app.modules.request_logs.repository import RequestLogsRepository
from app.modules.swissai import metrics
from app.modules.swissai import repository as repo
from app.modules.swissai.observations import ObservationError, Observations
from app.modules.swissai.policy import Failure, PoolSettings, classify, error_payload, sanitized_error

logger = logging.getLogger(__name__)
MAX_BODY = 32 * 1024 * 1024
MAX_RESPONSE = 64 * 1024 * 1024
MAX_ERROR = 64 * 1024
SAFE_HEADERS = {"accept", "content-type", "idempotency-key", "openai-beta"}


class Rejected(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: float | None = None):
        self.status, self.code, self.message, self.retry_after = status, code, message, retry_after


async def bounded_read(response: aiohttp.ClientResponse, maximum: int) -> bytes:
    data = bytearray()
    async for chunk in response.content.iter_chunked(65536):
        if len(data) + len(chunk) > maximum:
            raise Rejected(502, "upstream_response_too_large", "SwissAI response exceeded the configured bound")
        data.extend(chunk)
    return bytes(data)


def identifiers(body: dict) -> list[str]:
    values = [body.get("previous_response_id"), body.get("conversation_id"), body.get("conversation")]
    result = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            value = value.get("id")
        if not isinstance(value, str) or not 1 <= len(value) <= 512:
            raise ValueError("Continuation references require an ID of 1–512 characters")
        result.append(value)
    return result


async def prepare(request: Request, client_key: ApiKeyData | None, path: str) -> Response:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY:
            return JSONResponse(error_payload("request_too_large", "Request body exceeds 32 MiB"), status_code=413)
        body.extend(chunk)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        return JSONResponse(error_payload("invalid_json", "Expected a JSON object"), status_code=400)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("model"), str)
        or not payload["model"].strip()
        or len(payload["model"]) > 512
    ):
        return JSONResponse(
            error_payload("invalid_model", "A model ID of 1–512 characters is required"), status_code=400
        )
    if "stream" in payload and type(payload["stream"]) is not bool:
        return JSONResponse(error_payload("invalid_stream", "stream must be a boolean"), status_code=400)
    model = payload["model"]
    if client_key:
        if client_key.enforced_model and model != client_key.enforced_model:
            return JSONResponse(
                error_payload("model_not_allowed", "Client key requires a different model"), status_code=403
            )
        if client_key.allowed_models is not None and model not in client_key.allowed_models:
            return JSONResponse(
                error_payload("model_not_allowed", "This client key may not use that model"), status_code=403
            )
    try:
        owner = await repo.continuation_owner(identifiers(payload)) if path == "/responses" else None
    except repo.KeyNotFound:
        return JSONResponse(
            error_payload("continuation_owner_unavailable", "The continuation owner is unknown"), status_code=503
        )
    except ValueError:
        return JSONResponse(
            error_payload("invalid_continuation", "A continuation ID of 1–512 characters is required"), status_code=400
        )
    allowed = set(client_key.assigned_source_ids) if client_key and client_key.source_assignment_scope_enabled else None
    if owner and allowed is not None and owner[0] not in allowed:
        return JSONResponse(
            error_payload("continuation_owner_unavailable", "The continuation owner is unavailable"), status_code=503
        )
    config = await repo.pool_settings()
    # The body is never reserialized or modified between upstream attempts.
    return SwissAIResponse(request, bytes(body), payload, client_key, path, config, allowed, owner)


class SwissAIResponse(Response):
    media_type = "application/json"

    def __init__(
        self,
        request: Request,
        body: bytes,
        payload: dict,
        client_key: ApiKeyData | None,
        path: str,
        config: PoolSettings,
        allowed: set[str] | None,
        owner: tuple[str, int] | None,
    ):
        super().__init__()
        self.request, self.content, self.payload, self.client_key = request, body, payload, client_key
        self.path, self.config, self.allowed, self.owner = path, config, allowed, owner
        self.request_id = ensure_request_scope_id()
        self._clock = clock_for(request.app.state.swissai)
        self._scheduler = scheduler_for(request.app.state.swissai)
        self.started = self._clock.monotonic()
        self.stream = bool(payload.get("stream"))
        self.observed = Observations(path == "/responses")
        self.attempts = 0
        self.selected: repo.SelectedKey | None = None
        self.status = 502
        self.error: str | None = None
        self.visible = False
        self.ttft: int | None = None
        self.reservation: ApiKeyUsageReservationData | None = None
        self.response_started = False
        self.completed = False
        self.lease_lost = False

    async def __call__(self, scope, receive, send):
        async def disconnected():
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return

        work = self._scheduler.create_task(self._run(scope, receive, send))
        monitor = self._scheduler.create_task(disconnected())
        try:
            done, _ = await self._scheduler.wait({work, monitor}, return_when=asyncio.FIRST_COMPLETED)
            if work in done or self.completed:
                await wait_on_shared_future(work)
            else:
                work.cancel()
                try:
                    await wait_on_shared_future(work)
                except asyncio.CancelledError:
                    pass
        finally:
            monitor.cancel()
            work.cancel()
            cancellation = await _await_cleanup_deferring_cancellation(
                asyncio.gather(work, monitor, return_exceptions=True)
            )
            settlement_cancellation = await _await_cleanup_deferring_cancellation(self._settle_and_log())
            cancellation = cancellation or settlement_cancellation
            if cancellation is not None:
                raise cancellation

    async def _run(self, scope, receive, send):
        runtime = with_dashboard_overrides(get_settings())
        budget = (
            runtime.http_responses_stream_request_budget_seconds
            if self.stream
            else runtime.proxy_request_budget_seconds
        )
        deadline = self._clock.monotonic() + budget
        try:
            # Relative timers work even when the event-loop clock has a different epoch.
            with self._scheduler.fail_after(max(0.0, deadline - self._clock.monotonic())):
                _, cancellation = await _await_result_deferring_cancellation(self._reserve(), scheduler=self._scheduler)
                if cancellation is not None:
                    raise cancellation
                await self._dispatch(scope, receive, send, deadline)
        except asyncio.CancelledError:
            self.error = "capacity_lease_lost" if self.lease_lost else "client_cancelled"
            self.status = 503 if self.lease_lost else 499
            if self.lease_lost and not self.response_started:
                await self._error_response(
                    scope, receive, send, 503, error_payload(self.error, "Upstream capacity ownership was lost")
                )
                return
            raise
        except TimeoutError:
            self.status, self.error = 504, "request_deadline_exceeded"
            if not self.response_started:
                await self._error_response(
                    scope, receive, send, 504, error_payload(self.error, "SwissAI request budget expired")
                )
            else:
                raise
        except ObservationError:
            self.status, self.error = 502, "upstream_protocol_error"
            if self.response_started:
                raise
            await self._error_response(
                scope, receive, send, 502, error_payload(self.error, "SwissAI returned invalid response metadata")
            )
        except Rejected as exc:
            self.status, self.error = exc.status, exc.code
            if self.response_started:
                raise
            await self._error_response(
                scope, receive, send, exc.status, error_payload(exc.code, exc.message), exc.retry_after
            )
        except Exception:
            self.status, self.error = 502, "proxy_internal_error"
            logger.error("SwissAI request failed request_id=%s", self.request_id)
            if self.response_started:
                raise
            await self._error_response(
                scope, receive, send, 502, error_payload(self.error, "The proxy could not complete this request")
            )

    async def _reserve(self):
        if self.client_key is None:
            return
        from app.modules.api_keys.service import ApiKeyInvalidError, ApiKeyRateLimitExceededError

        async with get_background_session() as session:
            try:
                self.reservation = await ApiKeysService(ApiKeysRepository(session)).enforce_limits_for_request(
                    self.client_key.id,
                    request_model=self.payload["model"],
                )
            except ApiKeyRateLimitExceededError as exc:
                raise Rejected(
                    429,
                    "client_usage_limit",
                    "Local client key usage limit exceeded",
                    (exc.reset_at - utcnow()).total_seconds(),
                ) from exc
            except ApiKeyInvalidError as exc:
                raise Rejected(401, "invalid_api_key", "Local client key is no longer valid") from exc

    async def _dispatch(self, scope, receive, send, deadline):
        excluded: set[str] = set()
        last: tuple[int, dict, str | None] | None = None
        # At most three distinct keys; single-key debugging never rotates.
        max_attempts = 1 if self.owner or self.config.strategy == "single_key" else 3
        for index in range(1, max_attempts + 1):
            selected = await self._admit(excluded, deadline)
            if selected is None:
                if last:
                    break
                code = "continuation_owner_unavailable" if self.owner else "no_upstream_keys"
                raise Rejected(503, code, "No eligible SwissAI key is available")
            if index > 1 and self.error:
                metrics.failover(self.error)
            self.selected = selected
            self.attempts = index
            excluded.add(selected.id)
            attempt_started = self._clock.monotonic()
            attempt_id = None
            failure = None
            status = None
            transport = AsyncExitStack()
            parent = asyncio.current_task()
            keeper = self._scheduler.create_task(self._renew(selected.lease_id, parent))
            try:
                attempt_id = await repo.record_attempt(self.request_id, index, selected)
                session = await transport.enter_async_context(lease_model_source_session())
                secret = TokenEncryptor().decrypt(selected.encrypted)
                connection_headers = {
                    name.strip().lower() for name in self.request.headers.get("connection", "").split(",")
                }
                headers = {
                    k: v
                    for k, v in self.request.headers.items()
                    if k.lower() in SAFE_HEADERS and k.lower() not in connection_headers
                }
                headers.update(
                    {
                        "Authorization": "Bearer " + secret,
                        "Accept-Encoding": "identity",
                        "X-Request-ID": self.request_id,
                    }
                )
                runtime = with_dashboard_overrides(get_settings())
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=runtime.upstream_connect_timeout_seconds)
                phase_deadline = min(deadline, self._clock.monotonic() + self.config.first_byte_timeout_seconds)
                with self._scheduler.fail_after(max(0.0, phase_deadline - self._clock.monotonic())):
                    response = await transport.enter_async_context(
                        session.post(
                            get_settings().upstream_base_url.rstrip("/") + self.path,
                            data=self.content,
                            headers=headers,
                            timeout=timeout,
                            allow_redirects=False,
                        )
                    )
                    status = response.status
                    if status >= 300:
                        try:
                            raw = await bounded_read(response, MAX_ERROR)
                        except Rejected:
                            raw = b""
                        failure = classify(status, response.headers.get("Retry-After"), selected.failures)
                        last = (
                            status if status >= 400 else 502,
                            sanitized_error(raw, status, secret),
                            response.headers.get("Retry-After"),
                        )
                    else:
                        first = await response.content.read(65536)
                        if not first and self.stream:
                            raise aiohttp.ClientPayloadError("Empty upstream stream")
                if failure:
                    self.error = failure.reason
                    if not failure.retry:
                        break
                    continue
                self.error = None
                if self.stream:
                    self.observed.feed(first)
                    await repo.save_owners(self.observed.identifiers, selected)
                    self._record_first_output(attempt_started)
                    await self._stream(response, first, send, runtime.stream_idle_timeout_seconds, attempt_started)
                else:
                    content = first + await bounded_read(response, MAX_RESPONSE - len(first))
                    try:
                        obj = json.loads(content)
                    except (ValueError, UnicodeError):
                        pass
                    else:
                        if isinstance(obj, dict):
                            self.observed.inspect(obj)
                    await repo.save_owners(self.observed.identifiers, selected)
                    await self._send_content(
                        send, status, response.headers.get("Content-Type", "application/json"), content
                    )
                if self.observed.failed:
                    failure = Failure("upstream_response_failed", provider_wide=True)
                    self.error = failure.reason
                self.status = status
                return
            except asyncio.CancelledError:
                failure = Failure("capacity_lease_lost" if self.lease_lost else "client_cancelled", provider_wide=True)
                raise
            except (Rejected, ValueError):
                failure = Failure("upstream_protocol_error", provider_wide=True)
                raise
            except (aiohttp.ClientError, TimeoutError) as exc:
                if self.response_started:
                    failure = Failure("stream_interrupted", provider_wide=True)
                    raise Rejected(502, failure.reason, "SwissAI stream closed after output was committed") from exc
                network = isinstance(exc, (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError))
                failure = Failure(
                    "network_error" if network else "pre_output_timeout",
                    retry=True,
                    cooldown=0 if network else 2,
                    provider_wide=network,
                )
                last = (
                    502,
                    error_payload(
                        failure.reason, "SwissAI connection failed before output; upstream execution may have occurred"
                    ),
                    None,
                )
                self.error = failure.reason
                if network:
                    await refresh_http_client_after_network_failure(failed_session=session)
            finally:

                async def cleanup():
                    keeper.cancel()
                    await asyncio.gather(keeper, return_exceptions=True)
                    try:
                        await transport.aclose()
                        if attempt_id:
                            await repo.finish_attempt(
                                attempt_id, status, failure.reason if failure else None, self.visible
                            )
                        if failure is None or failure.reason not in {"client_cancelled", "capacity_lease_lost"}:
                            await repo.health(selected, failure)
                        metrics.attempt(
                            self.path,
                            status,
                            failure.reason if failure else None,
                            self._clock.monotonic() - attempt_started,
                        )
                    finally:
                        await repo.release_lease(selected.lease_id)

                cancellation = await _await_cleanup_deferring_cancellation(cleanup())
                if cancellation is not None:
                    raise cancellation
        if last:
            self.status = last[0]
            await self._error_response(scope, receive, send, *last)
            return
        raise Rejected(503, "no_upstream_keys", "No eligible SwissAI key is available")

    async def _admit(self, excluded, deadline):
        admission_started = self._clock.monotonic()
        admission_deadline = min(deadline, admission_started + self.config.admission_timeout_seconds)
        runtime = self.request.app.state.swissai
        queued = False
        try:
            while True:
                selection, cancellation = await _await_result_deferring_cancellation(
                    repo.select_key(self.config, excluded, self.allowed, self.owner)
                )
                selected, saturated, retry = selection
                if cancellation is not None:
                    if selected:
                        await _await_cleanup_deferring_cancellation(repo.release_lease(selected.lease_id))
                    raise cancellation
                if selected:
                    return selected
                if not saturated:
                    if excluded:
                        return None
                    code = "continuation_owner_unavailable" if self.owner else "no_upstream_keys"
                    raise Rejected(503, code, "No eligible SwissAI keys are available", retry)
                if not queued:
                    if runtime.queued >= self.config.max_queue_size:
                        raise Rejected(429, "local_capacity_exhausted", "Local admission queue is full", 1)
                    runtime.queued += 1
                    queued = True
                if self._clock.monotonic() >= admission_deadline:
                    raise Rejected(429, "local_capacity_exhausted", "Local admission timed out", 1)
                await self._scheduler.sleep(min(0.05, admission_deadline - self._clock.monotonic()))
        finally:
            if queued:
                runtime.queued -= 1
            metrics.admission(self._clock.monotonic() - admission_started)

    async def _renew(self, lease_id, parent):
        try:
            while True:
                await self._scheduler.sleep(20)
                if not await repo.renew_lease(lease_id):
                    self.lease_lost = True
                    parent.cancel()
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            # Fail closed: never keep generating without ownership of capacity.
            self.lease_lost = True
            parent.cancel()

    def _record_first_output(self, attempt_started: float) -> None:
        if self.ttft is None and self.observed.has_output:
            now = self._clock.monotonic()
            self.ttft = round((now - self.started) * 1000)
            metrics.first_output(self.path, now - attempt_started)

    async def _stream(
        self, response: aiohttp.ClientResponse, first: bytes, send: Send, idle: float, attempt_started: float
    ) -> None:
        assert self.selected is not None
        await send(
            {
                "type": "http.response.start",
                "status": response.status,
                "headers": self._response_headers(response.headers.get("Content-Type", "text/event-stream")),
            }
        )
        self.response_started = True
        await send({"type": "http.response.body", "body": first, "more_body": True})
        self.visible = True
        while True:
            with self._scheduler.fail_after(idle):
                chunk = await response.content.read(65536)
            if not chunk:
                break
            self.observed.feed(chunk)
            self._record_first_output(attempt_started)
            await repo.save_owners(self.observed.identifiers, self.selected)
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        self.observed.close()
        self._record_first_output(attempt_started)
        await repo.save_owners(self.observed.identifiers, self.selected)
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        self.completed = True

    def _response_headers(self, content_type):
        return [
            (b"content-type", content_type.encode("latin-1")),
            (b"x-request-id", self.request_id.encode()),
            (b"cache-control", b"no-cache, no-transform"),
            (b"x-accel-buffering", b"no"),
        ]

    async def _send_content(self, send, status, content_type, content):
        await send({"type": "http.response.start", "status": status, "headers": self._response_headers(content_type)})
        self.response_started = True
        await send({"type": "http.response.body", "body": content, "more_body": False})
        self.visible = True
        self.completed = True

    async def _error_response(self, scope, receive, send, status, payload, retry_after=None):
        headers = {"X-Request-ID": self.request_id}
        if retry_after is not None:
            from app.modules.swissai.policy import retry_after as parse_retry

            headers["Retry-After"] = str(int(parse_retry(str(retry_after))))
        self.response_started = True
        await JSONResponse(payload, status_code=status, headers=headers)(scope, receive, send)
        self.completed = True

    async def _settle_and_log(self):
        outcome = "cancelled" if self.status == 499 else "error" if self.error or self.status >= 400 else "success"
        metrics.request(self.path, outcome, self._clock.monotonic() - self.started)
        usage = self.observed.usage
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if self.reservation:
            async with get_background_session() as session:
                service = ApiKeysService(ApiKeysRepository(session))
                if input_tokens is not None and output_tokens is not None:
                    await service.finalize_usage_reservation(
                        self.reservation.reservation_id,
                        model=self.payload["model"],
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_input_tokens=usage.get("cached_input_tokens") or 0,
                        cost_microdollars=0,
                    )
                elif self.visible:
                    # Committed output can incur usage even when the stream fails; never refund it as unused.
                    from app.modules.api_keys.service import (
                        API_KEY_USAGE_RESERVATION_DEFAULT_INPUT_TOKENS,
                        API_KEY_USAGE_RESERVATION_DEFAULT_OUTPUT_TOKENS,
                    )

                    await service.fail_usage_reservation(
                        self.reservation.reservation_id,
                        model=self.payload["model"],
                        input_tokens=API_KEY_USAGE_RESERVATION_DEFAULT_INPUT_TOKENS,
                        output_tokens=API_KEY_USAGE_RESERVATION_DEFAULT_OUTPUT_TOKENS,
                    )
                else:
                    await service.release_usage_reservation(self.reservation.reservation_id)
        try:
            async with get_background_session() as session:
                await RequestLogsRepository(session).add_log(
                    account_id=None,
                    request_id=self.request_id,
                    model=self.payload["model"],
                    api_key_id=self.client_key.id if self.client_key else None,
                    model_source_id=self.selected.id if self.selected else None,
                    model_source_kind="swissai",
                    route=self.request.url.path.rstrip("/"),
                    stream=self.stream,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    cached_input_tokens=usage.get("cached_input_tokens"),
                    reasoning_tokens=usage.get("reasoning_tokens"),
                    latency_ms=round((self._clock.monotonic() - self.started) * 1000),
                    latency_first_token_ms=self.ttft,
                    status=outcome,
                    error_code=self.error,
                    source="model_source",
                    transport="http",
                    upstream_transport="swissai_http",
                    upstream_status_code=self.status,
                    requested_at=utcnow() - timedelta(seconds=self._clock.monotonic() - self.started),
                )
        except Exception:
            logger.error("SwissAI request log could not be written request_id=%s", self.request_id)
