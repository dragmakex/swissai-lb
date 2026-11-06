from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import delete, func, select

from app.core.utils.time import utcnow
from app.db.models import AuditLog, RequestLog, SwissAIAttempt, SwissAIContinuation, SwissAILease
from app.db.session import get_background_session
from app.modules.swissai import repository as repo
from tests.integration.test_swissai_pool import lease_count
from tests.integration.test_swissai_pool import pool as pool
from tests.simulation.virtual_time import VirtualClock, VirtualScheduler


async def test_lease_renewal_loss_cancels_without_rotating(pool, app_instance, monkeypatch):
    client, _, calls, state = pool
    state["delay"] = 0.5
    clock = VirtualClock()
    scheduler = VirtualScheduler(clock)
    app_instance.state.swissai._clock = clock
    app_instance.state.swissai._scheduler = scheduler
    monkeypatch.setattr(repo, "renew_lease", AsyncMock(return_value=False))
    task = asyncio.create_task(client.post("/v1/embeddings", json={"model": "Apertus-test"}))
    try:
        for _ in range(200):
            if calls:
                break
            await asyncio.sleep(0.001)
        assert len(calls) == 1
        await scheduler.advance(20)
        response = await asyncio.wait_for(task, 3)
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "capacity_lease_lost"
        assert len(calls) == 1
        assert await lease_count() == 0
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await scheduler.cancel_owned_tasks()


async def test_cancellation_during_final_settlement_is_deferred_and_rethrown(pool, monkeypatch):
    from app.modules.swissai.proxy import SwissAIResponse

    client, _, _, _ = pool
    started, finish = asyncio.Event(), asyncio.Event()
    original = SwissAIResponse._settle_and_log

    async def delayed(response):
        started.set()
        await finish.wait()
        await original(response)

    monkeypatch.setattr(SwissAIResponse, "_settle_and_log", delayed)
    task = asyncio.create_task(client.post("/v1/embeddings", json={"model": "Apertus-test"}))
    try:
        await asyncio.wait_for(started.wait(), 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert await lease_count() == 0
        async with get_background_session() as session:
            assert await session.scalar(select(func.count()).select_from(RequestLog)) == 0
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await lease_count() == 0
        async with get_background_session() as session:
            assert await session.scalar(select(func.count()).select_from(RequestLog)) == 1
    finally:
        finish.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_expired_crash_lease_is_reclaimed_by_next_admission(pool):
    client, keys, _, _ = pool
    async with get_background_session() as session:
        session.add(SwissAILease(id="crashed-owner", source_id=keys[0], expires_at=utcnow() - timedelta(seconds=1)))
        await session.commit()
    result = await client.post("/v1/embeddings", json={"model": "Apertus-test"})
    assert result.status_code == 200
    assert await lease_count() == 0


async def test_retention_is_disabled_or_prunes_in_bounded_batches(pool, app_instance):
    client, keys, _, _ = pool
    old = utcnow() - timedelta(days=31)
    async with get_background_session() as session:
        session.add_all(
            [
                SwissAIAttempt(
                    id=f"old-{index}",
                    request_id=f"old-{index}",
                    source_id=keys[0],
                    key_label="old",
                    attempt_index=1,
                    started_at=old,
                )
                for index in range(1005)
            ]
        )
        session.add(SwissAIContinuation(id="old-owner", source_id=keys[0], generation=0, created_at=old))
        audit = AuditLog(action="old-test-audit", timestamp=old)
        session.add(audit)
        await session.commit()
        audit_id = audit.id
    runtime = app_instance.state.swissai
    await runtime.prune_metadata()
    async with get_background_session() as session:
        assert await session.get(SwissAIAttempt, "old-0") is not None
    updated = await client.put("/api/settings", json={"requestLogRetentionOverrideDays": 30})
    assert updated.status_code == 200, updated.text
    await runtime.prune_metadata()
    async with get_background_session() as session:
        assert await session.scalar(select(func.count()).select_from(SwissAIAttempt)) == 0
        assert await session.get(SwissAIContinuation, "old-owner") is None
        assert await session.get(AuditLog, audit_id) is None
    assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200
    await runtime.prune_metadata()
    async with get_background_session() as session:
        assert await session.scalar(select(func.count()).select_from(RequestLog)) == 1
        assert await session.scalar(select(func.count()).select_from(SwissAIAttempt)) == 1


async def test_retention_preserves_attempts_while_logical_history_remains(pool, app_instance):
    client, keys, _, _ = pool
    old = utcnow() - timedelta(days=31)
    async with get_background_session() as session:
        session.add(
            RequestLog(
                request_id="retained-history",
                model="Apertus-test",
                status="success",
                requested_at=old,
                model_source_id=keys[0],
                model_source_kind="swissai",
            )
        )
        session.add(
            SwissAIAttempt(
                id="retained-attempt",
                request_id="retained-history",
                source_id=keys[0],
                key_label="Historical research label",
                attempt_index=1,
                started_at=old,
            )
        )
        await session.commit()
    assert (await client.put("/api/settings", json={"requestLogRetentionOverrideDays": 30})).status_code == 200
    await app_instance.state.swissai.prune_metadata()
    async with get_background_session() as session:
        parent = await session.scalar(select(RequestLog).where(RequestLog.request_id == "retained-history"))
        assert parent is not None
        assert parent.deleted_at is None and parent.request_kind == "normal"
        assert await session.get(SwissAIAttempt, "retained-attempt") is not None
    history = await client.get(
        "/api/request-logs",
        params={
            "search": "retained-history",
            "since": (old - timedelta(days=1)).isoformat() + "Z",
            "until": (old + timedelta(days=1)).isoformat() + "Z",
        },
    )
    assert history.status_code == 200, history.text
    assert len(history.json()["requests"]) == 1, history.text
    (row,) = history.json()["requests"]
    assert row["attemptCount"] == 1 and row["upstreamKeyLabel"] == "Historical research label"
    async with get_background_session() as session:
        await session.execute(delete(RequestLog).where(RequestLog.request_id == "retained-history"))
        await session.commit()
    await app_instance.state.swissai.prune_metadata()
    async with get_background_session() as session:
        assert await session.get(SwissAIAttempt, "retained-attempt") is None


async def test_partial_startup_failure_stops_previously_acquired_resources(app_instance, monkeypatch):
    import app.main as main
    import app.modules.api_keys.last_used_coalescer as last_used
    import app.modules.swissai.runtime as runtime

    stopped = []

    class Scheduler:
        def __init__(self, name, fail=False):
            self.name, self.fail = name, fail

        async def start(self):
            if self.fail:
                raise RuntimeError("injected scheduler startup failure")

        async def stop(self):
            stopped.append(self.name)

    monkeypatch.setattr(main, "build_data_retention_scheduler", lambda: Scheduler("retention"))
    monkeypatch.setattr(last_used, "build_api_key_last_used_flush_scheduler", lambda: Scheduler("last-used", fail=True))
    close_http = AsyncMock(wraps=runtime.close_http_client)
    close_db = AsyncMock(wraps=runtime.close_db)
    monkeypatch.setattr(runtime, "close_http_client", close_http)
    monkeypatch.setattr(runtime, "close_db", close_db)
    with pytest.raises(RuntimeError, match="injected scheduler"):
        async with app_instance.router.lifespan_context(app_instance):
            pytest.fail("Startup must not report ready after an acquisition failure")
    assert stopped == ["last-used", "retention"]
    close_http.assert_awaited_once()
    close_db.assert_awaited_once()


async def test_shutdown_drains_control_plane_before_closing_io(app_instance, monkeypatch):
    import app.main as main
    from app.modules.swissai import runtime
    from app.modules.telemetry import api as telemetry_api

    entered, finish = asyncio.Event(), asyncio.Event()
    order = []
    original_drain = main._drain_detached_control_plane_tasks
    original_close = runtime.close_http_client

    async def drain(timeout):
        entered.set()
        return await original_drain(timeout)

    async def close():
        order.append("http-closed")
        await original_close()

    async def pending_notice():
        await finish.wait()
        order.append("notice-finished")

    monkeypatch.setattr(main, "_drain_detached_control_plane_tasks", drain)
    monkeypatch.setattr(runtime, "close_http_client", close)
    monkeypatch.setattr(runtime.Catalog, "run", AsyncMock())
    manager = app_instance.router.lifespan_context(app_instance)
    await manager.__aenter__()
    notice = asyncio.create_task(pending_notice())
    telemetry_api._OPT_OUT_TASKS.add(notice)
    notice.add_done_callback(telemetry_api._OPT_OUT_TASKS.discard)
    exiting = asyncio.create_task(manager.__aexit__(None, None, None))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        assert not exiting.done() and "http-closed" not in order
        finish.set()
        await asyncio.wait_for(exiting, 3)
        assert order == ["notice-finished", "http-closed"]
        assert not telemetry_api._OPT_OUT_TASKS
    finally:
        finish.set()
        await asyncio.gather(notice, exiting, return_exceptions=True)


async def test_rollup_scheduler_is_owned_and_handler_tests_do_not_poll_public_catalog(app_instance, monkeypatch):
    import app.main as main
    from app.modules.swissai import runtime

    scheduler = Mock(start=AsyncMock(), stop=AsyncMock())
    refresh = AsyncMock(side_effect=AssertionError("Handler tests must not poll a public provider"))
    monkeypatch.setattr(main, "build_account_usage_rollup_scheduler", lambda: scheduler)
    monkeypatch.setattr(runtime.Catalog, "refresh", refresh)
    async with app_instance.router.lifespan_context(app_instance):
        await asyncio.sleep(0)
        scheduler.start.assert_awaited_once_with()
        scheduler.stop.assert_not_awaited()
        refresh.assert_not_awaited()
    scheduler.stop.assert_awaited_once_with()


async def test_repeated_request_batches_leave_no_capacity_or_request_tasks(pool):
    client, _, calls, state = pool
    state["delay"] = 0.005
    for _ in range(10):
        results = await asyncio.gather(
            *(client.post("/v1/embeddings", json={"model": "Apertus-test", "input": "load fixture"}) for _ in range(10))
        )
        assert all(response.status_code == 200 for response in results)
        assert await lease_count() == 0
    assert len(calls) == 100
    async with get_background_session() as session:
        assert await session.scalar(select(func.count()).select_from(RequestLog)) == 100
        assert await session.scalar(select(func.count()).select_from(SwissAIAttempt)) == 100


async def test_request_log_total_respects_rows_when_count_cache_is_warm(pool, monkeypatch):
    from app.modules.request_logs import repository as logs_repository

    client, _, _, _ = pool
    monkeypatch.setattr(logs_repository, "_COUNT_CACHE_TTL_SECONDS", 60)
    logs_repository._clear_recent_count_cache()
    try:
        assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200
        assert (await client.get("/api/request-logs")).json()["total"] == 1
        assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200
        page = (await client.get("/api/request-logs")).json()
        assert len(page["requests"]) == page["total"] == 2
    finally:
        logs_repository._clear_recent_count_cache()


async def test_request_log_route_stream_key_filter_and_deleted_key_label(pool):
    client, keys, _, state = pool
    for index, route in enumerate(("/v1/embeddings", "/v1/responses")):
        settings = await client.put(
            "/api/swissai/settings", json={"strategy": "single_key", "single_key_id": keys[index]}
        )
        assert settings.status_code == 200, settings.text
        stream = index == 1
        state["mode"] = "sse" if stream else "json"
        response = await client.post(route, json={"model": "Apertus-test", "stream": stream})
        assert response.status_code == 200, response.text
    assert (await client.delete(f"/api/swissai-keys/{keys[0]}")).status_code == 204
    page = await client.get("/api/request-logs", params={"accountId": keys[0]})
    assert page.status_code == 200, page.text
    (row,) = page.json()["requests"]
    assert row["route"] == "/v1/embeddings" and row["stream"] is False
    assert row["upstreamKeyLabel"] == "key 0"
    searched = await client.get("/api/request-logs", params={"search": "/v1/responses"})
    (streamed,) = searched.json()["requests"]
    assert streamed["stream"] is True and streamed["modelSourceId"] == keys[1]
    assert searched.json()["total"] == 1
    options = (await client.get("/api/request-logs/options")).json()
    assert set(options["accountIds"]) == {keys[0], keys[1]}
    scoped = await client.get("/api/request-logs/options", params={"accountId": keys[0], "timeframe": "7d"})
    assert scoped.json()["accountIds"] == [keys[0]]
