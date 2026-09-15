import threading
import unittest

from pydantic import ValidationError

from hea_reachy_mini.app_state import AppStateStore
from hea_reachy_mini.cue_contract import CueGate
from hea_reachy_mini.main import CuePreviewJob, HeaReachyMini, PreviewCueRequest


class FakeMotion:
    def __init__(self, outcome="completed"):
        self.calls = []
        self.outcome = outcome

    def execute(self, robot, selection, stop_event):
        self.calls.append((robot, selection, stop_event.is_set()))
        return self.outcome


class LocalPreviewTests(unittest.TestCase):
    def make_app(self, *, motion_outcome="completed"):
        app = object.__new__(HeaReachyMini)
        app.state = AppStateStore()
        app.state.set_robot_ready(True)
        app.motion = FakeMotion(motion_outcome)
        app._turn_cancel = threading.Event()
        return app

    def test_preview_payload_defaults_motion_off_and_rejects_malformed_cues(self):
        request = PreviewCueRequest(cue="grateful")
        self.assertFalse(request.run_motion)
        with self.assertRaises(ValidationError):
            PreviewCueRequest(cue="welcoming2!")

    def test_each_queued_turn_gets_a_new_local_turn_id_and_clears_the_prior_answer(self):
        state = AppStateStore()
        state.set_robot_ready(True)

        first_turn_id = state.try_queue_turn()
        state.complete(answer="Previous answer", request_id="req-1")
        second_turn_id = state.try_queue_turn()

        self.assertEqual(first_turn_id, 1)
        self.assertEqual(second_turn_id, 2)
        self.assertEqual(state.snapshot()["turn_id"], 2)
        self.assertEqual(state.snapshot()["answer"], "")

    def test_visual_preview_never_calls_motion_executor(self):
        app = self.make_app()
        selection = CueGate().select_local_preview("grateful", "local-1")
        self.assertTrue(app.state.try_queue_preview())

        app._run_cue_preview(object(), threading.Event(), CuePreviewJob(selection, False))

        self.assertEqual(app.motion.calls, [])
        state = app.state.snapshot()
        self.assertFalse(state["busy"])
        self.assertEqual(state["cues"][0]["cue"], "grateful")
        self.assertEqual(state["cues"][0]["outcome"], "visual_preview")

    def test_armed_preview_uses_the_existing_motion_gate(self):
        app = self.make_app(motion_outcome="motion_disabled")
        selection = CueGate().select_local_preview("grateful", "local-2")
        robot = object()
        self.assertTrue(app.state.try_queue_preview())

        app._run_cue_preview(robot, threading.Event(), CuePreviewJob(selection, True))

        self.assertEqual(len(app.motion.calls), 1)
        self.assertIs(app.motion.calls[0][0], robot)
        self.assertEqual(app.motion.calls[0][1].cue, "grateful")
        self.assertFalse(app.motion.calls[0][2])
        self.assertEqual(app.state.snapshot()["cues"][0]["outcome"], "motion_disabled")


if __name__ == "__main__":
    unittest.main()
