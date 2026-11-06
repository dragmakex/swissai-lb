"""Bounded metadata-only inspection; model output bytes are never rewritten."""

import json

from app.modules.swissai.policy import usage_from

MAX_FRAME_BYTES = 1024 * 1024
MAX_IDENTIFIERS = 16
_TERMINAL_RESPONSE_EVENTS = {"response.completed", "response.failed", "response.incomplete"}
_TERMINAL_RESPONSE_STATES = {"completed", "failed", "incomplete"}


class ObservationError(ValueError):
    pass


def _has_model_output(payload: dict, responses: bool) -> bool:
    if responses:
        kind, delta = payload.get("type"), payload.get("delta")
        return (
            isinstance(kind, str)
            and kind.startswith("response.")
            and kind.endswith(".delta")
            and isinstance(delta, str)
            and bool(delta)
        )
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        fragments = [choice.get("text")]
        delta = choice.get("delta")
        if isinstance(delta, dict):
            fragments.extend(delta.get(field) for field in ("content", "reasoning_content"))
            functions = [delta.get("function_call")]
            tools = delta.get("tool_calls")
            if isinstance(tools, list):
                functions.extend(tool.get("function") for tool in tools if isinstance(tool, dict))
            for function in functions:
                if isinstance(function, dict):
                    fragments.extend(function.get(field) for field in ("name", "arguments"))
        if any(isinstance(fragment, str) and fragment for fragment in fragments):
            return True
    return False


class Observations:
    def __init__(self, responses: bool) -> None:
        self.responses = responses
        self.usage: dict[str, int | None] = {}
        self.identifiers: set[str] = set()
        self.has_output = False
        self.failed = False
        self.buffer = b""
        self.data_lines: list[bytes] = []
        self.frame_size = 0

    def inspect(self, payload: dict, *, terminal: bool = True) -> None:
        response = payload.get("response")
        obj = response if isinstance(response, dict) else payload
        state = obj.get("status")
        if self.responses and isinstance(state, str) and state in {"queued", "in_progress"}:
            terminal = False
        if terminal:
            self.usage = usage_from(payload)
            self.failed = self.failed or (
                self.responses and (state == "failed" or payload.get("type") == "response.failed")
            )
        self.has_output = self.has_output or _has_model_output(payload, self.responses)
        if not self.responses:
            return
        for field in ("id", "conversation", "conversation_id"):
            value = obj.get(field)
            if isinstance(value, dict):
                value = value.get("id")
            if isinstance(value, str) and 0 < len(value) <= 512:
                if "sk-rc-" in value:
                    raise ObservationError("Credential-like upstream identifier was refused")
                if value not in self.identifiers and len(self.identifiers) >= MAX_IDENTIFIERS:
                    raise ObservationError("Too many upstream ownership identifiers")
                self.identifiers.add(value)

    def feed(self, chunk: bytes) -> None:
        self.buffer += chunk
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            self._line(line.rstrip(b"\r"))
        if len(self.buffer) + self.frame_size > MAX_FRAME_BYTES:
            raise ObservationError("SwissAI SSE frame exceeded 1 MiB")

    def _line(self, line: bytes) -> None:
        if not line:
            if self.data_lines:
                self._parse(b"\n".join(self.data_lines))
            self.data_lines.clear()
            self.frame_size = 0
            return
        self.frame_size += len(line) + 1
        if self.frame_size > MAX_FRAME_BYTES:
            raise ObservationError("SwissAI SSE frame exceeded 1 MiB")
        if line.startswith(b"data:"):
            self.data_lines.append(line[5:].lstrip(b" "))

    def _parse(self, raw: bytes) -> None:
        if raw == b"[DONE]":
            return
        try:
            obj = json.loads(raw)
        except (ValueError, UnicodeError):
            return
        if not isinstance(obj, dict):
            return
        if self.responses:
            response = obj.get("response")
            state = response.get("status") if isinstance(response, dict) else obj.get("status")
            kind = obj.get("type")
            terminal = (isinstance(kind, str) and kind in _TERMINAL_RESPONSE_EVENTS) or (
                isinstance(state, str) and state in _TERMINAL_RESPONSE_STATES
            )
        else:
            choices = obj.get("choices")
            terminal = isinstance(choices, list) and (
                not choices
                or all(
                    isinstance(choice, dict)
                    and isinstance(choice.get("finish_reason"), str)
                    and choice["finish_reason"]
                    for choice in choices
                )
            )
        self.inspect(obj, terminal=bool(terminal))

    def close(self) -> None:
        if self.buffer:
            self._line(self.buffer.rstrip(b"\r"))
            self.buffer = b""
        self._line(b"")
