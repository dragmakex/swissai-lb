from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_only_supported_delivery_and_ci_surfaces_remain() -> None:
    for name in (
        "deploy/helm",
        "flake.nix",
        "flake.lock",
        "frontend/bun.nix",
        "Dockerfile.distroless",
        "scripts/distroless-entrypoint.py",
        "scripts/helm-kind-smoke.sh",
        "docker-compose.prod.yml",
        "README.zh-CN.md",
        "mkdocs.yml",
        "docs",
        ".github/CODEOWNERS",
        ".all-contributorsrc",
        "renovate.json",
    ):
        assert not (ROOT / name).exists(), name
    assert {path.name for path in (ROOT / ".github/workflows").glob("*.yml")} == {
        "ci.yml",
        "simplicity-budgets.yml",
        "windows-startup.yml",
    }
    assert {path.name for path in ROOT.glob("Dockerfile*")} == {"Dockerfile"}
    assert {path.name for path in ROOT.glob("docker-compose*.yml")} == {"docker-compose.yml"}


def test_ignore_policy_protects_private_data_without_hiding_source() -> None:
    private = {
        ".env",
        ".env.local",
        "scratch/encryption.key",
        "scratch/bootstrap.token",
        "scratch/store.db",
        "scratch/store.db-wal",
        "scratch/store.db-shm",
        "scratch/store.sqlite3",
        "scratch/operator.pem",
        "scratch/server.log",
        "scripts/traffic_analysis/output/private-capture.jsonl",
        "frontend/node_modules/package/index.js",
        "app/static/index.html",
    }
    public = {
        ".env.example",
        "uv.lock",
        "frontend/bun.lock",
        "frontend/package.json",
        "app/modules/swissai/proxy.py",
        "tests/fixtures/codex/config.toml",
        "openspec/specs/configuration-tiers/reference.md",
        "scripts/traffic_analysis/output/.gitkeep",
    }
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=ROOT,
        input="\n".join(sorted(private | public)) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    assert set(result.stdout.splitlines()) == private


def test_current_source_snapshot_fits_root_allowlist() -> None:
    # The stock budget checker reads HEAD; validate this uncommitted removal snapshot too.
    names = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, text=True).split(
        "\0"
    )
    entries = {Path(name).parts[0] for name in names if name and ((ROOT / name).exists() or (ROOT / name).is_symlink())}
    budgets = tomllib.loads((ROOT / ".github/simplicity-budgets.toml").read_text())
    assert entries <= set(budgets["root_files"]["allowed"])
    assert {"LICENSE", ".gitleaks.toml"} <= entries


def test_readme_local_links_exist() -> None:
    links = re.findall(r"\]\(([^)]+)\)", (ROOT / "README.md").read_text())
    local = [link for link in links if "://" not in link and not link.startswith("#")]
    assert local
    for link in local:
        assert (ROOT / link.split("#", 1)[0]).is_file(), link
