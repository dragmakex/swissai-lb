"""Start the normal one-service Compose topology without an env file or database service."""

from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
import yaml

from tests.e2e.test_swissai_postgres_replicas import unused_port

pytestmark = pytest.mark.e2e


async def test_default_compose_dashboard_and_keys_survive_restart(tmp_path: Path) -> None:
    image = os.environ.get("SWISSAI_LB_TEST_CONTAINER_IMAGE")
    if not image:
        pytest.skip("Set SWISSAI_LB_TEST_CONTAINER_IMAGE to an already-built local image")
    engine = shutil.which("podman") or shutil.which("docker")
    assert engine, "A running disposable container engine is required"
    name = "swissai-compose-" + secrets.token_hex(5)
    volume = name + "-data"
    port = unused_port()
    base = f"http://127.0.0.1:{port}"
    config = yaml.safe_load((Path(__file__).parents[2] / "docker-compose.yml").read_text())
    # Isolate only the image, host port and volume; preserve default profiles,
    # optional env-file, entrypoint and application environment from the real file.
    config["services"]["server"]["image"] = image
    config["services"]["server"]["ports"] = [f"127.0.0.1:{port}:2455"]
    config["volumes"]["swissai-lb-data"]["name"] = volume
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text(yaml.safe_dump(config))
    assert not (tmp_path / ".env.local").exists()
    command = [engine, "compose", "-f", str(compose_file), "-p", name]

    def run(*args: str) -> str:
        return subprocess.check_output([*command, *args], stderr=subprocess.PIPE, text=True, timeout=120).strip()

    async def ready(client: httpx.AsyncClient) -> None:
        for _ in range(300):
            try:
                if (await client.get("/health/ready")).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.1)
        pytest.fail("Default Compose application did not become ready")

    try:
        run("up", "-d", "--no-build")
        assert run("ps", "--services", "--status", "running").splitlines() == ["server"]
        async with httpx.AsyncClient(base_url=base, timeout=5, headers={"Origin": base}) as client:
            await ready(client)
            assert "SwissAI LB" in (await client.get("/")).text
            bootstrap = run(
                "exec",
                "-T",
                "server",
                "python",
                "-c",
                "from pathlib import Path; print(Path('/var/lib/swissai-lb/bootstrap.token').read_text().strip())",
            )
            setup = await client.post(
                "/api/dashboard-auth/password/setup",
                json={
                    "password": "Compose-Test-Password-000000!",
                    "bootstrapToken": bootstrap,
                },
            )
            assert setup.status_code == 200
            created = await client.post(
                "/api/swissai-keys",
                json={
                    "name": "Compose persistence",
                    "apiKey": "sk-rc-test-compose-0000000000000",
                },
            )
            assert created.status_code == 201
            key_id = created.json()["id"]
            run("stop", "server")
            run("start", "server")
            await ready(client)
            inventory = await client.get("/api/swissai-keys")
            assert inventory.status_code == 200
            assert inventory.json()[0]["id"] == key_id
            assert "sk-rc-test-compose-0000000000000" not in inventory.text
    finally:
        subprocess.run([*command, "down", "--remove-orphans"], capture_output=True, timeout=120)
        subprocess.run([engine, "volume", "rm", "-f", volume], capture_output=True, timeout=30)
