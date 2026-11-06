"""Real two-process admission/migration/auth test against a disposable PostgreSQL database.

Set SWISSAI_LB_TEST_POSTGRES_ADMIN_URL to a dedicated test server whose user can
create databases. Never point this at an operator's production database.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import signal
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import psycopg
import pytest
from aiohttp import web
from psycopg import sql
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.e2e


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def ready(client: httpx.AsyncClient, base: str, processes: list[subprocess.Popen]) -> None:
    for _ in range(200):
        assert all(process.poll() is None for process in processes), (
            "Replica exited during startup; inspect replica logs"
        )
        try:
            if (await client.get(base + "/health/ready", timeout=1)).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.1)
    raise AssertionError("Replica did not become ready")


async def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        await asyncio.to_thread(process.wait, 20)
    except subprocess.TimeoutExpired:
        process.kill()
        await asyncio.to_thread(process.wait, 5)
        raise AssertionError("Replica exceeded its graceful shutdown bound")


async def test_two_real_replicas_share_caps_and_control_plane(tmp_path: Path):
    admin = os.environ.get("SWISSAI_LB_TEST_POSTGRES_ADMIN_URL")
    if not admin:
        pytest.skip("Requires a dedicated PostgreSQL test server with CREATE DATABASE permission")
    database = "swissai_e2e_" + secrets.token_hex(6)
    admin_url = make_url(admin).set(drivername="postgresql")
    database_url = admin_url.set(database=database)
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))

    active: dict[str, int] = {}
    peaks: dict[str, int] = {}
    calls: list[tuple[str, bytes]] = []
    total_peak = 0
    fail_next = False
    stream_started = asyncio.Event()
    stream_release = asyncio.Event()

    async def upstream(request):
        nonlocal total_peak, fail_next
        if request.path == "/v1/models":
            return web.json_response({"object": "list", "data": [{"id": "Apertus-test", "object": "model"}]})
        if request.path == "/v1/profile":
            return web.json_response({"ok": True})
        credential = request.headers.get("Authorization", "")
        body = await request.read()
        calls.append((credential, body))
        if request.path == "/v1/chat/completions" and b'"stream":true' in body:
            response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await response.prepare(request)
            await response.write(b'data: {"id":"chat_test","choices":[]}\n\n')
            stream_started.set()
            await stream_release.wait()
            await response.write(b"data: [DONE]\n\n")
            await response.write_eof()
            return response
        if fail_next:
            fail_next = False
            return web.json_response(
                {"error": {"message": "throttled", "code": "rate_limit"}}, status=429, headers={"Retry-After": "60"}
            )
        active[credential] = active.get(credential, 0) + 1
        peaks[credential] = max(peaks.get(credential, 0), active[credential])
        total_peak = max(total_peak, sum(active.values()))
        try:
            await asyncio.sleep(0.15)
            return web.json_response(
                {
                    "id": "resp_" + secrets.token_hex(8),
                    "object": "response",
                    "output": [],
                    "usage": {"input_tokens": 2, "output_tokens": 3},
                }
            )
        finally:
            active[credential] -= 1

    fake = web.Application()
    fake.router.add_route("*", "/{path:.*}", upstream)
    runner = web.AppRunner(fake)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    upstream_port = runner.addresses[0][1]
    ports = [unused_port(), unused_port()]
    processes = []
    handles = []
    environments = []
    try:
        for index, port in enumerate(ports):
            data = tmp_path / f"replica-{index}"
            data.mkdir()
            handle = (data / "server.log").open("wb")
            handles.append(handle)
            env = {key: value for key, value in os.environ.items() if not key.startswith("SWISSAI_LB_")}
            env.update(
                {
                    "SWISSAI_LB_DATA_DIR": str(data),
                    "SWISSAI_LB_DATABASE_URL": database_url.set(drivername="postgresql+asyncpg").render_as_string(
                        hide_password=False
                    ),
                    "SWISSAI_LB_ENCRYPTION_KEY_FILE": str(tmp_path / "shared-encryption.key"),
                    "SWISSAI_LB_UPSTREAM_BASE_URL": f"http://127.0.0.1:{upstream_port}/v1",
                    "SWISSAI_LB_ALLOW_INSECURE_UPSTREAM": "true",
                    "SWISSAI_LB_SHUTDOWN_DRAIN_TIMEOUT_SECONDS": "5",
                    "SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_ENABLED": "false",
                }
            )
            environments.append(env)
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "app.cli", "--host", "127.0.0.1", "--port", str(port)],
                    env=env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                )
            )
        async with httpx.AsyncClient(timeout=20) as client:
            bases = [f"http://127.0.0.1:{port}" for port in ports]
            await asyncio.gather(*(ready(client, base, processes) for base in bases))
            for index in range(2):
                response = await client.post(
                    bases[0] + "/api/swissai-keys",
                    json={
                        "name": f"shared {index}",
                        "apiKey": f"sk-rc-replica-test-{index}-00000",
                        "maxConcurrency": 1,
                    },
                )
                assert response.status_code == 201, response.text
            results = await asyncio.gather(
                *(
                    client.post(
                        bases[index % 2] + "/v1/embeddings",
                        json={
                            "model": "Apertus-test",
                            "input": "shared capacity",
                        },
                    )
                    for index in range(8)
                )
            )
            assert all(response.status_code == 200 for response in results), [
                response.status_code for response in results
            ]
            assert len(peaks) == 2 and all(peak == 1 for peak in peaks.values())
            assert total_peak == 2, "The pool should use both keys concurrently"

            # Persisted continuation ownership follows the request to another process.
            first = await client.post(bases[0] + "/v1/responses", json={"model": "Apertus-test", "input": "first"})
            owner = calls[-1][0]
            continuation = await client.post(
                bases[1] + "/v1/responses",
                json={
                    "model": "Apertus-test",
                    "input": "second",
                    "previous_response_id": first.json()["id"],
                },
            )
            assert continuation.status_code == 200 and calls[-1][0] == owner

            fail_next = True
            before = len(calls)
            retried = await client.post(bases[0] + "/v1/responses", json={"model": "Apertus-test", "input": "retry"})
            assert retried.status_code == 200, retried.text
            assert len(calls) == before + 2 and calls[-2][0] != calls[-1][0]
            states = (await client.get(bases[1] + "/api/swissai-keys")).json()
            assert any(key["status"] == "cooling_down" for key in states)
            cooled = {key["id"]: key["cooldownUntil"] for key in states if key["status"] == "cooling_down"}
            await stop(processes[0])
            processes[0] = subprocess.Popen(
                [sys.executable, "-m", "app.cli", "--host", "127.0.0.1", "--port", str(ports[0])],
                env=environments[0],
                stdout=handles[0],
                stderr=subprocess.STDOUT,
            )
            await ready(client, bases[0], processes)
            restarted = (await client.get(bases[0] + "/api/swissai-keys")).json()
            assert all(key["cooldownUntil"] == cooled[key["id"]] for key in restarted if key["id"] in cooled)

            # The settings invalidation bus must carry auth policy to the peer.
            created = await client.post(bases[0] + "/api/api-keys", json={"name": "shared SDK"})
            assert created.status_code == 200, created.text
            token = created.json()["key"]
            toggled = await client.put(bases[0] + "/api/settings", json={"apiKeyAuthEnabled": True})
            assert toggled.status_code == 200, toggled.text
            for _ in range(100):
                denied = await client.get(bases[1] + "/v1/models")
                if denied.status_code == 401:
                    break
                await asyncio.sleep(0.1)
            assert denied.status_code == 401, "Auth policy did not propagate to the other replica"
            allowed = await client.get(bases[1] + "/v1/models", headers={"Authorization": "Bearer " + token})
            assert allowed.status_code == 200, allowed.text

            # SIGTERM must drain an already-visible stream, not close its pooled client.
            async with client.stream(
                "POST",
                bases[0] + "/v1/chat/completions",
                json={
                    "model": "Apertus-test",
                    "messages": [],
                    "stream": True,
                },
                headers={"Authorization": "Bearer " + token},
            ) as streaming:
                assert streaming.status_code == 200
                chunks = streaming.aiter_bytes()
                assert b"chat_test" in await anext(chunks)
                await asyncio.wait_for(stream_started.wait(), 2)
                processes[0].terminate()
                await asyncio.sleep(0.1)
                assert processes[0].poll() is None, "Replica must remain alive while a stream drains"
                stream_release.set()
                remainder = b"".join([chunk async for chunk in chunks])
                assert b"[DONE]" in remainder
            await asyncio.to_thread(processes[0].wait, 20)
            # The retained uvicorn launcher re-raises SIGTERM after clean drain.
            assert processes[0].returncode == -signal.SIGTERM

            with psycopg.connect(database_url.render_as_string(hide_password=False)) as conn:
                leases = conn.execute("SELECT count(*) FROM swissai_leases").fetchone()
                revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                assert leases == (0,)
                assert revision is not None and revision[0].endswith("add_swissai_request_metadata")
            for process in processes:
                await stop(process)
            for index in range(2):
                text = (tmp_path / f"replica-{index}" / "server.log").read_text()
                assert "sk-rc-replica-test" not in text
                assert "Traceback" not in text
                assert "Application shutdown complete" in text
    finally:
        for process in processes:
            if process.poll() is None:
                await stop(process)
        for handle in handles:
            handle.close()
        await runner.cleanup()
        with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
