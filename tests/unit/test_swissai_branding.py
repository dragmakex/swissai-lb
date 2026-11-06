from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

from app import cli
from app.core.utils.time import utcnow
from app.db import migrate
from app.modules.runtime.schemas import RuntimeVersionResponse
from app.modules.telemetry.scheduler import TELEMETRY_FIELDS_DOCUMENTATION

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
INHERITED_BRAND = re.compile(r"codex[- ]lb", re.IGNORECASE)


def test_readme_keeps_only_one_short_attribution_line() -> None:
    text = (ROOT / "README.md").read_text()
    assert text.startswith("# SwissAI LB\n")
    matches = [line for line in text.splitlines() if INHERITED_BRAND.search(line)]
    assert matches == ["Based on [codex-lb](https://github.com/Soju06/codex-lb)."]
    assert (ROOT / "LICENSE").is_file()


@pytest.mark.parametrize(
    "relative",
    [
        "AGENTS.md",
        "PRINCIPLES.md",
        ".github/CONTRIBUTING.md",
        ".github/SECURITY.md",
        "openspec/specs/swissai-key-pool/context.md",
        "openspec/specs/swissai-key-pool/spec.md",
        "openspec/specs/admin-auth/context.md",
        "openspec/specs/admin-auth/ops.md",
        "openspec/specs/configuration-tiers/reference.md",
        "openspec/specs/database-backends/context.md",
        "openspec/specs/user-documentation/context.md",
    ],
)
def test_current_operator_guides_use_swissai_branding(relative: str) -> None:
    assert not INHERITED_BRAND.search((ROOT / relative).read_text()), relative


def test_dashboard_source_has_no_inherited_branding() -> None:
    sources = (ROOT / "frontend/src").rglob("*")
    for path in sources:
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".json"}:
            continue
        if "test" in path.parts or "__integration__" in path.parts or ".test." in path.name:
            continue
        assert not INHERITED_BRAND.search(path.read_text()), path.relative_to(ROOT)
    assert not INHERITED_BRAND.search((ROOT / "frontend/index.html").read_text())


@pytest.mark.parametrize("program", ["swissai-lb", "swissai-lb-db"])
def test_cli_help_uses_the_current_product_name(program: str, monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", [program, "--help"])
    parse = cli._parse_args if program == "swissai-lb" else migrate._parse_args
    with pytest.raises(SystemExit) as result:
        parse()
    assert result.value.code == 0
    text = capsys.readouterr().out
    assert "SwissAI LB" in text
    assert not INHERITED_BRAND.search(text)


def test_package_and_runtime_defaults_identify_the_fork() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert "SwissAI LB" in project["description"]
    assert not INHERITED_BRAND.search(project["description"])
    response = RuntimeVersionResponse(current_version="0.1.0-beta.1", checked_at=utcnow())
    assert response.release_url == "https://github.com/dragmakex/swissai-lb/releases/latest"
    assert (
        TELEMETRY_FIELDS_DOCUMENTATION
        in (ROOT / "frontend/src/features/settings/components/telemetry-consent-dialog.tsx").read_text()
    )
