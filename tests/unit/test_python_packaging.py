"""The supported Python application must not acquire a native build dependency."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_retired_rust_workspace_and_adapter_are_absent() -> None:
    for name in (
        "Cargo.toml",
        "Cargo.lock",
        "rust-toolchain.toml",
        "deny.toml",
        "crates",
        "app/core/clients/native_egress.py",
    ):
        assert not (ROOT / name).exists(), name
    for path in (ROOT / "app").rglob("*.py"):
        if "static" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert "native_egress" not in (node.module or ""), path
            elif isinstance(node, ast.Import):
                assert all("native_egress" not in alias.name for alias in node.names), path


def test_container_ships_python_and_built_dashboard_without_rust() -> None:
    source = (ROOT / "Dockerfile").read_text()
    assert "cargo build" not in source and "native-egress-build" not in source
    assert "uv sync --frozen" in source
    runtime = source.rsplit(" AS runtime", maxsplit=1)[1]
    assert "COPY --from=python-build /opt/venv /opt/venv" in runtime
    assert "app/static" in runtime


def test_default_ci_does_not_require_retired_worker_or_cluster_tools() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert "rust" not in workflow["jobs"]
    assert "rust" not in workflow["jobs"]["ci-required"]["needs"]
    for name in ("helm-lint", "helm-smoke-kind", "nix-flake"):
        assert name not in workflow["jobs"]
        assert name not in workflow["jobs"]["ci-required"]["needs"]
    source = (ROOT / "Makefile").read_text()
    for line in source.splitlines():
        if line.startswith(("ci:", "ci-fast:")):
            assert not any(tool in line for tool in ("rust", "helm", "postgres", "docker"))
