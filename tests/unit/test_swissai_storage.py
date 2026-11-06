from __future__ import annotations

import hashlib
import json
import stat
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from cryptography.fernet import Fernet
from packaging.version import Version
from sqlalchemy import create_engine

from app.core.crypto import get_or_create_key
from app.modules.swissai.runtime import verify_target_database


def test_concurrent_first_run_publishes_one_complete_encryption_key(tmp_path: Path) -> None:
    path = tmp_path / "shared" / "encryption.key"
    barrier = Barrier(8)

    def create_key(_: int) -> bytes:
        barrier.wait(timeout=10)
        return get_or_create_key(path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        keys = list(executor.map(create_key, range(8)))
    assert len(set(keys)) == 1
    assert path.read_bytes() == keys[0]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(path.parent.glob(".encryption-*")) == []
    encrypted = Fernet(keys[0]).encrypt(b"test-only-credential")
    assert all(Fernet(key).decrypt(encrypted) == b"test-only-credential" for key in keys)


@pytest.mark.parametrize("legacy_table", ["accounts", "swissai_keys"])
def test_legacy_database_is_rejected_without_modification(tmp_path: Path, legacy_table: str) -> None:
    path = tmp_path / "legacy.db"
    url = "sqlite:///" + str(path)
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"CREATE TABLE {legacy_table} (id INTEGER PRIMARY KEY, name TEXT)")
            connection.exec_driver_sql(f"INSERT INTO {legacy_table} VALUES (1, 'preserve me')")
    finally:
        engine.dispose()
    before = hashlib.sha256(path.read_bytes()).digest()
    with pytest.raises(RuntimeError, match="Refusing to migrate"):
        verify_target_database(url)
    assert hashlib.sha256(path.read_bytes()).digest() == before


def test_empty_database_passes_ownership_check(tmp_path: Path) -> None:
    verify_target_database("sqlite:///" + str(tmp_path / "fresh.db"))


def test_fork_runtime_and_package_versions_agree() -> None:
    from app import __version__
    from app.main import create_app

    root = Path(__file__).parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    frontend = json.loads((root / "frontend/package.json").read_text())
    assert project["name"] == "swissai-lb"
    assert frontend["private"] is True
    assert Version(__version__) == Version(project["version"]) == Version(frontend["version"])
    assert Version(__version__).is_prerelease
    assert create_app().version == __version__
    lock = tomllib.loads((root / "uv.lock").read_text())
    packages = [package for package in lock["package"] if package["name"] == project["name"]]
    assert len(packages) == 1
    assert Version(packages[0]["version"]) == Version(__version__)
