from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_development_compose_uses_owned_launcher_and_restarts_synced_source() -> None:
    compose = yaml.safe_load(_read("docker-compose.yml"))
    server = compose["services"]["server"]
    assert "command" not in server and "entrypoint" not in server
    assert 'CMD ["/app/scripts/docker-entrypoint.sh"]' in _read("Dockerfile")
    assert "exec python -m app.cli" in _read("scripts/docker-entrypoint.sh")
    app_watch = next(item for item in server["develop"]["watch"] if item["path"] == "./app")
    assert app_watch["action"] == "sync+restart"


@pytest.mark.parametrize(
    ("relative_path", "command"),
    [
        ("README.md", "uv run swissai-lb"),
        (
            "openspec/specs/responses-api-compat/ops.md",
            ".venv/bin/python -m app.cli --host 127.0.0.1 --port 2460",
        ),
    ],
)
def test_documented_launchers_delegate_to_app_cli(
    relative_path: str,
    command: str,
) -> None:
    assert command in _read(relative_path)


@pytest.mark.parametrize(
    ("relative_path", "contract"),
    [
        ("Dockerfile", 'CMD ["/app/scripts/docker-entrypoint.sh"]'),
        ("scripts/docker-entrypoint.sh", "exec python -m app.cli"),
    ],
)
def test_production_launchers_delegate_to_app_cli(relative_path: str, contract: str) -> None:
    assert contract in _read(relative_path)


def test_compose_does_not_override_the_app_cli_launcher() -> None:
    server = yaml.safe_load(_read("docker-compose.yml"))["services"]["server"]

    assert "command" not in server
    assert "entrypoint" not in server
