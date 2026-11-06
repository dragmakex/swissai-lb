"""SwissAI routes; the existing dashboard's authentication, CSRF, permissions and audit apply."""

from __future__ import annotations

from datetime import datetime

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, SecretStr, field_validator
from sqlalchemy import select
from starlette.responses import JSONResponse

from app.core.audit.service import AuditActor, AuditService, AuditTarget
from app.core.auth.dashboard_access import DashboardPrincipal, Permission
from app.core.auth.dependencies import (
    require_dashboard_permission,
    set_dashboard_error_format,
    set_openai_error_format,
    validate_dashboard_session,
    validate_proxy_api_key,
)
from app.core.clients.http import lease_model_source_session
from app.core.config.settings import get_settings
from app.core.crypto import TokenEncryptor
from app.db.models import ModelSource, SwissAIAttempt, SwissAIKeyState
from app.db.session import get_background_session
from app.modules.api_keys.service import ApiKeyData
from app.modules.shared.schemas import DashboardModel
from app.modules.swissai import repository as repo
from app.modules.swissai.policy import KEY_PROBE_MODEL, PoolSettings, classify, error_payload, key_probe_authenticated
from app.modules.swissai.proxy import MAX_ERROR, Rejected, bounded_read, prepare

router = APIRouter(
    prefix="/api",
    tags=["SwissAI"],
    dependencies=[Depends(validate_dashboard_session), Depends(set_dashboard_error_format)],
)
proxy_router = APIRouter(tags=["SwissAI proxy"], dependencies=[Depends(set_openai_error_format)])
read = require_dashboard_permission(Permission.ACCOUNTS_READ)
write = require_dashboard_permission(Permission.ACCOUNTS_WRITE)


class KeyCreate(DashboardModel):
    name: str = Field(min_length=1, max_length=128)
    api_key: SecretStr
    max_concurrency: int | None = Field(None, ge=1, le=1000)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()


class KeyPatch(DashboardModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    api_key: SecretStr | None = None
    max_concurrency: int | None = Field(None, ge=1, le=1000)
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip() if value else value


class KeyUsageView(DashboardModel):
    window_start: datetime
    window_end: datetime
    attempts: int
    reported_requests: int
    input_tokens: int | None
    output_tokens: int | None
    daily_requests: list[int] = Field(min_length=7, max_length=7)


class KeyProbeResult(DashboardModel):
    ok: bool
    status: int | None
    reason: str


class KeyView(DashboardModel):
    id: str
    name: str
    key_prefix: str
    status: str
    enabled: bool
    cooldown_until: datetime | None
    failure_reason: str | None
    max_concurrency: int | None
    in_flight: int
    last_success_at: datetime | None
    last_failure_at: datetime | None
    created_at: datetime
    usage: KeyUsageView


def audit(action: str, key_id: str, principal: DashboardPrincipal, request: Request):
    AuditService.log_async(
        action,
        actor=AuditActor.from_principal(principal),
        actor_ip=request.client.host if request.client else None,
        target=AuditTarget("swissai_key", key_id),
        details={"key_id": key_id},
    )


async def _key_views(keys: list[repo.KeySnapshot]) -> list[KeyView]:
    usage = await repo.key_usage([key.source.id for key in keys])
    return [
        KeyView(
            id=key.source.id,
            name=key.source.name,
            key_prefix=key.state.key_prefix,
            status=key.status,
            enabled=key.source.is_enabled,
            cooldown_until=key.state.cooldown_until,
            failure_reason=key.state.failure_reason
            if key.source.api_key_encrypted is not None
            else "credential_unavailable",
            max_concurrency=key.source.max_concurrency,
            in_flight=key.in_flight,
            last_success_at=key.state.last_success_at,
            last_failure_at=key.state.last_failure_at,
            created_at=key.source.created_at,
            usage=KeyUsageView.model_validate(usage[key.source.id], from_attributes=True),
        )
        for key in keys
    ]


async def view(key_id: str) -> KeyView:
    for key in await repo.list_keys():
        if key.source.id == key_id:
            return (await _key_views([key]))[0]
    raise HTTPException(404, "SwissAI key not found")


@router.get("/accounts", dependencies=[Depends(read)])
async def subscription_accounts():
    # Compatibility read for retained client-key forms; OAuth mutations are absent.
    return {"accounts": []}


@router.get("/swissai-keys", response_model=list[KeyView], dependencies=[Depends(read)])
async def keys():
    return await _key_views(await repo.list_keys())


@router.post("/swissai-keys", status_code=201, response_model=KeyView)
async def add_key(payload: KeyCreate, request: Request, principal=Depends(write)):
    try:
        key_id = await repo.create_key(payload.name, payload.api_key.get_secret_value(), payload.max_concurrency)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit("swissai_key_created", key_id, principal, request)
    await probe(key_id)
    return await view(key_id)


@router.patch("/swissai-keys/{key_id}", response_model=KeyView)
async def update_key(key_id: str, payload: KeyPatch, request: Request, principal=Depends(write)):
    changes = payload.model_dump(by_alias=True, exclude_unset=True)
    if payload.api_key is not None:
        changes["apiKey"] = payload.api_key.get_secret_value()
    for field in ("name", "enabled", "apiKey"):
        if field in changes and changes[field] is None:
            raise HTTPException(400, f"{field} cannot be null")
    try:
        await repo.patch_key(key_id, changes)
    except repo.KeyNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit("swissai_key_updated", key_id, principal, request)
    if payload.api_key is not None:
        await probe(key_id)
    return await view(key_id)


@router.post("/swissai-keys/{key_id}/pause", response_model=KeyView)
async def pause(key_id: str, request: Request, principal=Depends(write)):
    try:
        await repo.patch_key(key_id, {"enabled": False})
    except repo.KeyNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    audit("swissai_key_paused", key_id, principal, request)
    return await view(key_id)


@router.post("/swissai-keys/{key_id}/resume", response_model=KeyView)
async def resume(key_id: str, request: Request, principal=Depends(write)):
    try:
        await repo.patch_key(key_id, {"enabled": True})
    except repo.KeyNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    audit("swissai_key_resumed", key_id, principal, request)
    return await view(key_id)


@router.post("/swissai-keys/{key_id}/probe")
async def probe_key(key_id: str, request: Request, principal=Depends(write)):
    result = await probe(key_id)
    audit("swissai_key_probed", key_id, principal, request)
    return result


async def probe(key_id: str) -> KeyProbeResult:
    async with get_background_session() as session:
        source = await session.get(ModelSource, key_id)
        state = await session.get(SwissAIKeyState, key_id)
        if source is None or state is None:
            raise HTTPException(404, "SwissAI key not found")
        if source.api_key_encrypted is None:
            raise HTTPException(503, "SwissAI key has no stored credential")
        selected = repo.SelectedKey(
            source.id, source.name, source.api_key_encrypted, state.generation, state.failures, ""
        )
    try:
        async with lease_model_source_session() as session:
            # An unnamespaced sentinel cannot select a SwissAI model; no generation input is sent.
            async with session.post(
                get_settings().upstream_base_url.rstrip("/") + "/chat/completions",
                json={"model": KEY_PROBE_MODEL, "messages": []},
                headers={"Authorization": "Bearer " + TokenEncryptor().decrypt(selected.encrypted)},
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False,
            ) as response:
                body = await bounded_read(response, MAX_ERROR)
                status = response.status
                if key_probe_authenticated(status, body):
                    await repo.health(selected, None, probe=True)
                    return KeyProbeResult(
                        ok=True, status=status, reason="Authentication accepted; no generation performed"
                    )
                if status == 401:
                    await repo.health(selected, classify(status, None), probe=True)
                    return KeyProbeResult(ok=False, status=status, reason="SwissAI rejected the inference credential")
                return KeyProbeResult(ok=False, status=status, reason="Probe inconclusive; key health unchanged")
    except Rejected:
        return KeyProbeResult(ok=False, status=None, reason="Probe response exceeded its limit; key health unchanged")
    except (aiohttp.ClientError, TimeoutError):
        return KeyProbeResult(ok=False, status=None, reason="SwissAI could not be reached; key health unchanged")


@router.delete("/swissai-keys/{key_id}", status_code=204)
async def remove(key_id: str, request: Request, principal=Depends(write)):
    try:
        if not await repo.delete_key(key_id):
            raise HTTPException(409, "Key is paused and draining; retry deletion after active requests finish")
    except repo.KeyNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    audit("swissai_key_deleted", key_id, principal, request)
    return Response(status_code=204)


@router.get("/swissai/settings", dependencies=[Depends(read)])
async def settings():
    return await repo.pool_settings()


@router.put("/swissai/settings")
async def change_settings(payload: PoolSettings, request: Request, principal=Depends(write)):
    saved = await repo.save_pool_settings(payload)
    audit("swissai_routing_updated", "settings", principal, request)
    return saved


@router.get("/swissai/catalog", dependencies=[Depends(read)])
async def catalog_status(request: Request):
    catalog = request.app.state.swissai.catalog
    return {"models": catalog.available(), "ageSeconds": catalog.age, "lastError": catalog.error}


@router.get("/swissai/attempts/{request_id}", dependencies=[Depends(read)])
async def attempts(request_id: str):
    async with get_background_session() as session:
        rows = await session.scalars(
            select(SwissAIAttempt).where(SwissAIAttempt.request_id == request_id).order_by(SwissAIAttempt.attempt_index)
        )
        return [
            {
                "keyId": row.source_id,
                "keyLabel": row.key_label,
                "index": row.attempt_index,
                "status": row.status_code,
                "reason": row.failure_reason,
                "downstreamVisible": row.downstream_visible,
                "startedAt": row.started_at,
                "finishedAt": row.finished_at,
            }
            for row in rows
        ]


@proxy_router.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    from app.modules.swissai.metrics import scrape

    return Response(
        await scrape(request.app.state.swissai.catalog.age), media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@proxy_router.get("/v1/models")
@proxy_router.get("/v1/models/")
async def models(request: Request, client_key=Depends(validate_proxy_api_key)):
    catalog = request.app.state.swissai.catalog
    if catalog.fetched_at is None:
        await catalog.refresh()
    allowed = client_key.allowed_models if client_key else None
    records = catalog.available(allowed)
    if not records and not catalog.available():
        return JSONResponse(
            error_payload("model_catalog_unavailable", "SwissAI catalog is unavailable"), status_code=503
        )
    return {"object": "list", "data": records}


@proxy_router.get("/backend-api/codex/models")
async def codex_models(request: Request, client_key=Depends(validate_proxy_api_key)):
    result = await models(request, client_key)
    if isinstance(result, Response):
        return result
    return {
        "models": [{"slug": m["id"], "display_name": m.get("name", m["id"]), "id": m["id"]} for m in result["data"]]
    }


async def generate(request: Request, client_key: ApiKeyData | None = Depends(validate_proxy_api_key)):
    path = request.url.path.rstrip("/")
    return await prepare(
        request, client_key, "/responses" if path.startswith("/backend-api/") else path.removeprefix("/v1")
    )


for path in (
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/responses",
    "/v1/embeddings",
    "/backend-api/codex/responses",
):
    proxy_router.add_api_route(path, generate, methods=["POST"])
    proxy_router.add_api_route(path + "/", generate, methods=["POST"], include_in_schema=False)


@proxy_router.api_route("/v1", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
@proxy_router.api_route("/backend-api", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
@proxy_router.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
@proxy_router.api_route(
    "/backend-api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False
)
async def unsupported(path: str = ""):
    if not path:
        raise HTTPException(404, "Not Found")
    return JSONResponse(
        error_payload("unsupported_upstream_capability", "SwissAI does not expose this capability through this proxy"),
        status_code=501,
    )
