"""Run the actual image through first start, hot SQLite backup and restored inference.

Set SWISSAI_LB_TEST_CONTAINER_IMAGE to an already-built local image. No real key,
external generation or operator volume is used. Uses the available local engine.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from tests.e2e.test_swissai_postgres_replicas import unused_port

pytestmark = pytest.mark.e2e


async def test_container_password_keys_inference_and_sqlite_restore(tmp_path: Path):
    image = os.environ.get("SWISSAI_LB_TEST_CONTAINER_IMAGE")
    if not image:
        pytest.skip("Set SWISSAI_LB_TEST_CONTAINER_IMAGE after building the runtime image")
    engine = shutil.which("podman") or shutil.which("docker")
    assert engine, "A running container engine is required"
    prefix = "swissai-smoke-" + secrets.token_hex(5)
    volumes = [prefix + "-original", prefix + "-restored"]
    containers: list[str] = []
    fixture = Path(__file__).parents[1] / "fixtures" / "fake_swissai.py"
    port = unused_port()
    base = f"http://127.0.0.1:{port}"
    bootstrap = "test-only-bootstrap-secret-00000000"
    credential = "sk-rc-test-container-000000000000"
    volume_mode = ":U" if Path(engine).name == "podman" else ""

    def run(*args: str) -> str:
        try:
            return subprocess.check_output([engine, *args], stderr=subprocess.STDOUT, text=True, timeout=120).strip()
        except subprocess.CalledProcessError as exc:
            output = exc.output.replace(credential, "[redacted]").replace(bootstrap, "[redacted]")
            raise AssertionError(f"Container {args[0]} failed: {output[-4000:]}") from exc

    def start(volume: str) -> str:
        name = prefix + "-" + str(len(containers))
        containers.append(name)
        run(
            "run",
            "-d",
            "--name",
            name,
            "-p",
            f"127.0.0.1:{port}:2455",
            "-v",
            f"{volume}:/var/lib/swissai-lb{volume_mode}",
            "-v",
            f"{fixture.resolve()}:/tmp/fake.py:ro",
            "-e",
            "SWISSAI_LB_UPSTREAM_BASE_URL=http://127.0.0.1:2467/v1",
            "-e",
            "SWISSAI_LB_ALLOW_INSECURE_UPSTREAM=true",
            "-e",
            "SWISSAI_LB_PROXY_ALLOW_ANONYMOUS_LAN=true",
            "-e",
            "SWISSAI_LB_TELEMETRY_ENABLED=false",
            "-e",
            "SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN=" + bootstrap,
            "--entrypoint",
            "sh",
            image,
            "-c",
            "python /tmp/fake.py --port 2467 >/tmp/fake.log 2>&1 & exec /app/scripts/docker-entrypoint.sh",
        )
        return name

    async def ready(client: httpx.AsyncClient) -> None:
        for _ in range(300):
            try:
                if (await client.get("/health/ready")).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.1)
        raise AssertionError("Container never became ready; inspect captured container logs")

    try:
        for volume in volumes:
            run("volume", "create", volume)
        original = start(volumes[0])
        async with httpx.AsyncClient(base_url=base, timeout=5, headers={"Origin": base}) as client:
            await ready(client)
            dashboard = await client.get("/")
            assert dashboard.status_code == 200 and "SwissAI LB" in dashboard.text
            password = await client.post(
                "/api/dashboard-auth/password/setup",
                json={
                    "password": "Container-Test-Password-00000!",
                    "bootstrapToken": bootstrap,
                },
            )
            assert password.status_code == 200, password.text
            key = await client.post("/api/swissai-keys", json={"name": "Restore fixture", "apiKey": credential})
            assert key.status_code == 201, key.text
            assert credential not in key.text and key.json()["status"] == "active"
            created = await client.post("/api/api-keys", json={"name": "Container SDK"})
            assert created.status_code == 200, created.text
            token = created.json()["key"]
            assert (await client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
            assert (await client.get("/v1/models")).status_code == 401
            headers = {"Authorization": "Bearer " + token}
            payload = {"model": "apertus-test", "messages": [{"role": "user", "content": "Container smoke"}]}
            first = await client.post("/v1/chat/completions", headers=headers, json=payload)
            assert first.status_code == 200, first.text
            assert first.json()["choices"][0]["message"]["content"] == "Hello"
            for _ in range(100):
                if (await client.get("/api/request-logs")).json()["total"] == 1:
                    break
                await asyncio.sleep(0.1)
            else:
                pytest.fail("The successful request never settled its durable log")
            metrics = await client.get("/metrics")
            assert metrics.status_code == 200
            assert 'swissai_lb_request_duration_seconds_count{route="/chat/completions"} 1.0' in metrics.text
            assert 'swissai_lb_requests_total{outcome="success",route="/chat/completions"} 1.0' in metrics.text
            # WAL readers need a writable SHM directory even with a mode=ro connection.
            # SQLite backup() includes committed WAL pages; never copy a live store.db alone.
            backup = (
                "import sqlite3,shutil; "
                "source=sqlite3.connect('file:/source/store.db?mode=ro',uri=True); "
                "target=sqlite3.connect('/backup/store.db'); source.backup(target); target.close(); source.close(); "
                "shutil.copy2('/source/encryption.key','/backup/encryption.key')"
            )
            run(
                "run",
                "--rm",
                "-v",
                volumes[0] + ":/source",
                "-v",
                volumes[1] + ":/backup" + volume_mode,
                "--entrypoint",
                "python",
                image,
                "-c",
                backup,
            )
            run("stop", "--time", "15", original)
            start(volumes[1])
            await ready(client)
            restored = await client.get("/api/swissai-keys")
            assert restored.status_code == 200, restored.text
            assert restored.json()[0]["id"] == key.json()["id"]
            second = await client.post("/v1/chat/completions", headers=headers, json=payload)
            assert second.status_code == 200, second.text
            for _ in range(100):
                logs = await client.get("/api/request-logs")
                if logs.status_code == 200 and logs.json()["total"] == 2:
                    break
                await asyncio.sleep(0.1)
            assert logs.status_code == 200 and logs.json()["total"] == 2
            assert "Container smoke" not in logs.text and credential not in logs.text
            assert all(row["costUsd"] is None for row in logs.json()["requests"])
    finally:
        for name in containers:
            logs = subprocess.run([engine, "logs", name], capture_output=True, text=True).stdout
            (tmp_path / (name + ".log")).write_text(logs)
            subprocess.run([engine, "rm", "-f", name], capture_output=True)
            assert credential not in logs and bootstrap not in logs
        for volume in volumes:
            subprocess.run([engine, "volume", "rm", "-f", volume], capture_output=True)
