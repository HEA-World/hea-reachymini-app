import io
import json
import unittest
from contextlib import redirect_stdout

from hea_reachy_mini.app_state import AppStateStore
from hea_reachy_mini.safe_logging import safe_log


class DiagnosticsTests(unittest.TestCase):
    def test_export_excludes_conversation_audio_and_session_data(self) -> None:
        state = AppStateStore()
        state.select_hea(
            {
                "creator_id": "public-creator",
                "hea_id": "public-hea",
                "name": "Public HEA",
                "avatar_url": "https://example.com/avatar.png",
                "beta": True,
            }
        )
        state.append_answer("ANSWER_SECRET_74A")
        state.record_sentence(
            "thinking",
            "🤔",
            0,
            "completed",
            "spoken",
            "SENTENCE_SECRET_93B",
            "nl",
            "Xander",
            "thinking",
        )
        state.fail(code="local_app_error", message="RAW_EXCEPTION_SECRET_18C", request_id="req-safe-1")

        payload = state.diagnostics_snapshot()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["app_version"], "0.6.0")
        self.assertEqual(payload["selected_public_hea"]["hea_id"], "public-hea")
        self.assertEqual(payload["recent_sentence_outcomes"][0]["speech_language"], "nl")
        self.assertNotIn("ANSWER_SECRET_74A", serialized)
        self.assertNotIn("SENTENCE_SECRET_93B", serialized)
        self.assertNotIn("RAW_EXCEPTION_SECRET_18C", serialized)
        self.assertNotIn("avatar.png", serialized)
        self.assertIn("visitor_id", payload["excluded"])
        self.assertIn("session_id", payload["excluded"])

    def test_safe_log_is_json_and_sanitizes_untrusted_identifiers(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            safe_log(
                "turn_failed",
                code="network_error",
                requestId="not safe user-like text",
                sentenceIndex=2,
                http=503,
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["appVersion"], "0.6.0")
        self.assertEqual(payload["requestId"], "invalid_identifier")
        self.assertEqual(payload["http"], 503)
        self.assertEqual(payload["sentenceIndex"], 2)


if __name__ == "__main__":
    unittest.main()
