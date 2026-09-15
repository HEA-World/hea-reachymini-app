import threading
import time
import unittest

from hea_reachy_mini.cue_contract import CueSelection
from hea_reachy_mini.motion_executor import (
    CADENCE_PROXY_CUE_BY_CUE,
    MotionExecutor,
    OfficialMoveLibraryError,
)
from hea_reachy_mini.official_moves import OFFICIAL_EMOTIONS_DATASET, OFFICIAL_MOVE_BY_CUE


class FakeMove:
    def __init__(self, name):
        self.name = name


class FakeLibrary:
    def __init__(self, dataset, *, missing=()):
        self.dataset = dataset
        self.missing = set(missing)
        self.requested = []

    def list_moves(self):
        return list(set(OFFICIAL_MOVE_BY_CUE.values()) - self.missing)

    def get(self, name):
        self.requested.append(name)
        return FakeMove(name)


class FakeRobot:
    def __init__(self):
        self.play_calls = []
        self.goto_calls = []
        self.cancel_calls = 0

    def play_move(self, move, **kwargs):
        self.play_calls.append((move, kwargs))

    def goto_target(self, **kwargs):
        self.goto_calls.append(kwargs)

    def cancel_move(self):
        self.cancel_calls += 1


def selection(cue, index=0):
    return CueSelection(cue=cue, emoji="🙂", message_id=f"m-{cue}", sentence_index=index)


class MotionExecutorTests(unittest.TestCase):
    def make_executor(self, **kwargs):
        libraries = []

        def factory(dataset):
            library = FakeLibrary(dataset)
            libraries.append(library)
            return library

        executor = MotionExecutor(library_factory=factory, **kwargs)
        executor.prepare()
        return executor, libraries[0]

    def test_uses_only_official_dataset_move_names_without_sound(self):
        executor, library = self.make_executor(global_cooldown_seconds=0, per_cue_cooldown_seconds=0)
        robot = FakeRobot()
        for cue, expected_move in OFFICIAL_MOVE_BY_CUE.items():
            outcome = executor.execute(robot, selection(cue), threading.Event())
            self.assertEqual(outcome, "completed")
            self.assertEqual(robot.play_calls[-1][0].name, expected_move)
            self.assertEqual(robot.play_calls[-1][1], {"initial_goto_duration": 1.0, "sound": False})
        self.assertEqual(library.dataset, OFFICIAL_EMOTIONS_DATASET)
        self.assertEqual(library.requested, list(OFFICIAL_MOVE_BY_CUE.values()))

    def test_missing_official_move_fails_preflight(self):
        executor = MotionExecutor(library_factory=lambda dataset: FakeLibrary(dataset, missing={"loving1"}))
        with self.assertRaises(OfficialMoveLibraryError):
            executor.prepare()

    def test_cooldown_and_unsupported_selection_do_not_play(self):
        now = [10.0]
        executor, _ = self.make_executor(clock=lambda: now[0])
        robot = FakeRobot()
        self.assertEqual(executor.execute(robot, selection("agree"), threading.Event()), "completed")
        self.assertEqual(executor.execute(robot, selection("agree"), threading.Event()), "global_cooldown")
        self.assertEqual(executor.execute(robot, selection("celebrate"), threading.Event()), "motion_disabled")
        self.assertEqual(len(robot.play_calls), 1)

    def test_cadence_uses_one_reviewed_motion_family_per_two_sentences(self):
        executor, library = self.make_executor(
            global_cooldown_seconds=0,
            per_cue_cooldown_seconds=0,
        )
        executor.begin_turn()
        robot = FakeRobot()

        first = executor.execute_cadenced(robot, selection("helpful", 0), threading.Event())
        same_window = executor.execute_cadenced(robot, selection("thinking", 1), threading.Event())
        next_window = executor.execute_cadenced(robot, selection("agree", 2), threading.Event())

        self.assertEqual((first.outcome, first.motion_cue), ("completed", "warm_smile"))
        self.assertEqual((same_window.outcome, same_window.motion_cue), ("cadence_limit", None))
        self.assertEqual((next_window.outcome, next_window.motion_cue), ("completed", "agree"))
        self.assertEqual(library.requested, ["welcoming2", "understanding2"])

    def test_unmatched_negative_cue_leaves_its_cadence_window_available(self):
        executor, library = self.make_executor(
            global_cooldown_seconds=0,
            per_cue_cooldown_seconds=0,
        )
        executor.begin_turn()
        robot = FakeRobot()

        negative = executor.execute_cadenced(robot, selection("sad", 0), threading.Event())
        positive = executor.execute_cadenced(robot, selection("grateful", 1), threading.Event())

        self.assertEqual((negative.outcome, negative.motion_cue), ("motion_disabled", None))
        self.assertEqual((positive.outcome, positive.motion_cue), ("completed", "warm_smile"))
        self.assertEqual(library.requested, ["welcoming2"])

    def test_cadence_proxies_can_only_target_the_four_reviewed_cues(self):
        self.assertTrue(set(CADENCE_PROXY_CUE_BY_CUE.values()).issubset(OFFICIAL_MOVE_BY_CUE))
        self.assertTrue({"sad", "frustrated", "disagree"}.isdisjoint(CADENCE_PROXY_CUE_BY_CUE))

    def test_stop_cancels_active_sdk_move_then_neutralizes(self):
        executor, _ = self.make_executor(global_cooldown_seconds=0, per_cue_cooldown_seconds=0)
        started = threading.Event()
        released = threading.Event()

        class BlockingRobot(FakeRobot):
            def play_move(self, move, **kwargs):
                super().play_move(move, **kwargs)
                started.set()
                released.wait(timeout=2)

            def cancel_move(self):
                super().cancel_move()
                released.set()

        robot = BlockingRobot()
        outcomes = []
        thread = threading.Thread(
            target=lambda: outcomes.append(executor.execute(robot, selection("thinking"), threading.Event()))
        )
        thread.start()
        self.assertTrue(started.wait(timeout=1))
        executor.stop()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(robot.cancel_calls, 1)
        self.assertEqual(outcomes, ["stopped"])
        self.assertEqual(len(robot.goto_calls), 1)

    def test_playback_is_serialized(self):
        executor, _ = self.make_executor(global_cooldown_seconds=0, per_cue_cooldown_seconds=0)

        class CountingRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.active = 0
                self.max_active = 0
                self.lock = threading.Lock()

            def play_move(self, move, **kwargs):
                with self.lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                time.sleep(0.03)
                with self.lock:
                    self.active -= 1

        robot = CountingRobot()
        threads = [
            threading.Thread(target=executor.execute, args=(robot, selection(cue), threading.Event()))
            for cue in ("agree", "thinking")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=1)
        self.assertEqual(robot.max_active, 1)
        self.assertEqual(len(robot.play_calls), 0)  # CountingRobot intentionally records only concurrency.

    def test_neutral_return_runs_after_playback_error(self):
        executor, _ = self.make_executor(global_cooldown_seconds=0, per_cue_cooldown_seconds=0)

        class ErrorRobot(FakeRobot):
            def play_move(self, move, **kwargs):
                raise RuntimeError("motor transport")

        robot = ErrorRobot()
        with self.assertRaisesRegex(RuntimeError, "motor transport"):
            executor.execute(robot, selection("warm_smile"), threading.Event())
        self.assertEqual(len(robot.goto_calls), 1)

    def test_neutral_failure_is_reported_without_becoming_a_local_app_exception(self):
        executor, _ = self.make_executor(global_cooldown_seconds=0, per_cue_cooldown_seconds=0)

        class NeutralErrorRobot(FakeRobot):
            def goto_target(self, **kwargs):
                super().goto_target(**kwargs)
                raise AttributeError("neutral transport closed")

        robot = NeutralErrorRobot()
        outcome = executor.execute(robot, selection("warm_smile"), threading.Event())

        self.assertEqual(outcome, "neutral_recovery_failed")
        self.assertEqual(len(robot.goto_calls), 1)

    def test_neutral_failure_does_not_replace_the_original_playback_error(self):
        executor, _ = self.make_executor(global_cooldown_seconds=0, per_cue_cooldown_seconds=0)

        class PlaybackAndNeutralErrorRobot(FakeRobot):
            def play_move(self, move, **kwargs):
                raise RuntimeError("motor transport")

            def goto_target(self, **kwargs):
                super().goto_target(**kwargs)
                raise AttributeError("neutral transport closed")

        robot = PlaybackAndNeutralErrorRobot()
        with self.assertRaisesRegex(RuntimeError, "motor transport"):
            executor.execute(robot, selection("warm_smile"), threading.Event())
        self.assertEqual(len(robot.goto_calls), 1)


if __name__ == "__main__":
    unittest.main()
