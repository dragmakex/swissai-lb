from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts.check_source_secrets import stage_sources


def test_source_snapshot_includes_untracked_code_and_excludes_fixtures(tmp_path: Path):
    root, stage = tmp_path / "repo", tmp_path / "stage"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    files = {
        "app/main.py",
        "frontend/src/view.tsx",
        "frontend/vite.config.ts",
        "frontend/bun.lock",
        "frontend/src/view.test.tsx",
        "frontend/src/test/mocks.ts",
        "frontend/src/__integration__/flow.tsx",
        "app/static/assets.js",
        "app/__pycache__/main.pyc",
        "tests/fixture.py",
        ".env.example",
        ".gitleaks.toml",
    }
    for name in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    subprocess.run(["git", "-C", str(root), "add", "app/main.py"], check=True)
    assert stage_sources(root, stage) == 6
    assert {str(path.relative_to(stage)) for path in stage.rglob("*") if path.is_file()} == {
        "app/main.py",
        "frontend/src/view.tsx",
        "frontend/vite.config.ts",
        "frontend/bun.lock",
        ".env.example",
        ".gitleaks.toml",
    }


def test_annotation_allowance_does_not_cover_credentials_or_other_paths():
    config = tomllib.loads((Path(__file__).resolve().parents[2] / ".gitleaks.toml").read_text())
    assert config["extend"]["useDefault"] is True
    rule = config["rules"][0]
    assert rule["id"] == "generic-api-key"
    allowance = rule["allowlists"][0]
    assert allowance["condition"] == "AND" and allowance["regexTarget"] == "match"
    match, path = allowance["regexes"][0], allowance["paths"][0]
    assert re.fullmatch(match, "private_key: Ed25519PrivateKey")
    assert not re.fullmatch(match, 'private_key = "sensitive-value"')
    assert re.search(path, "app/modules/telemetry/consent.py")
    assert not re.search(path, "app/other.py")


def test_source_symlink_cannot_pull_an_external_secret_into_the_snapshot(tmp_path: Path):
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    external = tmp_path / "external"
    external.write_text("outside repository")
    (root / "app/key.py").symlink_to(external)
    with pytest.raises(ValueError, match="Source symlink requires review"):
        stage_sources(root, tmp_path / "stage")
