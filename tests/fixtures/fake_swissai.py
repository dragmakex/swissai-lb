"""Local-only, key-free SwissAI contract fixture for SDK and browser smoke tests."""

from __future__ import annotations

import argparse
import asyncio
import json

from aiohttp import web


class FakeSwissAI:
    def __init__(self):
        self.calls: list[tuple[str, bytes]] = []
        self.owners: dict[str, str] = {}
        self.next_statuses: list[int] = []

    def application(self) -> web.Application:
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", self.handle)
        return app

    async def handle(self, request: web.Request) -> web.StreamResponse:
        if request.path == "/v1/models":
            return web.json_response(
                {
                    "object": "list",
                    "data": [
                        {"id": "apertus-test", "object": "model", "created": 0, "owned_by": "swissai-test"},
                    ],
                }
            )
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer sk-rc-test-"):
            return web.json_response(
                {"error": {"message": "Use a fake sk-rc-test-... key", "code": "invalid_api_key"}}, status=401
            )
        if request.path == "/v1/profile":
            return web.json_response({"detail": "Invalid access token"}, status=401)
        raw = await request.read()
        body = json.loads(raw)
        if request.path == "/v1/chat/completions" and body == {"model": "__swissai_lb_auth_probe__", "messages": []}:
            return web.json_response(
                {"error": {"type": "invalid_request_error", "message": "Model '__swissai_lb_auth_probe__' not found."}},
                status=404,
            )
        self.calls.append((auth, raw))
        if self.next_statuses:
            status = self.next_statuses.pop(0)
            if status != 200:
                return web.json_response(
                    {"error": {"message": "Injected test failure", "code": "test_failure"}},
                    status=status,
                    headers={"Retry-After": "60"},
                )
        model = body.get("model", "apertus-test")
        suffix = str(len(self.calls))
        usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
        if request.path == "/v1/embeddings":
            return web.json_response(
                {
                    "object": "list",
                    "model": model,
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
                    "usage": {"prompt_tokens": 3, "total_tokens": 3},
                }
            )
        if request.path == "/v1/responses":
            previous = body.get("previous_response_id")
            if previous and self.owners.get(previous) != auth:
                return web.json_response(
                    {"error": {"message": "Wrong continuation owner", "code": "owner_mismatch"}}, status=403
                )
            response_id = "resp_fake_" + suffix
            self.owners[response_id] = auth
            payload = {
                "id": response_id,
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": model,
                "output": [
                    {
                        "id": "msg_" + suffix,
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "Hello", "annotations": []}],
                    }
                ],
                "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
            }
            if body.get("stream"):
                return await self.sse(
                    request,
                    [
                        {
                            "type": "response.created",
                            "sequence_number": 0,
                            "response": {**payload, "status": "in_progress"},
                        },
                        {
                            "type": "response.output_text.delta",
                            "sequence_number": 1,
                            "item_id": "msg_" + suffix,
                            "output_index": 0,
                            "content_index": 0,
                            "delta": "Hello",
                            "logprobs": [],
                        },
                        {"type": "response.completed", "sequence_number": 2, "response": payload},
                    ],
                )
            return web.json_response(payload)
        if request.path == "/v1/chat/completions":
            payload = {
                "id": "chatcmpl_" + suffix,
                "object": "chat.completion",
                "created": 0,
                "model": model,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "Hello"}, "finish_reason": "stop"}
                ],
                "usage": usage,
            }
            if body.get("stream"):
                chunk = {"id": payload["id"], "object": "chat.completion.chunk", "created": 0, "model": model}
                return await self.sse(
                    request,
                    [
                        {
                            **chunk,
                            "choices": [
                                {"index": 0, "delta": {"role": "assistant", "content": "Hello"}, "finish_reason": None}
                            ],
                        },
                        {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage},
                    ],
                    done=True,
                )
            return web.json_response(payload)
        if request.path == "/v1/completions":
            return web.json_response(
                {
                    "id": "cmpl_" + suffix,
                    "object": "text_completion",
                    "created": 0,
                    "model": model,
                    "choices": [{"text": "Hello", "index": 0, "finish_reason": "stop", "logprobs": None}],
                    "usage": usage,
                }
            )
        return web.json_response({"error": {"message": "Unsupported fake route", "code": "not_found"}}, status=404)

    async def sse(self, request, events, *, done=False):
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        for event in events:
            await response.write(b"data: " + json.dumps(event).encode() + b"\n\n")
            await asyncio.sleep(0)
        if done:
            await response.write(b"data: [DONE]\n\n")
        await response.write_eof()
        return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2467)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    web.run_app(FakeSwissAI().application(), host=args.host, port=args.port, access_log=None)
