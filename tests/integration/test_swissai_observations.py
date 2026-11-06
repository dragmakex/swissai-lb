from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.db.models import RequestLog, SwissAIContinuation
from app.db.session import get_background_session
from app.modules.swissai import metrics
from app.modules.swissai import repository as repo
from tests.integration.test_swissai_pool import lease_count
from tests.integration.test_swissai_pool import pool as pool
from tests.simulation.virtual_time import VirtualClock, VirtualScheduler


@pytest.mark.parametrize(
    "payload",
    [
        {"model": " "},
        {"model": "x" * 513},
        {"model": "Apertus-test", "previous_response_id": 42},
        {"model": "Apertus-test", "previous_response_id": ""},
        {"model": "Apertus-test", "conversation": {}},
        {"model": "Apertus-test", "conversation": {"id": "x" * 513}},
    ],
)
async def test_unbounded_models_and_malformed_owner_references_never_dispatch(pool, payload):
    client, _, calls, _ = pool
    result = await client.post("/v1/responses", json=payload)
    assert result.status_code == 400, result.text
    assert calls == [] and await lease_count() == 0


async def test_preliminary_stream_usage_is_not_logged_as_terminal_usage(pool):
    client, _, _, state = pool
    state["mode"] = "sse_initial_usage"
    result = await client.post("/v1/responses", json={"model": "Apertus-test", "stream": True})
    assert result.status_code == 200 and b'"input_tokens":0' in result.content
    async with get_background_session() as session:
        row = (await session.scalars(select(RequestLog))).one()
        assert row.input_tokens is row.output_tokens is None
        assert row.latency_first_token_ms is None
    assert await lease_count() == 0


async def test_ttft_waits_for_model_output_not_creation_metadata(pool, app_instance, monkeypatch):
    client, _, _, state = pool
    state["mode"] = "sse_output"
    gate, metadata = asyncio.Event(), asyncio.Event()
    state["output_gate"] = gate
    clock = VirtualClock()
    scheduler = VirtualScheduler(clock)
    app_instance.state.swissai._clock = clock
    app_instance.state.swissai._scheduler = scheduler
    save_owners = repo.save_owners
    observed = Mock()

    async def record_owners(identifiers, selected):
        await save_owners(identifiers, selected)
        if identifiers:
            metadata.set()

    monkeypatch.setattr(repo, "save_owners", record_owners)
    monkeypatch.setattr(metrics, "first_output", observed)
    task = asyncio.create_task(client.post("/v1/responses", json={"model": "Apertus-test", "stream": True}))
    try:
        await asyncio.wait_for(metadata.wait(), 3)
        observed.assert_not_called()
        await scheduler.advance(0.5)
        gate.set()
        result = await asyncio.wait_for(task, 3)
        assert result.status_code == 200 and b'"delta":"Hello"' in result.content
        observed.assert_called_once_with("/responses", 0.5)
        async with get_background_session() as session:
            row = (await session.scalars(select(RequestLog))).one()
            assert row.latency_first_token_ms == 500
            assert row.input_tokens == 2 and row.output_tokens == 3
        assert await lease_count() == 0
    finally:
        gate.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await scheduler.cancel_owned_tasks()


async def test_failed_response_over_http_success_is_not_a_successful_generation(pool, monkeypatch):
    client, _, calls, state = pool
    state["mode"] = "sse_failed"
    observed = Mock()
    monkeypatch.setattr(metrics, "request", observed)
    result = await client.post("/v1/responses", json={"model": "Apertus-test", "stream": True})
    assert result.status_code == 200 and b'"type":"response.failed"' in result.content
    observed.assert_called_once()
    assert observed.call_args.args[:2] == ("/responses", "error")
    assert observed.call_args.args[2] >= 0
    assert len(calls) == 1
    async with get_background_session() as session:
        row = (await session.scalars(select(RequestLog))).one()
        assert row.status == "error" and row.error_code == "upstream_response_failed"
        assert row.input_tokens == 2 and row.output_tokens == 3
        assert row.upstream_status_code == 200
    assert all(row["status"] == "active" for row in (await client.get("/api/swissai-keys")).json())
    assert await lease_count() == 0


async def test_credential_like_owner_identifier_is_not_forwarded_or_persisted(pool):
    client, _, calls, state = pool
    secret = "sk-rc-test-never-store-owner-0000"
    state["response_id"] = secret
    result = await client.post("/v1/responses", json={"model": "Apertus-test"})
    assert result.status_code == 502, result.text
    assert secret not in result.text and len(calls) == 1
    async with get_background_session() as session:
        assert await session.get(SwissAIContinuation, secret) is None
        row = (await session.scalars(select(RequestLog))).one()
        assert row.error_code == "upstream_protocol_error"
    assert await lease_count() == 0
