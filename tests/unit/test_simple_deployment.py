"""Default laptop/VPS operation needs only the application and its data volume."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_default_compose_starts_only_the_application_without_an_env_file() -> None:
    config = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = config["services"]
    assert [name for name, service in services.items() if not service.get("profiles")] == ["server"]
    server = services["server"]
    assert server["env_file"] == [{"path": ".env.local", "required": False}]
    assert server["ports"] == ["127.0.0.1:2455:2455"]
    assert server["volumes"] == ["swissai-lb-data:/var/lib/swissai-lb"]
    assert config["volumes"]["swissai-lb-data"]["name"] == "swissai-lb-data"
    assert "command" not in server and "entrypoint" not in server
    assert "dev" in services["frontend"]["profiles"]
    assert "postgres" in services["postgres"]["profiles"]
    assert not server.get("depends_on")


def test_frontend_uses_committed_components_not_generator_or_doctor_clis() -> None:
    import json

    package = json.loads((ROOT / "frontend/package.json").read_text())
    assert not {"shadcn", "react-doctor"} & package["devDependencies"].keys()
    assert not any(name.startswith("doctor") for name in package["scripts"])
    assert {"lint", "typecheck", "test", "build"} <= package["scripts"].keys()
    assert "shadcn/tailwind.css" not in (ROOT / "frontend/src/index.css").read_text()
