import threading
import unittest
from types import SimpleNamespace

from hea_reachy_mini.app_state import AppStateStore
from hea_reachy_mini.cue_contract import CueGate
from hea_reachy_mini.main import AskRequest, HeaReachyMini, TurnJob
from hea_reachy_mini.motion_executor import MotionPlaybackResult
from hea_reachy_mini.speech_executor import SpeechError, SpeechPlaybackResult


class FakeClient:
    def __init__(self, events):
        self.events = events
        self.calls = []

    def ask(self, question, **kwargs):
        self.calls.append((question, kwargs))
        kwargs["on_delta"]("Visible answer.")
        for event in self.events:
            kwargs["on_sentence"](event)
        return SimpleNamespace(answer="Visible answer.", request_id="req-spoken")


class FakeMotion:
    def __init__(self):
        self.calls = []
        self.begin_calls = 0

    def begin_turn(self):
        self.begin_calls += 1

    def execute_cadenced(self, robot, selection, stop_event):
        self.calls.append((selection.cue, selection.sentence_index))
        motion_cue = "warm_smile" if selection.cue == "helpful" else selection.cue
        return MotionPlaybackResult("completed", motion_cue)


class FakeSpeech:
    def __init__(self, *, error=None):
        self.available = True
        self.error = error
        self.calls = []
        self.begin_calls = 0

    def begin_turn(self):
        self.begin_calls += 1

    def speak_with_motion(self, robot, text, stop_event, motion_callback, language=None):
        self.calls.append((text, language))
        if self.error is not None:
            raise self.error
        voices = {"nl": "Xander", "es": "Mónica", "en": "Daniel"}
        return SpeechPlaybackResult("spoken", motion_callback(), language, voices.get(language))


def sentence_event(index, text, cue=None, language=None):
    return {
        "type": "reachy_sentence_ready",
        "msg_id": "msg-spoken",
        "request_id": "req-spoken",
        "cue_set_version": "reachy_emoji",
        "sentence_index": index,
        "text": text,
        "language": language,
        "cue_item": {"cue": cue} if cue else None,
    }


class SpokenTurnTests(unittest.TestCase):
    def make_app(self, events, *, speech_error=None):
        app = object.__new__(HeaReachyMini)
        app.state = AppStateStore()
        app.state.set_robot_ready(True)
        app.state.set_speech_available(True)
        app.client = FakeClient(events)
        app.cue_gate = CueGate()
        app.motion = FakeMotion()
        app.speech = FakeSpeech(error=speech_error)
        app._turn_cancel = threading.Event()
        app._visitor_id = "visitor"
        app._session_id = "session"
        return app

    def test_spoken_output_defaults_on_for_a_turn_request(self):
        self.assertTrue(AskRequest(text="Hello Reachy.").speak)

    def test_every_sentence_is_spoken_even_without_an_expression(self):
        app = self.make_app(
            [
                sentence_event(0, "This sentence has no cue."),
                sentence_event(1, "Ik kan helpen.", "helpful", "nl"),
            ]
        )
        self.assertTrue(app.state.try_queue_turn())

        app._run_turn(object(), threading.Event(), TurnJob("Question", True))

        self.assertEqual(app.speech.calls, [("This sentence has no cue.", None), ("Ik kan helpen.", "nl")])
        self.assertEqual(app.motion.calls, [("helpful", 1)])
        self.assertEqual(app.motion.begin_calls, 1)
        sentences = app.state.snapshot()["cues"]
        self.assertIsNone(sentences[0]["cue"])
        self.assertEqual(sentences[0]["speech_outcome"], "spoken")
        self.assertEqual(sentences[0]["outcome"], "no_expression")
        self.assertEqual(sentences[1]["cue"], "helpful")
        self.assertEqual(sentences[1]["speech_outcome"], "spoken")
        self.assertEqual(sentences[1]["speech_language"], "nl")
        self.assertEqual(sentences[1]["speech_voice"], "Xander")
        self.assertEqual(sentences[1]["motion_cue"], "warm_smile")

    def test_speech_failure_keeps_visible_answer_and_motion_path(self):
        app = self.make_app(
            [sentence_event(0, "Hello.", "warm_smile")],
            speech_error=SpeechError("speech_synthesis_failed", "failed"),
        )
        self.assertTrue(app.state.try_queue_turn())

        app._run_turn(object(), threading.Event(), TurnJob("Question", True))

        snapshot = app.state.snapshot()
        self.assertEqual(snapshot["answer"], "Visible answer.")
        self.assertEqual(snapshot["status"], "complete")
        self.assertEqual(app.motion.calls, [("warm_smile", 0)])
        self.assertEqual(snapshot["cues"][0]["speech_outcome"], "speech_synthesis_failed")
        self.assertEqual(snapshot["speech"]["status"], "degraded")

    def test_operator_can_disable_speech_without_disabling_safe_motion(self):
        app = self.make_app([sentence_event(0, "Hello.", "warm_smile")])
        self.assertTrue(app.state.try_queue_turn())

        app._run_turn(object(), threading.Event(), TurnJob("Question", False))

        self.assertEqual(app.speech.calls, [])
        self.assertEqual(app.motion.calls, [("warm_smile", 0)])
        self.assertEqual(app.state.snapshot()["cues"][0]["speech_outcome"], "disabled")

    def test_turn_job_carries_the_selected_hea_and_fresh_conversation_identity(self):
        app = self.make_app([sentence_event(0, "Hello.")])
        self.assertTrue(app.state.try_queue_turn())

        app._run_turn(
            object(),
            threading.Event(),
            TurnJob(
                "Question",
                False,
                creator_id="owner-public",
                hea_id="public-hea",
                visitor_id="visitor-after-switch",
                session_id="session-after-switch",
            ),
        )

        kwargs = app.client.calls[0][1]
        self.assertEqual(kwargs["creator_id"], "owner-public")
        self.assertEqual(kwargs["hea_id"], "public-hea")
        self.assertEqual(kwargs["visitor_id"], "visitor-after-switch")
        self.assertEqual(kwargs["session_id"], "session-after-switch")

    def test_duplicate_sentence_event_is_not_spoken_twice(self):
        event = sentence_event(0, "Only once.", "warm_smile")
        app = self.make_app([event, dict(event)])
        self.assertTrue(app.state.try_queue_turn())

        app._run_turn(object(), threading.Event(), TurnJob("Question", True))

        self.assertEqual(app.speech.calls, [("Only once.", None)])
        self.assertEqual(app.motion.calls, [("warm_smile", 0)])
        self.assertEqual(len(app.state.snapshot()["cues"]), 1)

    def test_sdk_exception_after_stop_finishes_stopped_instead_of_local_app_error(self):
        app = self.make_app([sentence_event(0, "Stopping now.", "warm_smile")])

        class StopRaceMotion(FakeMotion):
            def execute_cadenced(self, robot, selection, stop_event):
                app._turn_cancel.set()
                raise AttributeError("SDK cancellation race")

        app.motion = StopRaceMotion()
        self.assertTrue(app.state.try_queue_turn())

        app._run_turn(object(), threading.Event(), TurnJob("Question", True))

        snapshot = app.state.snapshot()
        self.assertEqual(snapshot["status"], "stopped")
        self.assertTrue(snapshot["stopped"])
        self.assertIsNone(snapshot["error"])


if __name__ == "__main__":
    unittest.main()
