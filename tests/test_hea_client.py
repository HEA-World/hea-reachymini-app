import json
import pathlib
import threading
import unittest

import requests

from hea_reachy_mini.config import APP_VERSION, MAX_ANSWER_CHARS
from hea_reachy_mini.hea_client import HeaCancelled, HeaClient, HeaClientError, SseParser


FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, chunks=(), *, status=200, headers=None, json_body=None):
        self._chunks = chunks
        self.status_code = status
        self.headers = headers or {
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-HEA-Request-Id": "req-header",
        }
        self._json_body = json_body
        self.closed = False

    def iter_content(self, chunk_size=1024):
        del chunk_size
        chunks = self._chunks() if callable(self._chunks) else self._chunks
        yield from chunks

    def json(self):
        return self._json_body

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def sse(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


class SseParserTests(unittest.TestCase):
    def test_fragmented_utf8_and_crlf(self):
        raw = 'data: {"type":"x","emoji":"😊"}\r\n\r\n'.encode()
        parser = SseParser()
        events = []
        for byte in raw:
            events.extend(parser.feed(bytes([byte])))
        events.extend(parser.finish())
        self.assertEqual(events, [{"type": "x", "emoji": "😊"}])

    def test_malformed_and_oversized_frames_fail_closed(self):
        with self.assertRaisesRegex(HeaClientError, "malformed"):
            SseParser().feed(b"data: {nope}\n\n")
        with self.assertRaisesRegex(HeaClientError, "safety limit"):
            SseParser(max_frame_bytes=8).feed(b"data: 123456789")


class HeaClientTests(unittest.TestCase):
    def _ask(self, response, **callbacks):
        session = FakeSession(response)
        result = HeaClient(endpoint="https://example.invalid/chat", session=session).ask(
            "Hello",
            visitor_id="visitor-test",
            session_id="session-test",
            cancel_event=threading.Event(),
            **callbacks,
        )
        return result, session

    def test_fixture_stream_is_fragment_safe_and_payload_is_bounded(self):
        raw = (FIXTURES / "normal.sse").read_bytes()
        chunks = [raw[index : index + 7] for index in range(0, len(raw), 7)]
        deltas = []
        sentences = []
        result, session = self._ask(
            FakeResponse(chunks),
            on_delta=deltas.append,
            on_sentence=sentences.append,
        )
        self.assertEqual(result.answer, "Hello Reachy.")
        self.assertEqual(result.request_id, "reachy_req_1")
        self.assertEqual(result.sentence_count, 1)
        self.assertEqual(deltas, ["Hello ", "Reachy."])
        self.assertEqual(sentences[0]["cue_item"]["cue"], "warm_smile")

        sent = session.calls[0][1]["json"]
        self.assertEqual(sent["creator_id"], "hea-world")
        self.assertEqual(sent["hea_id"], "heaguide-web-001")
        self.assertTrue(sent["reachy_sentence_sync"])
        self.assertEqual(sent["cue_set_version"], "reachy_emoji")
        self.assertEqual(
            session.calls[0][1]["headers"]["User-Agent"],
            f"hea-reachy-mini-lite/{APP_VERSION}",
        )

    def test_v2_remains_an_explicit_legacy_compatible_client_choice(self):
        session = FakeSession(FakeResponse([sse({"type": "reachy_done"})]))
        HeaClient(
            endpoint="https://example.invalid/chat",
            session=session,
            cue_set_version="reachy_emoji_v2",
        ).ask(
            "Hello",
            visitor_id="visitor-v2",
            session_id="session-v2",
            cancel_event=threading.Event(),
        )
        self.assertEqual(session.calls[0][1]["json"]["cue_set_version"], "reachy_emoji_v2")

    def test_selected_public_identity_is_sent_instead_of_the_default(self):
        session = FakeSession(FakeResponse([sse({"type": "reachy_done"})]))
        HeaClient(endpoint="https://example.invalid/chat", session=session).ask(
            "Hello",
            visitor_id="visitor-public",
            session_id="session-public",
            creator_id="owner-public",
            hea_id="public-hea",
            cancel_event=threading.Event(),
        )
        sent = session.calls[0][1]["json"]
        self.assertEqual(sent["creator_id"], "owner-public")
        self.assertEqual(sent["hea_id"], "public-hea")

    def test_structured_http_error(self):
        response = FakeResponse(
            status=403,
            headers={"Content-Type": "application/json"},
            json_body={"code": "reachy_install_disabled", "requestId": "req-403"},
        )
        with self.assertRaises(HeaClientError) as caught:
            self._ask(response)
        self.assertEqual(caught.exception.code, "reachy_install_disabled")
        self.assertEqual(caught.exception.http, 403)
        self.assertEqual(caught.exception.request_id, "req-403")

    def test_planner_failure_keeps_text_and_enqueues_no_sentence(self):
        chunks = [
            sse({"choices": [{"delta": {"content": "Text only."}}]}),
            sse({"type": "reachy_cue_plan_failed", "code": "planner_timeout"}),
            sse({"type": "reachy_done", "request_id": "req-1"}),
        ]
        sentences = []
        result, _ = self._ask(FakeResponse(chunks), on_sentence=sentences.append)
        self.assertEqual(result.answer, "Text only.")
        self.assertEqual(result.planner_failures, ("planner_timeout",))
        self.assertEqual(sentences, [])

    def test_unknown_event_is_ignored(self):
        result, _ = self._ask(
            FakeResponse(
                [
                    sse({"type": "future_robot_command", "pose": [1, 2, 3]}),
                    sse({"type": "reachy_done"}),
                ]
            )
        )
        self.assertEqual(result.ignored_event_types, ("future_robot_command",))

    def test_clean_disconnect_before_done_is_an_error(self):
        with self.assertRaises(HeaClientError) as caught:
            self._ask(FakeResponse([sse({"choices": [{"delta": {"content": "partial"}}]})]))
        self.assertEqual(caught.exception.code, "incomplete_stream")

    def test_network_disconnect_is_structured(self):
        def chunks():
            yield sse({"choices": [{"delta": {"content": "partial"}}]})
            raise requests.exceptions.ChunkedEncodingError("disconnect")

        with self.assertRaises(HeaClientError) as caught:
            self._ask(FakeResponse(chunks))
        self.assertEqual(caught.exception.code, "hea_network_error")

    def test_cancellation_closes_active_response(self):
        cancel = threading.Event()

        def chunks():
            cancel.set()
            yield sse({"type": "reachy_done"})

        response = FakeResponse(chunks)
        client = HeaClient(endpoint="https://example.invalid/chat", session=FakeSession(response))
        with self.assertRaises(HeaCancelled):
            client.ask(
                "Hello",
                visitor_id="v",
                session_id="s",
                cancel_event=cancel,
            )
        self.assertTrue(response.closed)

    def test_answer_limit(self):
        huge = "x" * (MAX_ANSWER_CHARS + 1)
        with self.assertRaises(HeaClientError) as caught:
            self._ask(FakeResponse([sse({"choices": [{"delta": {"content": huge}}]})]))
        self.assertEqual(caught.exception.code, "answer_too_large")


if __name__ == "__main__":
    unittest.main()
