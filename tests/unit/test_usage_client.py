from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

import pytest

from app.core.clients.usage import UsageFetchError, consume_rate_limit_reset_credit, fetch_usage
from app.core.upstream_proxy import ResolvedProxyEndpoint, ResolvedUpstreamRoute

pytestmark = pytest.mark.unit


class StubResponse:
    def __init__(self, status: int, payload: dict | None, text: str) -> None:
        self.status = status
        self._payload = payload
        self._text = text

    async def json(self, content_type: str | None = None) -> dict:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    async def text(self) -> str:
        return self._text


@dataclass
class UsageClientState:
    calls: int = 0
    method: str | None = None
    url: str | None = None
    auth: str | None = None
    account: str | None = None
    payload: dict[str, str] | None = None


class StubRequestContext:
    def __init__(
        self,
        responses: list[StubResponse],
        state: UsageClientState,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, str] | None,
        retry_options: object | None,
    ) -> None:
        self._responses = responses
        self._state = state
        self._method = method
        self._url = url
        self._headers = headers
        self._payload = payload
        self._retry_options = retry_options

    async def __aenter__(self) -> StubResponse:
        attempts = getattr(self._retry_options, "attempts", 1)
        statuses = set(getattr(self._retry_options, "statuses", set()))
        response: StubResponse | None = None
        for attempt in range(attempts):
            index = min(self._state.calls, len(self._responses) - 1)
            response = self._responses[index]
            self._state.calls += 1
            self._state.method = self._method
            self._state.url = self._url
            self._state.auth = self._headers.get("Authorization")
            self._state.account = self._headers.get("chatgpt-account-id")
            self._state.payload = self._payload
            if response.status in statuses and attempt < attempts - 1:
                continue
            return response
        if response is None:
            response = StubResponse(500, None, "no response")
        return response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class StubRetryClient:
    def __init__(self, responses: list[StubResponse], state: UsageClientState) -> None:
        self._responses = responses
        self._state = state

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, str] | None = None,
        timeout: object | None = None,
        retry_options: object | None = None,
    ) -> StubRequestContext:
        return StubRequestContext(self._responses, self._state, method, url, headers or {}, json, retry_options)


class StubCodexResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload or {
            "plan_type": "plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 12.5,
                    "reset_at": 1735689600,
                    "limit_window_seconds": 60,
                    "reset_after_seconds": 30,
                }
            },
        }


class StubCodexClient:
    def __init__(self, responses: list[StubCodexResponse] | None = None) -> None:
        self._responses = responses or [StubCodexResponse()]
        self.calls: list[dict[str, object]] = []

    async def request(self, method: str, url: str, *, route: ResolvedUpstreamRoute, **kwargs: object) -> object:
        self.calls.append({"method": method, "url": url, "route": route, **kwargs})
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]


class StubNativeResponse:
    def __init__(
        self,
        status: int,
        payload: object | None = None,
        *,
        body: bytes | None = None,
        read_error: BaseException | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self._body = body
        self._read_error = read_error
        self.headers = headers or {}
        self.read_calls = 0
        self.closed = False

    async def __aenter__(self) -> StubNativeResponse:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        self.closed = True
        return None

    async def read(self) -> bytes:
        self.read_calls += 1
        if self._read_error is not None:
            raise self._read_error
        if self._body is not None:
            return self._body
        return json.dumps(self._payload).encode()


def _usage_payload() -> dict[str, object]:
    return {
        "plan_type": "plus",
        "rate_limit": {
            "primary_window": {
                "used_percent": 12.5,
                "reset_at": 1735689600,
                "limit_window_seconds": 60,
                "reset_after_seconds": 30,
            }
        },
    }


@pytest.fixture
def usage_server() -> tuple[str, StubRetryClient, UsageClientState]:
    state = UsageClientState()
    responses = [
        StubResponse(503, None, "busy"),
        StubResponse(
            200,
            {
                "plan_type": "plus",
                "rate_limit": {
                    "primary_window": {
                        "used_percent": 12.5,
                        "reset_at": 1735689600,
                        "limit_window_seconds": 60,
                        "reset_after_seconds": 30,
                    }
                },
            },
            "",
        ),
    ]
    client = StubRetryClient(responses, state)
    return "http://usage.test/backend-api", client, state


@pytest.fixture
def failing_usage_server() -> tuple[str, StubRetryClient]:
    state = UsageClientState()
    responses = [StubResponse(503, None, "busy")]
    client = StubRetryClient(responses, state)
    return "http://usage.test/backend-api", client


@pytest.mark.asyncio
async def test_fetch_usage_retries_and_returns_payload(usage_server):
    base_url, client, state = usage_server
    data = await fetch_usage(
        access_token="access-token",
        account_id="acc_test",
        base_url=base_url,
        max_retries=1,
        timeout_seconds=2.0,
        client=cast(Any, client),
        allow_direct_egress=True,
    )
    assert data.plan_type == "plus"
    assert state.calls == 2
    assert state.auth == "Bearer access-token"
    assert state.account == "acc_test"


@pytest.mark.asyncio
async def test_fetch_usage_uses_explicit_retry_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = UsageClientState()
    client = StubRetryClient([StubResponse(200, _usage_payload(), "")], state)

    data = await fetch_usage(
        access_token="access-token",
        account_id="acc_test",
        base_url="http://usage.test",
        max_retries=0,
        client=cast(Any, client),
        allow_direct_egress=True,
    )

    assert data.plan_type == "plus"
    assert state.calls == 1


@pytest.mark.asyncio
async def test_fetch_usage_direct_egress_gate_runs_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = UsageClientState()
    client = StubRetryClient([], state)

    with pytest.raises(ValueError, match="allow_direct_egress=True"):
        await fetch_usage(
            access_token="access-token",
            account_id=None,
            base_url="http://usage.test",
            client=cast(Any, client),
        )

    assert state.calls == 0


@pytest.mark.asyncio
async def test_fetch_usage_uses_resolved_codex_route(monkeypatch: pytest.MonkeyPatch) -> None:
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    client = StubCodexClient()

    data = await fetch_usage(
        access_token="access-token",
        account_id="acc_test",
        base_url="http://usage.test/backend-api",
        timeout_seconds=2.0,
        route=route,
        codex_client=cast(Any, client),
        allow_direct_egress=True,
    )

    assert data.plan_type == "plus"
    assert client.calls[0]["route"] is route
    assert client.calls[0]["method"] == "GET"
    assert client.calls[0]["url"] == "http://usage.test/backend-api/wham/usage"


@pytest.mark.asyncio
async def test_consume_rate_limit_reset_credit_posts_payload_direct() -> None:
    state = UsageClientState()
    client = StubRetryClient(
        [StubResponse(200, {"code": "reset", "windows_reset": 2}, "")],
        state,
    )

    data = await consume_rate_limit_reset_credit(
        access_token="access-token",
        account_id="acc_test",
        redeem_request_id="redeem-123",
        base_url="http://usage.test",
        max_retries=0,
        timeout_seconds=1.0,
        client=cast(Any, client),
        allow_direct_egress=True,
    )

    assert data.code == "reset"
    assert data.windows_reset == 2
    assert state.calls == 1
    assert state.method == "POST"
    assert state.url == "http://usage.test/backend-api/wham/rate-limit-reset-credits/consume"
    assert state.auth == "Bearer access-token"
    assert state.account == "acc_test"
    assert state.payload == {"redeem_request_id": "redeem-123"}


@pytest.mark.asyncio
async def test_consume_rate_limit_reset_credit_uses_resolved_codex_route() -> None:
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    client = StubCodexClient(
        [
            StubCodexResponse(
                200,
                {"code": "already_redeemed", "windows_reset": 0},
            )
        ]
    )

    data = await consume_rate_limit_reset_credit(
        access_token="access-token",
        account_id="acc_test",
        redeem_request_id="redeem-123",
        base_url="http://usage.test/backend-api",
        max_retries=0,
        timeout_seconds=1.0,
        route=route,
        codex_client=cast(Any, client),
    )

    assert data.code == "already_redeemed"
    assert client.calls[0]["route"] is route
    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["url"] == "http://usage.test/backend-api/wham/rate-limit-reset-credits/consume"
    assert client.calls[0]["json"] == {"redeem_request_id": "redeem-123"}


@pytest.mark.asyncio
async def test_fetch_usage_retries_resolved_codex_route_retryable_status(monkeypatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.core.clients.usage.asyncio.sleep", no_sleep)
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    client = StubCodexClient(
        [
            StubCodexResponse(503, {"error": {"message": "busy"}}),
            StubCodexResponse(),
        ]
    )

    data = await fetch_usage(
        access_token="access-token",
        account_id="acc_test",
        base_url="http://usage.test/backend-api",
        max_retries=1,
        timeout_seconds=2.0,
        route=route,
        codex_client=cast(Any, client),
        allow_direct_egress=True,
    )

    assert data.plan_type == "plus"
    assert len(client.calls) == 2
    assert client.calls[0]["route"] is route
    assert client.calls[1]["route"] is route


@pytest.mark.asyncio
async def test_fetch_usage_raises_after_retries(failing_usage_server):
    base_url, client = failing_usage_server
    with pytest.raises(UsageFetchError) as excinfo:
        await fetch_usage(
            access_token="access-token",
            account_id=None,
            base_url=base_url,
            max_retries=0,
            timeout_seconds=1.0,
            client=cast(Any, client),
            allow_direct_egress=True,
        )
    exc = excinfo.value
    assert isinstance(exc, UsageFetchError)
    assert exc.status_code == 503


@pytest.mark.asyncio
async def test_fetch_usage_preserves_error_code():
    state = UsageClientState()
    responses = [
        StubResponse(
            401,
            {
                "error": {
                    "code": "account_deactivated",
                    "message": "Your OpenAI account has been deactivated.",
                }
            },
            "",
        )
    ]
    client = StubRetryClient(responses, state)

    with pytest.raises(UsageFetchError) as excinfo:
        await fetch_usage(
            access_token="access-token",
            account_id=None,
            base_url="http://usage.test/backend-api",
            max_retries=0,
            timeout_seconds=1.0,
            client=cast(Any, client),
            allow_direct_egress=True,
        )

    exc = excinfo.value
    assert exc.status_code == 401
    assert exc.code == "account_deactivated"
    assert "deactivated" in exc.message.lower()
