from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Any, cast

import aiohttp
import pytest
from aiohttp.client_reqrep import ConnectionKey
from python_socks import ProxyType

from app.core.clients import codex as codex_module
from app.core.clients.codex import (
    CodexClient,
    CodexTransportError,
    create_codex_session,
    require_route_or_direct_egress_opt_in,
)
from app.core.clients.http import _reset_shared_ssl_context, _shared_ssl_context
from app.core.upstream_proxy import ResolvedProxyEndpoint, ResolvedUpstreamRoute
from tests.unit._proxy_test_helpers import runtime_basic_auth_url

pytestmark = pytest.mark.unit


def _route_basic_auth_url(user: str, value: str, authority: str) -> str:
    return runtime_basic_auth_url(user, value, authority).replace("http://", "https://", 1)


# The Basic token aiohttp itself derives from ``https://u:p@`` userinfo (latin1).
_ROUTE_PROXY_BASIC_TOKEN = "Basic " + base64.b64encode(b"u:p").decode("latin1")


def _assert_credentialed_proxy_call(call: dict[str, Any]) -> None:
    # Credentials ride in Proxy-Authorization, never in the pooled proxy URL.
    assert call["proxy"] == "https://proxy.test:8080"
    assert call["proxy_headers"] == {"Proxy-Authorization": _ROUTE_PROXY_BASIC_TOKEN}


def _assert_credential_free_proxy_call(call: dict[str, Any], proxy_url: str) -> None:
    assert call["proxy"] == proxy_url
    assert "proxy_headers" not in call


@dataclass
class _Response:
    status_code: int = 200
    content: bytes = b'{"ok": true}'
    headers: dict[str, str] | None = None

    def json(self) -> dict[str, bool]:
        return {"ok": True}


class _Session:
    def __init__(self, *, fail_first: bool = False, fail_all: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_first = fail_first
        self.fail_all = fail_all

    async def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.fail_all:
            raise OSError("proxy " + _route_basic_auth_url("u", "p", "proxy.test:8080") + " failed")
        if self.fail_first and len(self.calls) == 1:
            raise OSError("proxy failed before response")
        return _Response(headers={"content-type": "application/json"})

    async def ws_connect(self, url: str, **kwargs: Any) -> object:
        self.calls.append({"url": url, **kwargs})
        return object()


class _HandshakeFailure(Exception):
    status = 426


class _WsFailSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def ws_connect(self, url: str, **kwargs: Any) -> object:
        self.calls.append({"url": url, **kwargs})
        raise _HandshakeFailure("Upgrade Required")


class _WsContext:
    def __init__(self) -> None:
        self.websocket = object()
        self.exited = False

    async def __aenter__(self) -> object:
        return self.websocket

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.exited = True


class _SocksWsSession:
    latest: "_SocksWsSession | None" = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls: list[dict[str, Any]] = []
        self.context = _WsContext()
        self.closed = False
        _SocksWsSession.latest = self

    def ws_connect(self, url: str, **kwargs: Any) -> _WsContext:
        self.calls.append({"url": url, **kwargs})
        return self.context

    async def close(self) -> None:
        self.closed = True


class _SocksConnector:
    calls: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.fixture
def route() -> ResolvedUpstreamRoute:
    return ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "https", "proxy.test", 8080, "u", "p"),
        fallbacks=(ResolvedProxyEndpoint("ep_2", "http", "proxy-two.test", 8081),),
    )


@pytest.mark.asyncio
async def test_request_requires_route() -> None:
    client = CodexClient(_Session())
    with pytest.raises(ValueError, match="resolved upstream proxy route"):
        await client.request("GET", "https://upstream.test", route=cast(Any, None))


def test_direct_egress_requires_explicit_opt_in() -> None:
    with pytest.raises(ValueError, match="allow_direct_egress=True"):
        require_route_or_direct_egress_opt_in(
            route=None,
            allow_direct_egress=False,
            operation="test operation",
        )

    require_route_or_direct_egress_opt_in(
        route=None,
        allow_direct_egress=True,
        operation="test operation",
    )


@pytest.mark.asyncio
async def test_request_passes_resolver_proxy_and_builtin_fingerprint(route: ResolvedUpstreamRoute) -> None:
    session = _Session()
    client = CodexClient(session)

    response = await client.request("POST", "https://upstream.test", route=route, json={"x": 1})

    _assert_credentialed_proxy_call(session.calls[0])
    assert session.calls[0]["json"] == {"x": 1}
    assert response.content == b'{"ok": true}'


@pytest.mark.asyncio
async def test_streaming_request_can_opt_out_of_response_buffering(route: ResolvedUpstreamRoute) -> None:
    session = _Session()
    client = CodexClient(session)

    result = await client.request_with_route_metadata(
        "POST",
        "https://upstream.test",
        route=route,
        buffer_response=False,
        json={"x": 1},
    )

    _assert_credentialed_proxy_call(session.calls[0])
    assert "buffer_response" not in session.calls[0]
    assert isinstance(result.response, _Response)


@pytest.mark.asyncio
async def test_request_converts_legacy_files_payload_to_form_data(route: ResolvedUpstreamRoute) -> None:
    session = _Session()
    client = CodexClient(session)

    await client.request_with_route_metadata(
        "POST",
        "https://upstream.test/transcribe",
        route=route,
        files={"file": ("audio.wav", b"abc", "audio/wav")},
        data={"prompt": "summarize"},
    )

    assert "files" not in session.calls[0]
    assert isinstance(session.calls[0]["data"], aiohttp.FormData)
    _assert_credentialed_proxy_call(session.calls[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("override", ["akamai", "extra_fp", "impersonate", "ja3", "proxies", "proxy", "proxy_headers"])
async def test_runtime_route_and_fingerprint_overrides_are_rejected(
    route: ResolvedUpstreamRoute,
    override: str,
) -> None:
    client = CodexClient(_Session())
    with pytest.raises(ValueError, match="controlled centrally"):
        await client.request("GET", "https://upstream.test", route=route, **{override: "bad"})


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "GET"])
async def test_credentialed_route_requires_tls_target_for_request(route: ResolvedUpstreamRoute, method: str) -> None:
    # aiohttp forwards proxy_headers only on the CONNECT tunnel, so a plaintext
    # target would silently drop the proxy credentials; fail closed before any
    # dispatch. The idempotent GET must not slip through the credential-free
    # fallback endpoint either (the route fixture carries one). Surfaces as a
    # connect-phase transport error so callers answer upstream-unavailable.
    session = _Session()
    client = CodexClient(session)

    with pytest.raises(CodexTransportError, match="https/wss upstream target") as exc_info:
        await client.request(method, "http://upstream.test", route=route, json={"x": 1})

    assert session.calls == []
    assert "proxy.test" not in str(exc_info.value)
    assert exc_info.value.failure_phase == "connect"
    assert exc_info.value.retryable_same_contract is False


@pytest.mark.asyncio
async def test_credentialed_route_requires_tls_target_for_ws_connect(route: ResolvedUpstreamRoute) -> None:
    session = _Session()
    client = CodexClient(session)

    with pytest.raises(CodexTransportError, match="https/wss upstream target"):
        await client.ws_connect("ws://upstream.test", route=route)

    assert session.calls == []


@pytest.mark.asyncio
async def test_credentialed_route_requires_tls_target_for_ws_open_with_fallback(route: ResolvedUpstreamRoute) -> None:
    session = _Session()
    client = CodexClient(session)

    with pytest.raises(CodexTransportError, match="https/wss upstream target"):
        await client.open_ws_with_route_metadata("ws://upstream.test", route=route)

    assert session.calls == []


@pytest.mark.asyncio
async def test_credential_free_route_allows_plaintext_target() -> None:
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "https", "proxy.test", 8080),
    )
    session = _Session()
    client = CodexClient(session)

    await client.request("GET", "http://upstream.test", route=route)

    _assert_credential_free_proxy_call(session.calls[0], "https://proxy.test:8080")


@pytest.mark.asyncio
async def test_pre_response_failure_uses_same_pool_fallback(route: ResolvedUpstreamRoute) -> None:
    session = _Session(fail_first=True)
    client = CodexClient(session)

    result = await client.request_with_route_metadata("GET", "https://upstream.test", route=route)

    assert result.fallback_used is True
    assert result.route.endpoint_id == "ep_2"
    _assert_credentialed_proxy_call(session.calls[0])
    _assert_credential_free_proxy_call(session.calls[1], "http://proxy-two.test:8081")


@pytest.mark.asyncio
async def test_non_idempotent_request_failure_does_not_fallback(route: ResolvedUpstreamRoute) -> None:
    session = _Session(fail_first=True)
    client = CodexClient(session)

    with pytest.raises(RuntimeError) as exc_info:
        await client.request_with_route_metadata("POST", "https://upstream.test", route=route, json={"x": 1})

    assert "ep_1" in str(exc_info.value)
    assert len(session.calls) == 1
    _assert_credentialed_proxy_call(session.calls[0])


def _proxy_connect_error() -> aiohttp.ClientProxyConnectionError:
    key = ConnectionKey("proxy.test", 8080, False, False, None, None, None)
    return aiohttp.ClientProxyConnectionError(key, OSError("proxy credentials must stay private"))


class _ProxyConnectFailureSession(_Session):
    def __init__(self, *, fail_all: bool = False) -> None:
        super().__init__()
        self.fail_all_proxy_connects = fail_all

    async def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.fail_all_proxy_connects or len(self.calls) == 1:
            raise _proxy_connect_error()
        return _Response(headers={"content-type": "application/json"})


@pytest.mark.asyncio
async def test_non_idempotent_pre_dispatch_proxy_failure_uses_same_pool_fallback(
    route: ResolvedUpstreamRoute,
) -> None:
    session = _ProxyConnectFailureSession()
    client = CodexClient(session)

    result = await client.request_with_route_metadata(
        "POST",
        "https://upstream.test",
        route=route,
        buffer_response=False,
        json={"x": 1},
    )

    assert result.fallback_used is True
    assert result.route.endpoint_id == "ep_2"
    _assert_credentialed_proxy_call(session.calls[0])
    _assert_credential_free_proxy_call(session.calls[1], "http://proxy-two.test:8081")


@pytest.mark.asyncio
async def test_exhausted_proxy_connect_failures_preserve_pre_dispatch_provenance(
    route: ResolvedUpstreamRoute,
) -> None:
    client = CodexClient(_ProxyConnectFailureSession(fail_all=True))

    with pytest.raises(CodexTransportError) as exc_info:
        await client.request_with_route_metadata(
            "POST",
            "https://upstream.test",
            route=route,
            buffer_response=False,
            json={"x": 1},
        )

    assert exc_info.value.retryable_same_contract is True
    assert exc_info.value.failure_phase == "connect"
    assert "ClientProxyConnectionError" in str(exc_info.value)
    assert "credentials must stay private" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_non_idempotent_tls_verification_connect_failure_does_not_fallback(
    route: ResolvedUpstreamRoute,
) -> None:
    connection_key = ConnectionKey("proxy.test", 8080, True, True, None, None, None)

    class _TLSFailSession(_Session):
        async def request(self, method: str, url: str, **kwargs: Any) -> _Response:
            self.calls.append({"method": method, "url": url, **kwargs})
            raise aiohttp.ClientConnectorCertificateError(connection_key, ValueError("certificate verify failed"))

    session = _TLSFailSession()
    client = CodexClient(session)

    with pytest.raises(CodexTransportError) as exc_info:
        await client.request_with_route_metadata(
            "POST",
            "https://upstream.test",
            route=route,
            buffer_response=False,
            json={"x": 1},
        )

    assert len(session.calls) == 1
    assert exc_info.value.is_tls_verification_failure is True


@pytest.mark.asyncio
async def test_transport_errors_do_not_expose_proxy_credentials(route: ResolvedUpstreamRoute) -> None:
    client = CodexClient(_Session(fail_all=True))

    with pytest.raises(RuntimeError) as exc_info:
        await client.request("GET", "https://upstream.test", route=route)

    message = str(exc_info.value)
    assert "ep_2" in message
    assert "OSError" in message
    assert "u:p" not in message
    assert "proxy.test:8080" not in message


@pytest.mark.asyncio
async def test_websocket_transport_error_preserves_handshake_status(route: ResolvedUpstreamRoute) -> None:
    session = _WsFailSession()
    client = CodexClient(session)

    with pytest.raises(RuntimeError) as exc_info:
        await client.open_ws_with_route_metadata("wss://upstream.test", route=route)

    assert getattr(exc_info.value, "status_code") == 426
    assert len(session.calls) == 2


@pytest.mark.asyncio
async def test_routed_websocket_preserves_noncompressed_aiohttp_semantics(
    route: ResolvedUpstreamRoute,
) -> None:
    session = _Session()
    client = CodexClient(session)

    result = await client.open_ws_with_route_metadata(
        "wss://upstream.test/responses",
        route=route,
        compress=0,
    )

    assert result.route == route
    assert session.calls[0]["compress"] == 0


@pytest.mark.asyncio
async def test_websocket_definitive_handshake_status_can_disable_route_replay(
    route: ResolvedUpstreamRoute,
) -> None:
    session = _WsFailSession()
    client = CodexClient(session)

    with pytest.raises(RuntimeError) as exc_info:
        await client.open_ws_with_route_metadata(
            "wss://upstream.test",
            route=route,
            retry_handshake_status=False,
        )

    assert getattr(exc_info.value, "status_code") == 426
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_websocket_network_error_can_disable_route_fallback(
    route: ResolvedUpstreamRoute,
) -> None:
    class _NetworkFailSession:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def ws_connect(self, url: str, **kwargs: Any) -> object:
            self.calls.append({"url": url, **kwargs})
            raise OSError("network unavailable")

    session = _NetworkFailSession()
    client = CodexClient(session)

    with pytest.raises(RuntimeError) as exc_info:
        await client.open_ws_with_route_metadata(
            "wss://upstream.test",
            route=route,
            retry_network_errors=False,
        )

    assert getattr(exc_info.value, "status_code", None) is None
    assert getattr(exc_info.value, "retryable_same_contract") is False
    assert len(session.calls) == 1
    assert "retry_network_errors" not in session.calls[0]


@pytest.mark.asyncio
async def test_websocket_network_error_uses_route_fallback_by_default(
    monkeypatch: pytest.MonkeyPatch,
    route: ResolvedUpstreamRoute,
) -> None:
    connection_key = ConnectionKey("proxy.test", 8080, False, False, None, None, None)
    session = aiohttp.ClientSession()
    calls: list[dict[str, Any]] = []

    async def fake_ws_connect(url: str, **kwargs: Any) -> object:
        calls.append({"url": url, **kwargs})
        if len(calls) == 1:
            raise aiohttp.ClientProxyConnectionError(connection_key, ConnectionRefusedError("connection refused"))
        return object()

    monkeypatch.setattr(session, "_ws_connect", fake_ws_connect)
    client = CodexClient(session)
    try:
        result = await client.open_ws_with_route_metadata(
            "wss://upstream.test",
            route=route,
        )
    finally:
        await client.close()

    assert len(calls) == 2
    assert result.fallback_used is True
    assert result.route.endpoint_id == "ep_2"


@pytest.mark.asyncio
async def test_websocket_awaitable_connect_failure_preserves_original_transport_error(
    monkeypatch: pytest.MonkeyPatch,
    route: ResolvedUpstreamRoute,
) -> None:
    connection_key = ConnectionKey("proxy.test", 8080, False, False, None, None, None)
    session = aiohttp.ClientSession()
    calls: list[dict[str, Any]] = []

    async def fail_ws_connect(url: str, **kwargs: Any) -> object:
        calls.append({"url": url, **kwargs})
        raise aiohttp.ClientProxyConnectionError(connection_key, ConnectionRefusedError("connection refused"))

    monkeypatch.setattr(session, "_ws_connect", fail_ws_connect)
    client = CodexClient(session)
    try:
        with pytest.raises(CodexTransportError) as exc_info:
            await client.open_ws_with_route_metadata(
                "wss://upstream.test",
                route=route,
                retry_network_errors=False,
            )
    finally:
        await client.close()

    assert str(exc_info.value) == (
        "Codex upstream websocket failed via proxy endpoint ep_1: ClientProxyConnectionError"
    )
    assert exc_info.value.failure_phase == "connect"
    assert exc_info.value.retryable_same_contract is False
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_websocket_success_returns_caller_owned_entered_context(
    route: ResolvedUpstreamRoute,
) -> None:
    class _WsContextSession:
        def __init__(self) -> None:
            self.context = _WsContext()

        def ws_connect(self, *_args: object, **_kwargs: object) -> _WsContext:
            return self.context

    session = _WsContextSession()
    result = await CodexClient(session).open_ws_with_route_metadata("wss://upstream.test", route=route)

    assert result.websocket is session.context.websocket
    assert result.context is session.context

    await result.context.__aexit__(None, None, None)

    assert session.context.exited is True


@pytest.mark.asyncio
async def test_websocket_connector_error_preserves_pre_dispatch_retry_provenance(
    route: ResolvedUpstreamRoute,
) -> None:
    connection_key = ConnectionKey("upstream.test", 443, True, True, None, None, None)

    class _ConnectorFailSession:
        def ws_connect(self, *_args: object, **_kwargs: object) -> object:
            raise aiohttp.ClientConnectorError(connection_key, ConnectionRefusedError("connection refused"))

    client = CodexClient(_ConnectorFailSession())

    with pytest.raises(RuntimeError) as exc_info:
        await client.open_ws_with_route_metadata("wss://upstream.test", route=route, compress=15)

    assert getattr(exc_info.value, "failure_phase") == "connect"
    assert getattr(exc_info.value, "retryable_same_contract") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("scheme", ["socks5", "socks5h"])
async def test_socks_websocket_uses_proxy_connector_and_closes_session(
    monkeypatch: pytest.MonkeyPatch,
    scheme: str,
) -> None:
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", scheme, "proxy.test", 1080),
    )
    _SocksConnector.calls = []
    _SocksWsSession.latest = None
    monkeypatch.setattr("app.core.clients.codex.ProxyConnector", _SocksConnector)
    monkeypatch.setattr("app.core.clients.codex.aiohttp.ClientSession", _SocksWsSession)
    client = CodexClient(_Session())

    result = await client.open_ws_with_route_metadata("wss://upstream.test", route=route, heartbeat=30)

    session = _SocksWsSession.latest
    assert session is not None
    assert _SocksConnector.calls[0]["ssl"] is not None
    assert _SocksConnector.calls[0] | {"ssl": "present"} == {
        "host": "proxy.test",
        "port": 1080,
        "proxy_type": ProxyType.SOCKS5,
        "username": None,
        "password": None,
        "rdns": True,
        "ssl": "present",
    }
    assert session.calls == [{"url": "wss://upstream.test", "heartbeat": 30}]
    assert "proxy" not in session.calls[0]
    assert result.websocket is session.context.websocket

    await result.context.__aexit__(None, None, None)

    assert session.context.exited is True
    assert session.closed is True


@pytest.mark.asyncio
async def test_socks_websocket_cancel_during_enter_closes_local_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "socks5h", "proxy.test", 1080),
    )
    entered = asyncio.Event()

    class _HangingWsContext:
        def __init__(self) -> None:
            self.exited = False
            self.owned = False

        async def __aenter__(self) -> object:
            entered.set()
            await asyncio.Event().wait()
            raise AssertionError("hanging enter must be cancelled")

        async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
            self.exited = True

    class _HangingSocksWsSession:
        latest: "_HangingSocksWsSession | None" = None

        def __init__(self, **kwargs: Any) -> None:
            del kwargs
            self.context = _HangingWsContext()
            self.closed = 0
            _HangingSocksWsSession.latest = self

        def ws_connect(self, url: str, **kwargs: Any) -> _HangingWsContext:
            del url, kwargs
            return self.context

        async def close(self) -> None:
            self.closed += 1

    _SocksConnector.calls = []
    monkeypatch.setattr("app.core.clients.codex.ProxyConnector", _SocksConnector)
    monkeypatch.setattr("app.core.clients.codex.aiohttp.ClientSession", _HangingSocksWsSession)
    client = CodexClient(_Session())

    task = asyncio.create_task(client.open_ws_with_route_metadata("wss://upstream.test", route=route))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    session = _HangingSocksWsSession.latest
    assert session is not None
    assert session.closed == 1
    assert session.context.exited is False
    assert session.context.owned is False


async def test_socks_session_owned_response_releases_before_closing_session() -> None:
    order: list[str] = []

    async def _noop() -> None:
        return None

    class _Content:
        async def iter_chunked(self, size: int):
            del size
            yield b"data: first\n\n"
            yield b"data: second\n\n"

    class _RawResponse:
        status = 200
        headers: dict[str, str] = {}
        content = _Content()

        def release(self) -> Any:
            order.append("release")
            return _noop()

    class _Session:
        async def close(self) -> None:
            order.append("session_close")

    owned = codex_module._SessionOwnedResponse(_RawResponse(), cast(Any, _Session()))

    async for _ in owned.content.iter_chunked(1024):
        break
    await owned.release()

    assert order == ["release", "session_close"]


@pytest.mark.asyncio
async def test_create_codex_session_connectors_share_one_ssl_context() -> None:
    _reset_shared_ssl_context()
    first = create_codex_session()
    second = create_codex_session()
    try:
        assert first.connector._ssl is second.connector._ssl
        assert first.connector._ssl is _shared_ssl_context()
    finally:
        await first.close()
        await second.close()
        _reset_shared_ssl_context()


@pytest.mark.asyncio
async def test_socks_proxy_connector_reuses_shared_ssl_context() -> None:
    _reset_shared_ssl_context()
    endpoint = ResolvedProxyEndpoint("ep_1", "socks5h", "proxy.test", 1080)
    connector = codex_module._socks_proxy_connector(endpoint)
    try:
        assert connector._ssl is _shared_ssl_context()
        assert connector._rdns is True
    finally:
        await connector.close()
        _reset_shared_ssl_context()
