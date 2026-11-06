"""Live SwissAI catalog, persisted atomically, with a strict 24-hour stale ceiling."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from app.core.clients.http import lease_model_source_session
from app.core.config.settings import get_settings
from app.core.metadata_store import write_metadata
from app.core.utils.time import utcnow
from app.modules.swissai.proxy import MAX_RESPONSE, bounded_read


class Catalog:
    def __init__(self):
        self.models: list[dict] = []
        self.fetched_at: datetime | None = None
        self.error: str | None = None
        self.lock = asyncio.Lock()
        self.path = get_settings().data_dir / "swissai-models.json"
        try:
            payload = json.loads(self.path.read_text())
            self.models = payload["models"]
            self.fetched_at = datetime.fromisoformat(payload["fetched_at"])
        except (OSError, ValueError, KeyError, TypeError):
            pass

    @property
    def age(self) -> float | None:
        return (utcnow() - self.fetched_at).total_seconds() if self.fetched_at else None

    def available(self, allowed: list[str] | None = None) -> list[dict]:
        if self.age is None or not 0 <= self.age <= 86400:
            return []
        return [
            model
            for model in self.models
            if isinstance(model, dict)
            and isinstance(model.get("id"), str)
            and model.get("has_service") is not False
            and model.get("status") not in {"inactive", "stopped", "expired", "unavailable"}
            and (allowed is None or model["id"] in allowed)
        ]

    async def refresh(self):
        async with self.lock:
            try:
                import aiohttp

                async with lease_model_source_session() as session:
                    async with session.get(
                        get_settings().upstream_base_url.rstrip("/") + "/models",
                        timeout=aiohttp.ClientTimeout(total=15),
                        allow_redirects=False,
                    ) as response:
                        response.raise_for_status()
                        payload = json.loads(await bounded_read(response, MAX_RESPONSE))
                models = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(models, list):
                    raise ValueError("invalid catalog")
                self.models = [
                    model for model in models if isinstance(model, dict) and isinstance(model.get("id"), str)
                ]
                self.fetched_at = utcnow()
                write_metadata(
                    self.path, json.dumps({"models": self.models, "fetched_at": self.fetched_at.isoformat()})
                )
                self.error = None
            except asyncio.CancelledError:
                raise
            except Exception:
                # Transport URLs, response bodies and exceptions may contain credentials.
                self.error = "SwissAI model catalog refresh failed"

    async def run(self):
        while True:
            await self.refresh()
            await asyncio.sleep(300)
