"""SwissAI persistence on the upstream SQLAlchemy session/migration lifecycle."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError

from app.core.config.settings import get_settings
from app.core.crypto import TokenEncryptor, get_or_create_key
from app.core.utils.time import utcnow
from app.db.models import (
    ModelSource,
    RequestLog,
    SwissAIAttempt,
    SwissAIContinuation,
    SwissAIKeyState,
    SwissAILease,
    SwissAIRuntime,
)
from app.db.session import get_background_session, sqlite_writer_section
from app.modules.swissai.policy import Failure, PoolSettings


@dataclass(frozen=True)
class SelectedKey:
    id: str
    name: str
    encrypted: bytes
    generation: int
    failures: int
    lease_id: str


@dataclass(frozen=True)
class KeySnapshot:
    source: ModelSource
    state: SwissAIKeyState
    in_flight: int
    observed_at: datetime

    @property
    def status(self) -> str:
        if not self.source.is_enabled:
            return "paused"
        if self.state.invalid_at or self.source.api_key_encrypted is None:
            return "invalid"
        if self.state.cooldown_until and self.state.cooldown_until > self.observed_at:
            return "cooling_down"
        return "active"


@dataclass
class KeyUsage:
    window_start: datetime
    window_end: datetime
    attempts: int = 0
    reported_requests: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    daily_requests: list[int] = field(default_factory=lambda: [0] * 7)


class KeyNotFound(ValueError):
    pass


class KeyConflict(ValueError):
    pass


def fingerprint(secret: str) -> str:
    return hmac.new(get_or_create_key(), b"swissai-key-fingerprint\0" + secret.encode(), hashlib.sha256).hexdigest()


def validate_secret(value: str) -> None:
    if not value.startswith("sk-rc-") or not 12 <= len(value) <= 512 or any(c.isspace() for c in value):
        raise ValueError("SwissAI keys must have the form sk-rc-... and contain no whitespace")


async def pool_settings() -> PoolSettings:
    async with get_background_session() as session:
        row = await session.get(SwissAIRuntime, "settings")
        return PoolSettings.model_validate_json(row.value) if row else PoolSettings()


async def save_pool_settings(value: PoolSettings) -> PoolSettings:
    async with sqlite_writer_section(), get_background_session() as session:
        row = await session.get(SwissAIRuntime, "settings")
        if row:
            row.value = value.model_dump_json()
        else:
            session.add(SwissAIRuntime(id="settings", value=value.model_dump_json()))
        await session.commit()
    return value


async def list_keys() -> list[KeySnapshot]:
    async with get_background_session() as session:
        rows = (
            await session.execute(
                select(ModelSource, SwissAIKeyState)
                .join(SwissAIKeyState, ModelSource.id == SwissAIKeyState.source_id)
                .order_by(ModelSource.created_at, ModelSource.id)
            )
        ).all()
        counts = {
            key_id: count
            for key_id, count in await session.execute(
                select(SwissAILease.source_id, func.count())
                .where(SwissAILease.expires_at > utcnow())
                .group_by(SwissAILease.source_id)
            )
        }
        now = utcnow()
        # Background-session rollback must not expire the already-loaded read-only snapshot.
        session.expunge_all()
        return [KeySnapshot(source, state, counts.get(source.id, 0), now) for source, state in rows]


async def key_usage(source_ids: list[str]) -> dict[str, KeyUsage]:
    now = utcnow()
    start = datetime.combine(now.date() - timedelta(days=6), time.min)
    usage = {source_id: KeyUsage(start, now) for source_id in source_ids}
    if not source_ids:
        return usage
    # shortcut: aggregate seven raw UTC days; use source-aware rollups if this window becomes expensive.
    async with get_background_session() as session:
        rows = await session.execute(
            select(
                SwissAIAttempt.source_id,
                func.date(SwissAIAttempt.started_at),
                func.count(),
                func.sum(RequestLog.input_tokens),
                func.sum(RequestLog.output_tokens),
                func.sum(
                    case((or_(RequestLog.input_tokens.is_not(None), RequestLog.output_tokens.is_not(None)), 1), else_=0)
                ),
            )
            .outerjoin(
                RequestLog,
                and_(
                    RequestLog.request_id == SwissAIAttempt.request_id,
                    RequestLog.model_source_id == SwissAIAttempt.source_id,
                ),
            )
            .where(
                SwissAIAttempt.source_id.in_(source_ids),
                SwissAIAttempt.started_at >= start,
                SwissAIAttempt.started_at <= now,
            )
            .group_by(SwissAIAttempt.source_id, func.date(SwissAIAttempt.started_at))
        )
        for source_id, day, attempts, inputs, outputs, reported in rows:
            entry = usage[source_id]
            entry.attempts += attempts
            entry.reported_requests += reported
            entry.daily_requests[(date.fromisoformat(str(day)) - start.date()).days] = attempts
            if inputs is not None:
                entry.input_tokens = (entry.input_tokens or 0) + inputs
            if outputs is not None:
                entry.output_tokens = (entry.output_tokens or 0) + outputs
    return usage


async def create_key(name: str, secret: str, cap: int | None) -> str:
    validate_secret(secret)
    key_id = "sak_" + secrets.token_hex(12)
    async with sqlite_writer_section(), get_background_session() as session:
        session.add(
            ModelSource(
                id=key_id,
                name=name.strip(),
                kind="swissai",
                base_url=get_settings().upstream_base_url,
                api_key_encrypted=TokenEncryptor().encrypt(secret),
                is_enabled=True,
                supports_chat_completions=True,
                supports_responses=True,
                supports_embeddings=True,
                supports_audio_transcriptions=False,
                max_concurrency=cap,
            )
        )
        await session.flush()
        session.add(
            SwissAIKeyState(
                source_id=key_id,
                fingerprint=fingerprint(secret),
                key_prefix="sk-rc-…" + secret[-4:],
            )
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            raise KeyConflict("This SwissAI key is already configured") from exc
    return key_id


async def patch_key(key_id: str, changes: dict) -> None:
    secret = changes.get("apiKey")
    if secret is not None:
        validate_secret(secret)
    async with sqlite_writer_section(), get_background_session() as session:
        state = await session.scalar(
            select(SwissAIKeyState).where(SwissAIKeyState.source_id == key_id).with_for_update()
        )
        source = await session.get(ModelSource, key_id)
        if state is None or source is None:
            raise KeyNotFound("SwissAI key not found")
        if "name" in changes:
            source.name = changes["name"].strip()
        if "enabled" in changes:
            source.is_enabled = changes["enabled"]
        if "maxConcurrency" in changes:
            source.max_concurrency = changes["maxConcurrency"]
        if secret is not None:
            source.api_key_encrypted = TokenEncryptor().encrypt(secret)
            state.fingerprint = fingerprint(secret)
            state.key_prefix = "sk-rc-…" + secret[-4:]
            state.generation += 1
            state.invalid_at = state.cooldown_until = state.failure_reason = None
            state.failures = 0
        source.updated_at = utcnow()
        try:
            await session.commit()
        except IntegrityError as exc:
            raise KeyConflict("This SwissAI key is already configured") from exc


async def delete_key(key_id: str) -> bool:
    await patch_key(key_id, {"enabled": False})
    async with sqlite_writer_section(), get_background_session() as session:
        await session.execute(delete(SwissAILease).where(SwissAILease.expires_at <= utcnow()))
        count = await session.scalar(
            select(func.count()).select_from(SwissAILease).where(SwissAILease.source_id == key_id)
        )
        if count:
            return False
        source = await session.get(ModelSource, key_id)
        if source is None:
            raise KeyNotFound("SwissAI key not found")
        await session.delete(source)
        await session.commit()
        return True


async def select_key(
    config: PoolSettings,
    excluded: set[str],
    allowed: set[str] | None,
    owner: tuple[str, int] | None,
) -> tuple[SelectedKey | None, bool, float | None]:
    """Lock pool state in a stable order, revalidate and claim capacity in one transaction.

    PostgreSQL row locks serialize replicas. SQLite uses its process writer gate
    plus BEGIN IMMEDIATE for cross-process exclusion; the host launcher fences
    file-backed SQLite to one process as in upstream.
    """
    async with sqlite_writer_section(), get_background_session() as session:
        if session.bind.dialect.name == "sqlite":
            await session.execute(text("BEGIN IMMEDIATE"))
        states = list(
            await session.scalars(select(SwissAIKeyState).order_by(SwissAIKeyState.source_id).with_for_update())
        )
        sources = (
            {
                s.id: s
                for s in await session.scalars(
                    select(ModelSource).where(ModelSource.id.in_([s.source_id for s in states]))
                )
            }
            if states
            else {}
        )
        now = utcnow()
        await session.execute(delete(SwissAILease).where(SwissAILease.expires_at <= now))
        counts = {
            key_id: count
            for key_id, count in await session.execute(
                select(SwissAILease.source_id, func.count()).group_by(SwissAILease.source_id)
            )
        }
        candidates = []
        cooldowns = []
        for state in states:
            source = sources[state.source_id]
            if source.id in excluded or (allowed is not None and source.id not in allowed):
                continue
            if owner and (source.id, state.generation) != owner:
                continue
            if config.strategy == "single_key" and config.single_key_id and source.id != config.single_key_id:
                continue
            if not source.is_enabled or state.invalid_at or source.api_key_encrypted is None:
                continue
            if state.cooldown_until and state.cooldown_until > now:
                cooldowns.append((state.cooldown_until - now).total_seconds())
                continue
            candidates.append((source, state))
        usable = [
            (s, k) for s, k in candidates if counts.get(s.id, 0) < (s.max_concurrency or config.default_max_concurrency)
        ]
        if not usable:
            await session.commit()
            return None, bool(candidates), min(cooldowns) if cooldowns else None

        def score(pair):
            source, state = pair
            oldest = state.last_selected_at or datetime.min
            if config.strategy in {"fill_first", "single_key"}:
                return (0, source.created_at, source.id)
            pressure = counts.get(source.id, 0) / (source.max_concurrency or config.default_max_concurrency)
            return (0 if config.strategy == "round_robin" else pressure, oldest, source.id)

        source, state = min(usable, key=score)
        assert source.api_key_encrypted is not None
        lease_id = secrets.token_hex(16)
        state.last_selected_at = now
        session.add(SwissAILease(id=lease_id, source_id=source.id, expires_at=now + timedelta(seconds=90)))
        result = SelectedKey(
            source.id, source.name, source.api_key_encrypted, state.generation, state.failures, lease_id
        )
        await session.commit()
        return result, False, None


async def renew_lease(lease_id: str) -> bool:
    async with sqlite_writer_section(), get_background_session() as session:
        result = await session.execute(
            update(SwissAILease)
            .where(SwissAILease.id == lease_id, SwissAILease.expires_at > utcnow())
            .values(expires_at=utcnow() + timedelta(seconds=90))
            .returning(SwissAILease.id)
        )
        renewed = result.scalar_one_or_none() is not None
        await session.commit()
        return renewed


async def release_lease(lease_id: str) -> None:
    async with sqlite_writer_section(), get_background_session() as session:
        await session.execute(delete(SwissAILease).where(SwissAILease.id == lease_id))
        await session.commit()


async def health(selected: SelectedKey, failure: Failure | None, *, probe: bool = False) -> None:
    async with sqlite_writer_section(), get_background_session() as session:
        state = await session.scalar(
            select(SwissAIKeyState)
            .where(SwissAIKeyState.source_id == selected.id, SwissAIKeyState.generation == selected.generation)
            .with_for_update()
        )
        if state:
            now = utcnow()
            if failure:
                state.last_failure_at = now
                state.failure_reason = failure.reason
                if not failure.provider_wide:
                    state.failures += 1
                    if failure.invalid:
                        state.invalid_at = now
                    if failure.cooldown:
                        state.cooldown_until = now + timedelta(seconds=failure.cooldown)
            else:
                state.last_success_at = now
                # An older concurrent success must never erase a newer 429.
                if probe:
                    state.invalid_at = state.cooldown_until = state.failure_reason = None
                    state.failures = 0
                elif not state.cooldown_until or state.cooldown_until <= now:
                    state.failures = 0
            await session.commit()


async def continuation_owner(identifiers: list[str]) -> tuple[str, int] | None:
    if not identifiers:
        return None
    async with get_background_session() as session:
        rows = list(await session.scalars(select(SwissAIContinuation).where(SwissAIContinuation.id.in_(identifiers))))
        owners = {(row.source_id, row.generation) for row in rows}
    if len(rows) != len(set(identifiers)) or len(owners) != 1:
        raise KeyNotFound("continuation_owner_unavailable")
    return owners.pop()


async def save_owners(identifiers: set[str], selected: SelectedKey) -> None:
    async with sqlite_writer_section(), get_background_session() as session:
        for identifier in identifiers:
            existing = await session.get(SwissAIContinuation, identifier)
            if existing is None:
                session.add(
                    SwissAIContinuation(
                        id=identifier,
                        source_id=selected.id,
                        generation=selected.generation,
                        created_at=utcnow(),
                    )
                )
            elif (existing.source_id, existing.generation) != (selected.id, selected.generation):
                raise KeyConflict("SwissAI returned a continuation ID belonging to a different key")
        await session.commit()


async def record_attempt(request_id: str, index: int, selected: SelectedKey) -> str:
    attempt_id = secrets.token_hex(16)
    async with sqlite_writer_section(), get_background_session() as session:
        session.add(
            SwissAIAttempt(
                id=attempt_id,
                request_id=request_id,
                source_id=selected.id,
                key_label=selected.name,
                attempt_index=index,
                started_at=utcnow(),
            )
        )
        await session.commit()
    return attempt_id


async def finish_attempt(attempt_id: str, status: int | None, failure: str | None, visible: bool) -> None:
    async with sqlite_writer_section(), get_background_session() as session:
        await session.execute(
            update(SwissAIAttempt)
            .where(SwissAIAttempt.id == attempt_id)
            .values(
                finished_at=utcnow(),
                status_code=status,
                failure_reason=failure,
                downstream_visible=visible,
            )
        )
        await session.commit()
