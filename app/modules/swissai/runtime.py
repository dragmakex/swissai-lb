"""SwissAI lifespan reusing upstream auth, migrations, retention, transport and drain machinery."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from urllib.parse import urlsplit

from anyio import to_thread
from sqlalchemy import create_engine, delete, inspect, select

from app.core.auth.dashboard_users_cache import get_dashboard_users_cache
from app.core.bootstrap import ensure_auto_bootstrap_token
from app.core.clients.http import close_http_client, init_http_client
from app.core.clock import REAL_CLOCK, REAL_SCHEDULER, Clock, Scheduler
from app.core.config.key_fingerprint import verify_encryption_key_fingerprint
from app.core.config.settings import get_settings
from app.core.config.settings_cache import get_settings_cache
from app.core.retention.job import get_effective_retention
from app.core.runtime_logging import install_redacting_loop_exception_handler
from app.core.utils.shared_future import _await_cleanup_deferring_cancellation
from app.core.utils.time import utcnow
from app.db.migration_lock import migration_lock
from app.db.migration_url import to_sync_database_url
from app.db.models import AuditLog, RequestLog, SwissAIAttempt, SwissAIContinuation
from app.db.session import close_db, get_background_session, init_background_db, sqlite_writer_section
from app.modules.swissai.catalog import Catalog

logger = logging.getLogger(__name__)


def verify_target_database(database_url: str | None = None):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = to_sync_database_url(database_url or settings.database_url)
    engine = create_engine(url)
    try:
        # Do not mistake a peer's partially applied fresh migration for a legacy database.
        with migration_lock(url, timeout_seconds=settings.database_migration_lock_timeout_seconds):
            tables = set(inspect(engine).get_table_names())
            if tables and "swissai_key_state" not in tables:
                raise RuntimeError(
                    "Refusing to migrate an upstream or prototype database. SwissAI LB v1 requires a fresh database; "
                    "choose a new SWISSAI_LB_DATA_DIR / SWISSAI_LB_DATABASE_URL. Existing data has not been modified."
                )
    finally:
        engine.dispose()


def validate_upstream():
    settings = get_settings()
    parsed = urlsplit(settings.upstream_base_url)
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in {"https", "http"}
    ):
        raise RuntimeError(
            "SWISSAI_LB_UPSTREAM_BASE_URL must be an absolute URL without credentials, query or fragment"
        )
    if parsed.scheme != "https" and not settings.allow_insecure_upstream:
        raise RuntimeError("HTTP upstream requires explicit SWISSAI_LB_ALLOW_INSECURE_UPSTREAM=true for development")
    # Bootstrap-only: the dashboard cannot change network destinations.


class SwissAIRuntime:
    def __init__(self, *, clock: Clock = REAL_CLOCK, scheduler: Scheduler = REAL_SCHEDULER):
        self._clock = clock
        self._scheduler = scheduler
        self.queued = 0
        self.catalog = Catalog()
        self.tasks: list[asyncio.Task] = []

    async def prune_metadata(self) -> None:
        retention = await get_effective_retention()
        if not retention.request_log_days:
            return
        cutoff = utcnow() - timedelta(days=retention.request_log_days)
        for model, column in (
            (SwissAIAttempt, SwissAIAttempt.started_at),
            (SwissAIContinuation, SwissAIContinuation.created_at),
            (AuditLog, AuditLog.timestamp),
        ):
            eligible = select(model.id).where(column < cutoff)
            if model is SwissAIAttempt:
                eligible = eligible.where(
                    ~select(RequestLog.id).where(RequestLog.request_id == SwissAIAttempt.request_id).exists()
                )
            while True:
                async with sqlite_writer_section(), get_background_session() as session:
                    ids = list(await session.scalars(eligible.limit(1000)))
                    if not ids:
                        break
                    await session.execute(delete(model).where(model.id.in_(ids)))
                    await session.commit()

    async def retention(self) -> None:
        from app.core.scheduling.leader_election import get_leader_election

        while True:
            try:
                await get_leader_election().run_if_leader(self.prune_metadata)
            except Exception:
                logger.error("SwissAI metadata retention pass failed; the next scheduled pass will retry")
            await self._scheduler.sleep(3600)

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


@asynccontextmanager
async def lifespan(app):
    import app.core.shutdown as shutdown
    import app.core.startup as startup
    from app.main import build_data_retention_scheduler
    from app.modules.api_keys.last_used_coalescer import build_api_key_last_used_flush_scheduler
    from app.modules.api_keys.reset_scheduler import build_api_key_limit_reset_scheduler

    settings = get_settings()
    validate_upstream()
    await to_thread.run_sync(verify_target_database)
    shutdown.prepare_lifespan_start()
    startup._startup_complete = False
    install_redacting_loop_exception_handler(asyncio.get_running_loop())
    await get_settings_cache().invalidate(propagate=False)
    await get_dashboard_users_cache().invalidate(propagate=False)
    # Preserve upstream's startup seam (tests and embedded deployments override it).
    from app import main as main_module

    resources = AsyncExitStack()
    resources.push_async_callback(close_db)
    try:
        await main_module.init_db()
        init_background_db()
        await verify_encryption_key_fingerprint()
        token = await ensure_auto_bootstrap_token()
        bootstrap_file = settings.data_dir / "bootstrap.token"
        if token:
            from app.core.metadata_store import write_metadata

            write_metadata(bootstrap_file, token + "\n")
            logger.warning(
                "First-run dashboard bootstrap token is stored in the data directory's bootstrap.token (mode 0600)"
            )
        else:
            bootstrap_file.unlink(missing_ok=True)

        async def drain_control_plane() -> None:
            clean = await main_module._drain_detached_control_plane_tasks(
                shutdown.remaining_post_drain_cleanup_timeout_seconds() or 0
            )
            if not clean:
                logger.warning("Control-plane work did not drain within the shutdown budget")

        resources.push_async_callback(close_http_client)
        resources.push_async_callback(drain_control_plane)
        await init_http_client()
        from app.core.scheduling.leader_election import get_leader_election
        from app.modules.reports.cache import ReportsCaches

        resources.push_async_callback(get_leader_election().release)
        app.state.reports_caches = ReportsCaches()
        runtime = SwissAIRuntime()
        app.state.swissai = runtime
        schedulers = [
            build_data_retention_scheduler(),
            build_api_key_last_used_flush_scheduler(),
            build_api_key_limit_reset_scheduler(),
            main_module.build_account_usage_rollup_scheduler(),
            main_module.build_telemetry_scheduler(),
        ]
        for scheduler in schedulers:
            # Register before start: a partially started scheduler still owns resources.
            resources.push_async_callback(scheduler.stop)
            await scheduler.start()
        from app.core.auth.api_key_cache import get_api_key_cache
        from app.core.cache.invalidation import (
            NAMESPACE_API_KEY,
            NAMESPACE_DASHBOARD_USERS,
            NAMESPACE_FIREWALL,
            NAMESPACE_SETTINGS,
            CacheInvalidationPoller,
            set_cache_invalidation_poller,
        )
        from app.core.middleware.firewall_cache import get_firewall_ip_cache
        from app.db.session import SessionLocal

        poller = CacheInvalidationPoller(SessionLocal)
        poller.on_invalidation(NAMESPACE_API_KEY, get_api_key_cache().clear)
        poller.on_invalidation(NAMESPACE_SETTINGS, lambda: get_settings_cache().invalidate(propagate=False))
        poller.on_invalidation(
            NAMESPACE_DASHBOARD_USERS, lambda: get_dashboard_users_cache().invalidate(propagate=False)
        )
        poller.on_invalidation(NAMESPACE_DASHBOARD_USERS, main_module.get_auth_provider_registry().clear)
        poller.on_invalidation(NAMESPACE_DASHBOARD_USERS, main_module.get_identity_resolution_cache().clear)
        poller.on_invalidation(NAMESPACE_FIREWALL, get_firewall_ip_cache().invalidate_all)
        resources.callback(set_cache_invalidation_poller, None)
        resources.push_async_callback(poller.stop)
        set_cache_invalidation_poller(poller)
        await poller.prime()
        await poller.start()
        resources.push_async_callback(runtime.stop)
        runtime.tasks = [asyncio.create_task(runtime.catalog.run()), asyncio.create_task(runtime.retention())]
        if settings.event_loop_lag_warn_threshold_seconds > 0:
            runtime.tasks.append(
                asyncio.create_task(
                    main_module.run_event_loop_lag_monitor(
                        warn_threshold_seconds=settings.event_loop_lag_warn_threshold_seconds,
                    )
                )
            )
        startup._startup_complete = True
        yield
    finally:
        startup._startup_complete = False
        try:
            shutdown.commit_shutdown(timeout_seconds=settings.shutdown_drain_timeout_seconds)
            await shutdown.wait_for_in_flight_drain(timeout_seconds=shutdown.remaining_drain_timeout_seconds() or 0)
            shutdown.close_control_plane_task_admission()
        finally:
            cancellation = await _await_cleanup_deferring_cancellation(resources.aclose())
            shutdown.mark_lifespan_completed()
            if cancellation is not None:
                raise cancellation
