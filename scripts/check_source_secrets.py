"""Scan a Git-listed production-source snapshot without test fixtures or build caches."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_SOURCE_DIRS = {"app", "frontend", "config", "scripts", ".github"}
_SOURCE_FILES = {
    ".env.example",
    ".gitleaks.toml",
    "Dockerfile",
    "docker-compose.yml",
    "pyproject.toml",
}
_FRONTEND_BUILD_FILES = {"frontend/package.json", "frontend/bun.lock", "frontend/vite.config.ts"}


def is_production_source(path: Path) -> bool:
    if path.parts[0] not in _SOURCE_DIRS and path.as_posix() not in _SOURCE_FILES:
        return False
    if path.parts[0] == "frontend" and not (
        path.as_posix().startswith("frontend/src/") or path.as_posix() in _FRONTEND_BUILD_FILES
    ):
        return False
    return not (
        any(part in {"test", "tests", "__tests__", "__integration__", "__pycache__", "static"} for part in path.parts)
        or ".test." in path.name
    )


def stage_sources(root: Path, stage: Path) -> int:
    names = subprocess.check_output(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"])
    count = 0
    for name in sorted(set(names.split(b"\0")) - {b""}):
        relative = Path(os.fsdecode(name))
        if not is_production_source(relative):
            continue
        source = root / relative
        if source.is_symlink():
            raise ValueError(f"Source symlink requires review: {relative}")
        if not source.is_file():
            continue
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Write the redacted Gitleaks JSON report here")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="swissai-source-scan-") as directory:
        stage = Path(directory)
        count = stage_sources(root, stage)
        print(f"Scanning {count} production-source files; excludes fixtures, generated assets and caches.", flush=True)
        return subprocess.run(
            [
                "gitleaks",
                "dir",
                str(stage),
                "--config",
                str(root / ".gitleaks.toml"),
                "--no-banner",
                "--redact",
                "--ignore-gitleaks-allow",
                "--report-format",
                "json",
                "--report-path",
                str(args.report.resolve()),
            ],
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
