from __future__ import annotations

import asyncio
import json
from typing import Literal, NotRequired, TypedDict

import pytest
import pytest_asyncio
from aiohttp import web
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.config.settings import get_settings
from app.db.models import RequestLog, SwissAIAttempt, SwissAIContinuation, SwissAIKeyState, SwissAILease
from app.db.session import get_background_session
from app.modules.swissai import repository as repo
from app.modules.swissai.policy import PoolSettings


class UpstreamState(TypedDict):
    statuses: list[int]
    mode: Literal["json", "sse", "stall", "disconnect", "json_trickle", "sse_output", "sse_initial_usage", "sse_failed"]
    delay: float
    error_size: int
    input_tokens: NotRequired[int]
    output_tokens: NotRequired[int]
    output_gate: NotRequired[asyncio.Event]
    disconnect_gate: NotRequired[asyncio.Event]
    response_id: NotRequired[str]
    probe_status: NotRequired[int]
    probe_message: NotRequired[str]


@pytest_asyncio.fixture
async def pool(app_instance, monkeypatch, tmp_path):
    calls = []
    state: UpstreamState = {"statuses": [], "mode": "json", "delay": 0.0, "error_size": 0}

    async def upstream(request):
        if request.path == "/v1/models":
            return web.json_response({"object": "list", "data": [{"id": "Apertus-test", "object": "model"}]})
        if request.path == "/v1/profile":
            return web.json_response({"detail": "Invalid access token"}, status=401)
        body = await request.read()
        if request.path == "/v1/chat/completions" and json.loads(body) == {
            "model": "__swissai_lb_auth_probe__",
            "messages": [],
        }:
            return web.json_response(
                {
                    "error": {
                        "type": "invalid_request_error",
                        "message": state.get("probe_message", "Model '__swissai_lb_auth_probe__' not found."),
                    }
                },
                status=state.get("probe_status", 404),
            )
        calls.append((request.headers.get("Authorization"), body, request.path))
        status = state["statuses"].pop(0) if state["statuses"] else 200
        if status != 200:
            if state.get("error_size"):
                return web.Response(status=status, body=b"x" * state["error_size"], headers={"Retry-After": "60"})
            return web.json_response(
                {
                    "error": {
                        "message": "provider error " + request.headers.get("Authorization", ""),
                        "code": "test_failure",
                    }
                },
                status=status,
                headers={"Retry-After": "60"},
            )
        if state["mode"] in {"sse", "stall", "disconnect", "sse_output", "sse_initial_usage", "sse_failed"}:
            response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await response.prepare(request)
            if state["mode"] == "stall" and len(calls) == 1:
                await asyncio.sleep(0.5)
            try:
                created = b'data: {"type":"response.created","response":{"id":"resp_test"}}\n\n'
                if state["mode"] == "sse_initial_usage":
                    created = (
                        b'data: {"type":"response.created","response":{"id":"resp_test",'
                        b'"usage":{"input_tokens":0,"output_tokens":0}}}\n\n'
                    )
                await response.write(created)
                if state["mode"] == "disconnect":
                    gate = state.get("disconnect_gate")
                    if gate is not None:
                        await gate.wait()
                    request.transport.close()
                    return response
                if state["mode"] == "sse_output":
                    gate = state.get("output_gate")
                    if gate is not None:
                        await gate.wait()
                    await response.write(b'data: {"type":"response.output_text.delta","delta":"Hello"}\n\n')
                completed = b'data: {"type":"response.completed","response":{"id":"resp_test"}}\n\n'
                if state["mode"] != "sse_initial_usage":
                    completed = (
                        b'data: {"type":"response.completed","response":{"id":"resp_test",'
                        b'"usage":{"input_tokens":2,"output_tokens":3}}}\n\n'
                    )
                if state["mode"] == "sse_failed":
                    completed = (
                        b'data: {"type":"response.failed","response":{"id":"resp_test","status":"failed",'
                        b'"usage":{"input_tokens":2,"output_tokens":3}}}\n\n'
                    )
                await response.write(completed)
                await response.write_eof()
            except (ConnectionError, RuntimeError):
                pass
            return response
        if state["mode"] == "json_trickle":
            response = web.StreamResponse(headers={"Content-Type": "application/json"})
            await response.prepare(request)
            await response.write(b'{"id":')
            await asyncio.sleep(state["delay"])
            try:
                await response.write(b'"resp_test"}')
                await response.write_eof()
            except (ConnectionError, RuntimeError):
                pass
            return response
        await asyncio.sleep(state["delay"])
        return web.json_response(
            {
                "id": state.get("response_id", "resp_test"),
                "object": "response",
                "usage": {"input_tokens": state.get("input_tokens", 2), "output_tokens": state.get("output_tokens", 3)},
                "output": [],
            }
        )

    application = web.Application()
    application.router.add_route("*", "/{path:.*}", upstream)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    monkeypatch.setenv("SWISSAI_LB_UPSTREAM_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("SWISSAI_LB_ALLOW_INSECURE_UPSTREAM", "true")
    monkeypatch.setenv("SWISSAI_LB_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        async with app_instance.router.lifespan_context(app_instance):
            async with AsyncClient(transport=ASGITransport(app_instance), base_url="http://testserver") as client:
                keys = []
                for i in range(3):
                    response = await client.post(
                        "/api/swissai-keys",
                        json={"name": f"key {i}", "apiKey": f"sk-rc-fake-key-{i}-00000", "maxConcurrency": 1},
                    )
                    assert response.status_code == 201, response.text
                    assert "sk-rc-fake" not in response.text
                    keys.append(response.json()["id"])
                yield client, keys, calls, state
    finally:
        await runner.cleanup()
        get_settings.cache_clear()


async def lease_count():
    async with get_background_session() as session:
        return await session.scalar(select(func.count()).select_from(SwissAILease))


@pytest.mark.parametrize("status", [401, 408, 429, 500, 502, 503, 504])
async def test_retry_matrix_and_one_log(pool, status):
    client, keys, calls, state = pool
    state["statuses"] = [status, 200]
    body = b'{"model":"Apertus-test", "input": "hello"}'
    response = await client.post("/v1/responses/", content=body)
    assert response.status_code == 200, response.text
    assert len(calls) == 2
    assert calls[0][0] != calls[1][0]
    assert calls[0][1] == calls[1][1] == body
    assert await lease_count() == 0
    async with get_background_session() as session:
        logs = list(await session.scalars(select(RequestLog)))
        attempts = list(await session.scalars(select(SwissAIAttempt).order_by(SwissAIAttempt.attempt_index)))
        assert len(logs) == 1 and len(attempts) == 2
        assert logs[0].cost_usd is None
        assert logs[0].input_tokens == 2
        failed_key = await session.get(SwissAIKeyState, attempts[0].source_id)
        assert failed_key is not None
        if status == 401:
            assert failed_key.invalid_at is not None
        if status == 429:
            assert failed_key.cooldown_until is not None


@pytest.mark.parametrize("status", [400, 403, 404, 409, 422])
async def test_request_failures_never_rotate_and_errors_redacted(pool, status):
    client, _, calls, state = pool
    state["statuses"] = [status]
    response = await client.post("/v1/chat/completions", json={"model": "Apertus-test", "messages": []})
    assert response.status_code == status
    assert "sk-rc-" not in response.text
    assert len(calls) == 1
    assert await lease_count() == 0


async def test_all_keys_fail_attempt_budget(pool):
    client, _, calls, state = pool
    state["statuses"] = [503] * 5
    response = await client.post("/v1/completions", json={"model": "Apertus-test", "prompt": "hi"})
    assert response.status_code == 503
    assert len(calls) == 3
    assert len({auth for auth, _, _ in calls}) == 3
    assert await lease_count() == 0


async def test_first_byte_timeout_rotates_before_commit(pool):
    client, _, calls, state = pool
    state["mode"] = "stall"
    await repo.save_pool_settings(PoolSettings(first_byte_timeout_seconds=0.1))
    response = await client.post("/v1/responses", json={"model": "Apertus-test", "stream": True})
    assert response.status_code == 200, response.text
    assert "response.completed" in response.text
    assert len(calls) == 2
    assert await lease_count() == 0


async def test_concurrent_requests_obey_caps(pool):
    client, _, calls, state = pool
    state["delay"] = 0.1
    results = await asyncio.gather(
        *(client.post("/v1/embeddings", json={"model": "Apertus-test", "input": "hi"}) for _ in range(3))
    )
    assert all(r.status_code == 200 for r in results)
    assert len({auth for auth, _, _ in calls}) == 3
    assert await lease_count() == 0


async def test_continuation_owner_never_changes(pool):
    client, keys, calls, _ = pool
    response = await client.post("/v1/responses", json={"model": "Apertus-test", "input": "hi"})
    assert response.status_code == 200
    async with get_background_session() as session:
        ownership = await session.get(SwissAIContinuation, "resp_test")
        assert ownership is not None
        owner = ownership.source_id
    response = await client.post(f"/api/swissai-keys/{owner}/pause")
    assert response.status_code == 200
    response = await client.post(
        "/v1/responses", json={"model": "Apertus-test", "previous_response_id": "resp_test", "input": "next"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "continuation_owner_unavailable"
    assert len(calls) == 1


async def test_sse_usage_and_ownership_are_collected(pool):
    client, _, calls, state = pool
    state["mode"] = "sse"
    response = await client.post("/v1/responses", json={"model": "Apertus-test", "stream": True})
    assert response.status_code == 200
    async with get_background_session() as session:
        log = await session.scalar(select(RequestLog))
        assert log is not None
        assert log.input_tokens == 2 and log.output_tokens == 3
        assert await session.get(SwissAIContinuation, "resp_test") is not None
    assert await lease_count() == 0


async def test_single_key_never_fails_over(pool):
    client, keys, calls, state = pool
    await repo.save_pool_settings(PoolSettings(strategy="single_key", single_key_id=keys[0]))
    state["statuses"] = [429, 200]
    response = await client.post("/v1/responses", json={"model": "Apertus-test"})
    assert response.status_code == 429
    assert len(calls) == 1
    assert await lease_count() == 0


async def test_cancel_during_body_read_never_rotates_and_releases_lease(pool):
    client, _, calls, state = pool
    state["delay"] = 5
    task = asyncio.create_task(client.post("/v1/responses", json={"model": "Apertus-test"}))
    for _ in range(100):
        if calls:
            break
        await asyncio.sleep(0.01)
    assert calls
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) == 1
    assert await lease_count() == 0


@pytest.mark.parametrize("limited", [False, True])
async def test_midstream_disconnect_never_rotates(pool, monkeypatch, limited):
    from app.modules.swissai.proxy import Rejected, SwissAIResponse

    client, _, calls, state = pool
    state["mode"] = "disconnect"
    visible, disconnect = asyncio.Event(), asyncio.Event()
    state["disconnect_gate"] = disconnect
    headers = {}
    if limited:
        created = await client.post(
            "/api/api-keys",
            json={
                "name": "stream limit",
                "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 100000}],
            },
        )
        assert created.status_code == 200
        headers = {"Authorization": "Bearer " + created.json()["key"]}
        assert (await client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
    original = SwissAIResponse.__call__

    async def observe_output(response, scope, receive, send):
        async def observed_send(message):
            await send(message)
            if message["type"] == "http.response.body" and message.get("body"):
                visible.set()

        await original(response, scope, receive, observed_send)

    monkeypatch.setattr(SwissAIResponse, "__call__", observe_output)
    task = asyncio.create_task(
        client.post("/v1/responses", json={"model": "Apertus-test", "stream": True}, headers=headers)
    )
    try:
        await asyncio.wait_for(visible.wait(), 3)
        disconnect.set()
        with pytest.raises(Rejected) as raised:
            await asyncio.wait_for(task, 3)
        assert raised.value.code == "stream_interrupted"
        assert len(calls) == 1
        assert await lease_count() == 0
        async with get_background_session() as session:
            row = (await session.scalars(select(RequestLog))).one()
            assert row.error_code == "stream_interrupted"
            assert row.input_tokens is row.output_tokens is None
        if limited:
            keys = await client.get("/api/api-keys")
            assert keys.json()[0]["limits"][0]["currentValue"] > 0
    finally:
        disconnect.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_absolute_deadline_applies_to_nonstream_body(pool, monkeypatch):
    client, _, calls, state = pool
    monkeypatch.setenv("SWISSAI_LB_PROXY_REQUEST_BUDGET_SECONDS", "0.1")
    get_settings.cache_clear()
    state["delay"] = 1
    state["mode"] = "json_trickle"
    response = await client.post("/v1/responses", json={"model": "Apertus-test"})
    assert response.status_code == 504, response.text
    assert len(calls) == 1
    assert await lease_count() == 0


@pytest.mark.parametrize("scope", ["models", "keys"])
async def test_empty_client_allowlist_denies_everything(pool, scope):
    client, _, calls, _ = pool
    created = await client.post(
        "/api/api-keys",
        json={
            "name": "restricted",
            **({"allowedModels": []} if scope == "models" else {"assignedSourceIds": []}),
        },
    )
    assert created.status_code == 200, created.text
    token = created.json()["key"]
    enabled = await client.put("/api/settings", json={"apiKeyAuthEnabled": True})
    assert enabled.status_code == 200, enabled.text
    response = await client.post(
        "/v1/responses", json={"model": "Apertus-test"}, headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == (403 if scope == "models" else 503), response.text
    assert not calls


async def test_client_key_auth_can_be_turned_on_and_off(pool):
    client, _, _, _ = pool
    enabled = await client.put("/api/settings", json={"apiKeyAuthEnabled": True})
    assert enabled.status_code == 200, enabled.text
    for path in ("/v1/responses", "/v1/chat/completions", "/v1/completions", "/v1/embeddings"):
        response = await client.post(path, json={"model": "Apertus-test"})
        assert response.status_code == 401
    assert (await client.get("/v1/models")).status_code == 401
    created = await client.post("/api/api-keys", json={"name": "SDK"})
    token = created.json()["key"]
    response = await client.post(
        "/v1/responses", json={"model": "Apertus-test"}, headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 200, response.text
    disabled = await client.put("/api/settings", json={"apiKeyAuthEnabled": False})
    assert disabled.status_code == 200
    assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200


async def test_client_usage_settles_once_after_failover(pool):
    client, _, calls, state = pool
    state["statuses"] = [429, 200]
    created = await client.post(
        "/api/api-keys",
        json={
            "name": "limited",
            "limits": [
                {
                    "limitType": "total_tokens",
                    "limitWindow": "weekly",
                    "maxValue": 100000,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    token = created.json()["key"]
    assert (await client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
    response = await client.post(
        "/v1/responses", json={"model": "Apertus-test"}, headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 200, response.text
    keys = await client.get("/api/api-keys")
    assert keys.json()[0]["limits"][0]["currentValue"] == 5
    assert len(calls) == 2


async def test_duplicate_external_request_ids_do_not_collide(pool):
    client, _, calls, _ = pool
    for _ in range(2):
        response = await client.post(
            "/v1/embeddings", json={"model": "Apertus-test"}, headers={"X-Request-ID": "reused"}
        )
        assert response.status_code == 200
    async with get_background_session() as session:
        logs = list(await session.scalars(select(RequestLog)))
        assert len(logs) == 2
        assert logs[0].request_id != logs[1].request_id


async def test_key_replacement_does_not_rebind_continuations(pool):
    client, _, _, _ = pool
    assert (await client.post("/v1/responses", json={"model": "Apertus-test"})).status_code == 200
    async with get_background_session() as session:
        ownership = await session.get(SwissAIContinuation, "resp_test")
        assert ownership is not None
        owner = ownership.source_id
    replaced = await client.patch(f"/api/swissai-keys/{owner}", json={"apiKey": "sk-rc-replacement-fake-00000"})
    assert replaced.status_code == 200
    response = await client.post("/v1/responses", json={"model": "Apertus-test", "previous_response_id": "resp_test"})
    assert response.status_code == 503


async def test_metrics_are_populated_and_have_no_secrets(pool):
    client, _, _, _ = pool
    assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "swissai_lb_requests_total" in response.text
    assert "swissai_lb_key_inflight" in response.text
    assert "sk-rc" not in response.text


async def test_invalid_credential_shape_is_not_echoed(pool):
    client, _, _, _ = pool
    secret = "sk-rc-invalid-shape-secret-0000"
    response = await client.post("/api/swissai-keys", json={"name": "bad", "apiKey": {"token": secret}})
    assert response.status_code == 422
    assert secret not in response.text


@pytest.mark.parametrize("status", [400, 429, 503])
async def test_oversized_upstream_error_body_never_leaks_a_lease(pool, status):
    client, _, calls, state = pool
    state["statuses"] = [status, 200]
    state["error_size"] = 100000
    response = await client.post("/v1/embeddings", json={"model": "Apertus-test"})
    assert response.status_code == (400 if status == 400 else 200)
    assert len(calls) == (1 if status == 400 else 2)
    assert await lease_count() == 0


async def test_anonymous_lan_is_explicit_and_client_auth_overrides_it(pool, app_instance, monkeypatch):
    client, _, _, _ = pool
    async with AsyncClient(
        transport=ASGITransport(app_instance, client=("192.168.1.30", 12345)), base_url="http://lan-proxy"
    ) as remote:
        assert (await remote.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 401
        monkeypatch.setenv("SWISSAI_LB_PROXY_ALLOW_ANONYMOUS_LAN", "true")
        get_settings.cache_clear()
        allowed = await remote.post("/v1/embeddings", json={"model": "Apertus-test"})
        assert allowed.status_code == 200, allowed.text
        assert (await client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
        assert (await remote.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 401


async def test_response_headers_are_safe_to_inspect_before_dispatch(pool, monkeypatch):
    from app.modules.swissai.proxy import SwissAIResponse

    original = SwissAIResponse.__call__

    async def inspect_headers(response, scope, receive, send):
        assert response.headers.get("content-type") == "application/json"
        await original(response, scope, receive, send)

    monkeypatch.setattr(SwissAIResponse, "__call__", inspect_headers)
    client, _, _, _ = pool
    response = await client.post("/v1/responses", json={"model": "Apertus-test"})
    assert response.status_code == 200, response.text
    assert await lease_count() == 0


async def test_duplicate_upstream_secret_is_rejected_and_stored_encrypted(pool):
    from app.db.models import ModelSource

    client, keys, _, _ = pool
    secret = "sk-rc-fake-key-0-00000"
    response = await client.post("/api/swissai-keys", json={"name": "duplicate", "apiKey": secret})
    assert response.status_code == 400
    assert secret not in response.text
    assert len((await client.get("/api/swissai-keys")).json()) == 3
    async with get_background_session() as session:
        stored = await session.get(ModelSource, keys[0])
        assert stored is not None and stored.api_key_encrypted is not None
        assert secret.encode() not in stored.api_key_encrypted


@pytest.mark.parametrize("removed", ["accounts:write", "accounts:read"])
async def test_swissai_management_requires_specific_permission(pool, monkeypatch, removed):
    from unittest.mock import AsyncMock

    from app.core.auth import dependencies
    from app.core.auth.dashboard_access import (
        ADMIN_GRANTS,
        DashboardPrincipal,
        DashboardRole,
        Permission,
        legacy_permissions,
    )
    from app.core.auth.dashboard_mode import DashboardAuthMode

    grants = dict(ADMIN_GRANTS)
    grants.pop(Permission(removed))
    if removed == "accounts:read":
        grants.pop(Permission.ACCOUNTS_EXPORT)
    principal = DashboardPrincipal(
        role=DashboardRole.ADMIN,
        permissions=legacy_permissions(grants),
        auth_mode=DashboardAuthMode.STANDARD,
        grants=grants,
    )
    monkeypatch.setattr(dependencies, "validate_dashboard_session", AsyncMock(return_value=principal))
    client, _, _, _ = pool
    if removed == "accounts:write":
        response = await client.post(
            "/api/swissai-keys", json={"name": "denied", "apiKey": "sk-rc-test-no-write-00000"}
        )
    else:
        response = await client.get("/api/swissai-keys")
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "permission_required"
    assert response.json()["error"]["param"] == removed
