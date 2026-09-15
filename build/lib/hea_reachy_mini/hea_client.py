"""Bounded, cancellable client for the HEA Reachy SSE endpoint."""

from __future__ import annotations

import codecs
import json
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import requests

from .config import (
    APP_VERSION,
    CUE_SET_VERSION,
    HEA_BEHAVIOR_CATALOG_ID,
    HEA_CREATOR_ID,
    HEA_ENDPOINT,
    HEA_ID,
    MAX_ANSWER_CHARS,
    MAX_SENTENCES,
    MAX_SSE_EVENTS,
    MAX_SSE_FRAME_BYTES,
    MAX_TURN_SECONDS,
    MAX_USER_INPUT_CHARS,
)
from .expression_catalog import SUPPORTED_CUE_SET_VERSIONS


class HeaClientError(RuntimeError):
    """Structured endpoint or stream failure safe to expose in the local UI."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http = http
        self.request_id = request_id


class HeaCancelled(HeaClientError):
    def __init__(self) -> None:
        super().__init__("cancelled", "Stopped by operator")


class SseParser:
    """Incremental UTF-8 SSE parser with a hard per-frame size cap."""

    _separator = re.compile(r"\r?\n\r?\n")

    def __init__(self, max_frame_bytes: int = MAX_SSE_FRAME_BYTES) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        self._buffer = ""
        self._max_frame_bytes = max_frame_bytes

    def feed(self, chunk: bytes | str) -> list[dict[str, Any]]:
        if isinstance(chunk, bytes):
            self._buffer += self._decoder.decode(chunk)
        else:
            self._buffer += str(chunk)
        return self._drain()

    def finish(self) -> list[dict[str, Any]]:
        self._buffer += self._decoder.decode(b"", final=True)
        events = self._drain()
        if self._buffer.strip():
            events.extend(self._parse_frame(self._buffer))
        self._buffer = ""
        return events

    def _drain(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while True:
            match = self._separator.search(self._buffer)
            if match is None:
                if len(self._buffer.encode("utf-8")) > self._max_frame_bytes:
                    raise HeaClientError("sse_frame_too_large", "HEA response frame exceeded the safety limit")
                return events
            frame = self._buffer[: match.start()]
            self._buffer = self._buffer[match.end() :]
            events.extend(self._parse_frame(frame))

    def _parse_frame(self, frame: str) -> list[dict[str, Any]]:
        if len(frame.encode("utf-8")) > self._max_frame_bytes:
            raise HeaClientError("sse_frame_too_large", "HEA response frame exceeded the safety limit")

        data_lines: list[str] = []
        for raw_line in frame.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if not raw_line or raw_line.startswith(":"):
                continue
            if raw_line.startswith("data:"):
                data_lines.append(raw_line[5:].lstrip(" "))
        if not data_lines:
            return []

        data = "\n".join(data_lines)
        if data == "[DONE]":
            return []
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as error:
            raise HeaClientError("malformed_sse_json", "HEA returned malformed streaming data") from error
        return [payload] if isinstance(payload, dict) else []


@dataclass(frozen=True)
class HeaTurnResult:
    answer: str
    request_id: str | None
    sentence_count: int
    planner_failures: tuple[str, ...]
    ignored_event_types: tuple[str, ...]


class HeaClient:
    def __init__(
        self,
        *,
        endpoint: str = HEA_ENDPOINT,
        session: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
        cue_set_version: str = CUE_SET_VERSION,
    ) -> None:
        if cue_set_version not in SUPPORTED_CUE_SET_VERSIONS:
            raise ValueError(f"unsupported cue set version: {cue_set_version}")
        self.endpoint = endpoint
        self._session = session or requests.Session()
        self._clock = clock
        self._cue_set_version = cue_set_version
        self._active_response: Any | None = None
        self._response_lock = threading.Lock()

    def cancel(self) -> None:
        with self._response_lock:
            response = self._active_response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def ask(
        self,
        question: str,
        *,
        visitor_id: str,
        session_id: str,
        creator_id: str = HEA_CREATOR_ID,
        hea_id: str = HEA_ID,
        cancel_event: threading.Event,
        on_delta: Callable[[str], None] | None = None,
        on_sentence: Callable[[dict[str, Any]], None] | None = None,
    ) -> HeaTurnResult:
        question = str(question or "").strip()
        if not question:
            raise HeaClientError("missing_user_input", "Enter a question first", http=400)
        if len(question) > MAX_USER_INPUT_CHARS:
            raise HeaClientError("user_input_too_large", "Question exceeds the 6,000 character limit", http=413)
        if cancel_event.is_set():
            raise HeaCancelled()

        body = {
            "creator_id": creator_id,
            "hea_id": hea_id,
            "visitorID": visitor_id,
            "visitor_id": visitor_id,
            "session_id": session_id,
            "message": question,
            "user_text": question,
            "channel": "reachy_mini",
            "reachy_cue_session": True,
            "reachy_sentence_sync": True,
            "cue_set_version": self._cue_set_version,
            "behavior_catalog_id": HEA_BEHAVIOR_CATALOG_ID,
            "client_msg_id": f"reachy_lite_{uuid.uuid4().hex}",
        }
        started_at = self._clock()
        response: Any | None = None
        try:
            response = self._session.post(
                self.endpoint,
                json=body,
                headers={
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                    "User-Agent": f"hea-reachy-mini-lite/{APP_VERSION}",
                },
                stream=True,
                timeout=(5.0, 15.0),
            )
            with self._response_lock:
                self._active_response = response

            request_id = self._response_request_id(response)
            if cancel_event.is_set():
                raise HeaCancelled()
            if int(response.status_code) != 200:
                raise self._http_error(response, request_id)

            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "text/event-stream" not in content_type:
                raise HeaClientError(
                    "unexpected_content_type",
                    "HEA endpoint did not return an event stream",
                    http=int(response.status_code),
                    request_id=request_id,
                )

            parser = SseParser()
            answer_parts: list[str] = []
            answer_chars = 0
            sentence_count = 0
            event_count = 0
            saw_done = False
            planner_failures: list[str] = []
            ignored_event_types: set[str] = set()

            def consume(events: Iterable[dict[str, Any]]) -> None:
                nonlocal answer_chars, event_count, saw_done, sentence_count, request_id
                for event in events:
                    event_count += 1
                    if event_count > MAX_SSE_EVENTS:
                        raise HeaClientError("too_many_sse_events", "HEA response exceeded the event limit")
                    if cancel_event.is_set():
                        raise HeaCancelled()
                    if self._clock() - started_at > MAX_TURN_SECONDS:
                        raise HeaClientError("turn_timeout", "HEA turn exceeded 90 seconds")

                    request_id = str(event.get("request_id") or request_id or "") or None
                    delta = self._assistant_delta(event)
                    if delta:
                        answer_chars += len(delta)
                        if answer_chars > MAX_ANSWER_CHARS:
                            raise HeaClientError("answer_too_large", "HEA answer exceeded the safety limit")
                        answer_parts.append(delta)
                        if on_delta is not None:
                            on_delta(delta)
                        continue

                    event_type = str(event.get("type") or "")
                    if event_type == "reachy_sentence_ready":
                        if sentence_count < MAX_SENTENCES:
                            sentence_count += 1
                            if on_sentence is not None:
                                on_sentence(event)
                        continue
                    if event_type == "reachy_cue_plan_failed":
                        planner_failures.append(str(event.get("code") or "reachy_cue_planner_failed"))
                        continue
                    if event_type == "reachy_done":
                        saw_done = True
                        continue
                    if event_type in {"error", "chat_error"}:
                        code = str(event.get("code") or event.get("error") or "hea_stream_error")
                        raise HeaClientError(code, "HEA reported a streaming error", request_id=request_id)
                    if event_type and event_type not in {"assistant_meta", "reachy_cue_plan"}:
                        ignored_event_types.add(event_type)

            for chunk in response.iter_content(chunk_size=1024):
                if cancel_event.is_set():
                    raise HeaCancelled()
                if chunk:
                    consume(parser.feed(chunk))
            consume(parser.finish())

            if cancel_event.is_set():
                raise HeaCancelled()
            if not saw_done:
                raise HeaClientError("incomplete_stream", "HEA stream ended before reachy_done", request_id=request_id)

            return HeaTurnResult(
                answer="".join(answer_parts).strip(),
                request_id=request_id,
                sentence_count=sentence_count,
                planner_failures=tuple(planner_failures),
                ignored_event_types=tuple(sorted(ignored_event_types)),
            )
        except HeaClientError:
            raise
        except requests.RequestException as error:
            if cancel_event.is_set():
                raise HeaCancelled() from error
            raise HeaClientError("hea_network_error", "Could not reach HEA-World") from error
        finally:
            with self._response_lock:
                if self._active_response is response:
                    self._active_response = None
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

    @staticmethod
    def _assistant_delta(event: dict[str, Any]) -> str:
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return ""
        delta = choices[0].get("delta")
        if not isinstance(delta, dict):
            return ""
        content = delta.get("content")
        return content if isinstance(content, str) else ""

    @staticmethod
    def _response_request_id(response: Any) -> str | None:
        value = response.headers.get("X-HEA-Request-Id")
        return str(value).strip() if value else None

    @staticmethod
    def _http_error(response: Any, request_id: str | None) -> HeaClientError:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        code = str(payload.get("code") or payload.get("error") or "hea_http_error")
        resolved_request_id = str(payload.get("requestId") or request_id or "") or None
        return HeaClientError(
            code,
            f"HEA request failed ({int(response.status_code)})",
            http=int(response.status_code),
            request_id=resolved_request_id,
        )
