from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_stock_compose_uses_user_defined_default_bridge() -> None:
    compose: dict[str, Any] = yaml.safe_load((_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert compose["networks"]["default"] == {"driver": "bridge"}
    for service in compose["services"].values():
        assert service.get("network_mode") != "bridge"
        assert "dns" not in service


def test_docker_quickstart_uses_the_single_service_compose_bridge() -> None:
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docker compose up -d --build" in readme
    assert "127.0.0.1:2455" in readme
    assert "ssh -N -L 2455:127.0.0.1:2455" in readme
    assert "without `-v`" in readme
    assert "--network host" not in readme and "--dns " not in readme


def test_running_container_resolver_runbook_uses_bridge_scoped_systemd_listener() -> None:
    context = (_REPO_ROOT / "openspec/specs/deployment-networking/context.md").read_text(encoding="utf-8")

    assert "DNSStubListenerExtra=%s" in context
    assert "docker exec --user 0 codex-lb" in context
    assert "without restarting codex-lb" in context
    assert "rather than `0.0.0.0`" in context
