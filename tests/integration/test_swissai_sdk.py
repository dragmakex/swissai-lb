from __future__ import annotations

import pytest_asyncio
from aiohttp import web
from httpx2 import ASGITransport, AsyncClient
from openai import AsyncOpenAI
from sqlalchemy import select

from app.core.config.settings import get_settings
from app.db.models import RequestLog
from app.db.session import get_background_session
from tests.fixtures.fake_swissai import FakeSwissAI


@pytest_asyncio.fixture
async def sdk(app_instance, monkeypatch, tmp_path):
    fake = FakeSwissAI()
    runner = web.AppRunner(fake.application())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    monkeypatch.setenv("SWISSAI_LB_UPSTREAM_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("SWISSAI_LB_ALLOW_INSECURE_UPSTREAM", "true")
    monkeypatch.setenv("SWISSAI_LB_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        async with app_instance.router.lifespan_context(app_instance):
            async with AsyncClient(transport=ASGITransport(app_instance), base_url="http://testserver") as management:
                for index in range(2):
                    response = await management.post(
                        "/api/swissai-keys",
                        json={
                            "name": f"SDK {index}",
                            "apiKey": f"sk-rc-test-sdk-{index}-00000",
                        },
                    )
                    assert response.status_code == 201, response.text
                http = AsyncClient(transport=ASGITransport(app_instance), base_url="http://testserver")
                async with AsyncOpenAI(
                    base_url="http://testserver/v1", api_key="unused-with-auth-off", http_client=http, max_retries=0
                ) as client:
                    yield client, fake
    finally:
        await runner.cleanup()
        get_settings.cache_clear()


async def test_openai_sdk_models_chat_completions_responses_embeddings(sdk):
    client, fake = sdk
    models = await client.models.list()
    assert models.data[0].id == "apertus-test"
    chat = await client.chat.completions.create(model="apertus-test", messages=[{"role": "user", "content": "Hi"}])
    assert chat.choices[0].message.content == "Hello"
    completion = await client.completions.create(model="apertus-test", prompt="Hi")
    assert completion.choices[0].text == "Hello"
    response = await client.responses.create(model="apertus-test", input="Hi")
    assert response.output_text == "Hello"
    await client.responses.create(model="apertus-test", input="Next", previous_response_id=response.id)
    assert fake.calls[-1][0] == fake.calls[-2][0]
    embeddings = await client.embeddings.create(model="apertus-test", input="Hi")
    assert embeddings.data[0].embedding == [0.1, 0.2, 0.3]


async def test_openai_sdk_streams_preserve_json_sse_and_usage(sdk):
    client, _ = sdk
    chat = await client.chat.completions.create(
        model="apertus-test", messages=[{"role": "user", "content": "Hi"}], stream=True
    )
    chunks = [chunk async for chunk in chat]
    assert chunks[0].choices[0].delta.content == "Hello"
    response = await client.responses.create(model="apertus-test", input="Hi", stream=True)
    events = [event async for event in response]
    assert any(event.type == "response.output_text.delta" and event.delta == "Hello" for event in events)
    assert events[-1].type == "response.completed"
    async with get_background_session() as session:
        logs = list(await session.scalars(select(RequestLog)))
        assert len(logs) == 2
        assert all(log.input_tokens == 3 and log.output_tokens == 2 for log in logs)


async def test_sdk_observes_one_response_after_transparent_failover(sdk):
    client, fake = sdk
    fake.next_statuses = [429, 200]
    response = await client.responses.create(model="apertus-test", input="Hi")
    assert response.output_text == "Hello"
    assert len(fake.calls) == 2
    assert fake.calls[0][0] != fake.calls[1][0]
    assert fake.calls[0][1] == fake.calls[1][1]
