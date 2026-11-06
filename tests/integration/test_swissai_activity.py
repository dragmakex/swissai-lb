from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from sqlalchemy import delete, select

from app.core.config.settings import get_settings
from app.core.utils.time import utcnow
from app.db.models import ModelSource, RequestDemandQuarterRollup, RequestLog, SwissAIAttempt, SwissAILease
from app.db.session import get_background_session
from app.modules.accounts.usage_time_rollup import run_hourly_fold_pass, to_dimension
from app.modules.reports.cache import ReportsCaches
from app.modules.reports.rollup import run_report_fold_pass
from app.modules.swissai import repository as repo
from tests.integration.test_swissai_pool import pool as pool


async def test_key_activity_preserves_unknown_zero_and_calendar_bounds(pool):
    client, keys, _, state = pool
    settings = await client.put("/api/swissai/settings", json={"strategy": "single_key", "single_key_id": keys[0]})
    assert settings.status_code == 200
    state["mode"] = "json_trickle"
    assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200
    rows = {row["id"]: row for row in (await client.get("/api/swissai-keys")).json()}
    usage = rows[keys[0]]["usage"]
    assert usage["attempts"] == 1 and usage["reportedRequests"] == 0
    assert usage["inputTokens"] is usage["outputTokens"] is None
    assert usage["dailyRequests"] == [0, 0, 0, 0, 0, 0, 1]
    assert rows[keys[1]]["usage"]["attempts"] == 0
    assert rows[keys[1]]["usage"]["inputTokens"] is None

    state["mode"] = "json"
    state["input_tokens"] = state["output_tokens"] = 0
    assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200
    rows = {row["id"]: row for row in (await client.get("/api/swissai-keys")).json()}
    usage = rows[keys[0]]["usage"]
    assert usage["attempts"] == 2 and usage["reportedRequests"] == 1
    assert usage["inputTokens"] == usage["outputTokens"] == 0

    async with get_background_session() as session:
        session.add(
            SwissAIAttempt(
                id="outside-window",
                request_id="outside-window",
                source_id=keys[0],
                key_label="old",
                attempt_index=1,
                started_at=utcnow() - timedelta(days=8),
            )
        )
        await session.commit()
    rows = {row["id"]: row for row in (await client.get("/api/swissai-keys")).json()}
    assert rows[keys[0]]["usage"]["attempts"] == 2
    assert sum(rows[keys[0]]["usage"]["dailyRequests"]) == 2


async def test_failover_activity_does_not_duplicate_terminal_usage(pool):
    client, _, _, state = pool
    state["statuses"] = [429, 200]
    assert (await client.post("/v1/embeddings", json={"model": "Apertus-test"})).status_code == 200
    rows = (await client.get("/api/swissai-keys")).json()
    cooled = next(row for row in rows if row["status"] == "cooling_down")
    final = next(row for row in rows if row["usage"]["reportedRequests"] == 1)
    assert cooled["usage"]["attempts"] == final["usage"]["attempts"] == 1
    assert cooled["usage"]["inputTokens"] is cooled["usage"]["outputTokens"] is None
    assert final["usage"]["inputTokens"] == 2 and final["usage"]["outputTokens"] == 3
    assert sum(row["usage"]["attempts"] for row in rows) == 2
    assert sum(row["usage"]["reportedRequests"] for row in rows) == 1


async def test_metrics_uses_lightweight_key_snapshots_and_excludes_missing_credentials(pool, monkeypatch):
    client, keys, _, _ = pool
    async with get_background_session() as session:
        source = await session.get(ModelSource, keys[0])
        assert source is not None
        source.api_key_encrypted = None
        await session.commit()
    metadata = (await client.get("/api/swissai-keys")).json()
    invalid = next(row for row in metadata if row["id"] == keys[0])
    assert invalid["status"] == "invalid" and invalid["failureReason"] == "credential_unavailable"
    monkeypatch.setattr(repo, "key_usage", AsyncMock(side_effect=AssertionError("Metrics must not scan usage history")))
    monkeypatch.setenv("SWISSAI_LB_METRICS_ENABLED", "true")
    get_settings.cache_clear()
    response = await client.get("/metrics")
    assert response.status_code == 200, response.text
    assert "swissai_lb_eligible_keys 2.0" in response.text
    assert "sk-rc-" not in response.text and 'name="key 0"' not in response.text
    async with get_background_session() as session:
        session.add(SwissAILease(id="metrics-busy", source_id=keys[1], expires_at=utcnow() + timedelta(seconds=90)))
        await session.commit()
    assert "swissai_lb_eligible_keys 1.0" in (await client.get("/metrics")).text
    configured = await client.put("/api/swissai/settings", json={"strategy": "single_key", "single_key_id": keys[1]})
    assert configured.status_code == 200
    assert "swissai_lb_eligible_keys 0.0" in (await client.get("/metrics")).text


async def test_report_key_filters_and_attribution_survive_folding_and_raw_retention(pool, app_instance):
    client, keys, _, _ = pool
    for index, model in enumerate(("model-a", "model-b")):
        configured = await client.put(
            "/api/swissai/settings", json={"strategy": "single_key", "single_key_id": keys[index]}
        )
        assert configured.status_code == 200
        generated = await client.post("/v1/embeddings", json={"model": model})
        assert generated.status_code == 200, generated.text
    historical = (utcnow() - timedelta(days=35)).replace(hour=12, minute=0, second=0, microsecond=0)
    async with get_background_session() as session:
        for row in await session.scalars(select(RequestLog)):
            row.requested_at = historical
        await session.commit()
    day = historical.date().isoformat()
    report_params = {"start_date": day, "end_date": day, "timezone": "UTC", "account_id": keys[0]}
    log_params = {
        "since": historical.replace(hour=0).isoformat() + "Z",
        "until": (historical.replace(hour=0) + timedelta(days=1)).isoformat() + "Z",
        "accountId": keys[0],
    }
    before = await client.get("/api/reports", params=report_params)
    assert before.status_code == 200, before.text
    assert before.json()["summary"]["totalRequests"] == 1
    assert before.json()["summary"]["activeAccounts"] == 1
    assert before.json()["byAccount"][0]["accountId"] == keys[0]
    assert before.json()["byAccount"][0]["alias"] == "key 0"
    options = await client.get("/api/reports/options", params=report_params)
    assert options.status_code == 200 and options.json()["models"] == ["model-a"], options.text
    assert (await client.get("/api/request-logs", params=log_params)).json()["total"] == 1

    await run_hourly_fold_pass(now=utcnow())
    await run_report_fold_pass(now=utcnow())
    async with get_background_session() as session:
        dimensions = set(await session.scalars(select(RequestDemandQuarterRollup.account_id)))
        assert {to_dimension(keys[0]), to_dimension(keys[1])} <= dimensions
    assert (await client.get("/api/request-logs", params=log_params)).json()["total"] == 1

    async with get_background_session() as session:
        await session.execute(delete(RequestLog))
        await session.commit()
    # Discard response caches so folded reads, not an earlier raw answer, prove parity.
    app_instance.state.reports_caches = ReportsCaches()
    after = await client.get("/api/reports", params=report_params)
    assert after.status_code == 200, after.text
    assert after.json()["summary"]["totalRequests"] == 1
    assert after.json()["summary"]["activeAccounts"] == 1
    assert after.json()["byAccount"][0]["accountId"] == keys[0]
    assert after.json()["byAccount"][0]["alias"] == "key 0"
    options = await client.get("/api/reports/options", params=report_params)
    assert options.status_code == 200 and options.json()["models"] == ["model-a"], options.text
