from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.models import SwissAIAttempt
from app.db.session import get_background_session
from app.modules.swissai import repository as repo
from tests.integration.test_swissai_pool import pool as pool


async def test_add_accepts_inference_keys_when_profile_requires_an_account_token(pool):
    client, keys, calls, _ = pool
    inventory = await client.get("/api/swissai-keys")
    assert len(inventory.json()) == len(keys)
    assert all(key["status"] == "active" for key in inventory.json())
    assert calls == []  # No real model/input was selected and no generation was recorded.


async def test_reprobe_recovers_an_invalid_key_without_replacing_its_secret(pool):
    client, _, calls, state = pool
    state["statuses"] = [401, 200]
    response = await client.post("/v1/responses", json={"model": "Apertus-test", "input": "test"})
    assert response.status_code == 200
    (before,) = [key for key in await repo.list_keys() if key.status == "invalid"]
    secret_before = before.source.api_key_encrypted
    generation_before = before.state.generation
    fingerprint_before = before.state.fingerprint
    result = await client.post(f"/api/swissai-keys/{before.source.id}/probe")
    assert result.status_code == 200
    assert result.json()["ok"] is True and result.json()["status"] == 404
    (after,) = [key for key in await repo.list_keys() if key.source.id == before.source.id]
    assert after.status == "active"
    assert after.source.api_key_encrypted == secret_before
    assert after.state.generation == generation_before
    assert after.state.fingerprint == fingerprint_before
    assert len(calls) == 2
    async with get_background_session() as session:
        assert await session.scalar(select(func.count()).select_from(SwissAIAttempt)) == 2


async def test_inference_401_still_invalidates_a_key(pool):
    client, keys, _, state = pool
    state["probe_status"] = 401
    response = await client.post(f"/api/swissai-keys/{keys[0]}/probe")
    assert response.status_code == 200 and response.json()["ok"] is False
    assert response.json()["status"] == 401
    assert next(key for key in await repo.list_keys() if key.source.id == keys[0]).status == "invalid"


async def test_oversized_probe_reply_is_inconclusive(pool):
    client, keys, _, state = pool
    before = next(key for key in await repo.list_keys() if key.source.id == keys[0])
    state["probe_message"] = "x" * 100_000
    response = await client.post(f"/api/swissai-keys/{keys[0]}/probe")
    assert response.status_code == 200 and response.json()["ok"] is False
    assert response.json()["status"] is None
    after = next(key for key in await repo.list_keys() if key.source.id == keys[0])
    assert after.status == before.status and after.state.failures == before.state.failures


@pytest.mark.parametrize("status", [200, 400, 403, 404, 429, 500])
@pytest.mark.parametrize("invalid", [False, True])
async def test_inconclusive_probe_preserves_existing_health(pool, status, invalid):
    client, keys, _, state = pool
    if invalid:
        state["probe_status"] = 401
        await client.post(f"/api/swissai-keys/{keys[0]}/probe")
    before = next(key for key in await repo.list_keys() if key.source.id == keys[0])
    state["probe_status"] = status
    state["probe_message"] = "Unrecognized provider response"
    response = await client.post(f"/api/swissai-keys/{keys[0]}/probe")
    assert response.status_code == 200 and response.json()["ok"] is False
    after = next(key for key in await repo.list_keys() if key.source.id == keys[0])
    assert after.status == before.status
    assert after.state.invalid_at == before.state.invalid_at
    assert after.state.failure_reason == before.state.failure_reason
    assert after.state.failures == before.state.failures
    assert after.state.cooldown_until == before.state.cooldown_until
