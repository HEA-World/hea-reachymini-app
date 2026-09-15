"""Single-flight playback of allowlisted official Pollen recordings."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_mini.utils import create_head_pose

from .config import CUE_SET_VERSION
from .cue_contract import CueSelection
from .expression_catalog import OFFICIAL_EMOTIONS_DATASET, motion_move_by_cue
from .safe_logging import safe_log


class OfficialMoveLibraryError(RuntimeError):
    pass


MOTION_CADENCE_SENTENCES = 2

# Local semantic compression for the supervised demo: these source cues may
# reuse one of the four physically reviewed motion families. This never enables
# the source cue's own pending recording. Negative cues without a good match are
# intentionally absent and remain visual-only.
CADENCE_PROXY_CUE_BY_CUE = {
    "warm_smile": "warm_smile",
    "thinking": "thinking",
    "agree": "agree",
    "goodbye": "goodbye",
    "celebrate": "warm_smile",
    "explain": "thinking",
    "listen": "thinking",
    "caution": "thinking",
    "amazed": "warm_smile",
    "curious": "thinking",
    "confused": "thinking",
    "uncertain": "thinking",
    "laugh": "warm_smile",
    "grateful": "warm_smile",
    "helpful": "warm_smile",
    "proud": "warm_smile",
    "relieved": "warm_smile",
    "concerned": "thinking",
    "oops": "thinking",
    "calm": "thinking",
    "invite": "warm_smile",
}


@dataclass(frozen=True)
class MotionPlaybackResult:
    outcome: str
    motion_cue: str | None


class MotionExecutor:
    """Serialize official moves, enforce cooldowns, latch Stop, and neutralize."""

    def __init__(
        self,
        *,
        library_factory: Callable[[str], Any] = RecordedMoves,
        clock: Callable[[], float] = time.monotonic,
        global_cooldown_seconds: float = 0.5,
        per_cue_cooldown_seconds: float = 0.5,
        cadence_sentences: int = MOTION_CADENCE_SENTENCES,
        cue_set_version: str = CUE_SET_VERSION,
    ) -> None:
        self._library_factory = library_factory
        self._library: Any | None = None
        self._clock = clock
        self._global_cooldown_seconds = global_cooldown_seconds
        self._per_cue_cooldown_seconds = per_cue_cooldown_seconds
        self._cadence_sentences = max(1, int(cadence_sentences))
        self._move_by_cue = motion_move_by_cue(cue_set_version)
        self._required_official_moves = frozenset(self._move_by_cue.values())
        self._motion_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stopped = False
        self._active_robot: Any | None = None
        self._last_motion_at = float("-inf")
        self._last_cue_at: dict[str, float] = {}
        self._cadence_lock = threading.Lock()
        self._cadence_windows_moved: set[int] = set()

    def prepare(self) -> None:
        """Load the daemon-preloaded official dataset and verify our move allowlist."""
        try:
            library = self._library_factory(OFFICIAL_EMOTIONS_DATASET)
            available = set(library.list_moves())
            missing = sorted(self._required_official_moves - available)
            if missing:
                raise OfficialMoveLibraryError(f"official move library is missing: {', '.join(missing)}")
            self._library = library
        except OfficialMoveLibraryError:
            raise
        except Exception as error:
            raise OfficialMoveLibraryError("could not load the official Pollen emotions library") from error

    @property
    def stopped(self) -> bool:
        with self._state_lock:
            return self._stopped

    def stop(self) -> None:
        """Latch Stop and cancel an official move at the SDK's safe loop boundary."""
        with self._state_lock:
            self._stopped = True
            active_robot = self._active_robot
        if active_robot is not None:
            try:
                active_robot.cancel_move()
            except Exception:
                pass

    def resume(self) -> None:
        with self._state_lock:
            self._stopped = False

    def begin_turn(self) -> None:
        with self._cadence_lock:
            self._cadence_windows_moved.clear()

    def execute_cadenced(
        self,
        reachy_mini: object,
        selection: CueSelection,
        stop_event: object,
    ) -> MotionPlaybackResult:
        """Render at most one reviewed motion family per sentence window."""

        source_cue = selection.cue
        motion_cue = CADENCE_PROXY_CUE_BY_CUE.get(source_cue)
        if motion_cue is None:
            return MotionPlaybackResult("motion_disabled", None)
        if motion_cue not in self._move_by_cue:
            return MotionPlaybackResult("motion_proxy_unavailable", None)

        window = selection.sentence_index // self._cadence_sentences
        with self._cadence_lock:
            if window in self._cadence_windows_moved:
                return MotionPlaybackResult("cadence_limit", None)

            proxy_selection = CueSelection(
                cue=motion_cue,
                emoji=selection.emoji,
                message_id=selection.message_id,
                sentence_index=selection.sentence_index,
            )
            outcome = self.execute(reachy_mini, proxy_selection, stop_event)
            if outcome in {"completed", "stopped"}:
                self._cadence_windows_moved.add(window)
            rendered_cue = (
                motion_cue
                if outcome not in {"motion_disabled", "motion_proxy_unavailable"}
                else None
            )
            return MotionPlaybackResult(outcome, rendered_cue)

    def execute(self, reachy_mini: object, selection: CueSelection, stop_event: object) -> str:
        move_name = self._move_by_cue.get(selection.cue)
        if move_name is None:
            return "motion_disabled"
        if self._library is None:
            return "library_unavailable"

        with self._motion_lock:
            if self.stopped or stop_event.is_set():
                return "stopped"

            now = self._clock()
            if now - self._last_motion_at < self._global_cooldown_seconds:
                return "global_cooldown"
            if now - self._last_cue_at.get(selection.cue, float("-inf")) < self._per_cue_cooldown_seconds:
                return "cue_cooldown"

            with self._state_lock:
                self._active_robot = reachy_mini
            outcome = "completed"
            try:
                if self.stopped or stop_event.is_set():
                    outcome = "stopped"
                else:
                    move = self._library.get(move_name)
                    reachy_mini.play_move(
                        move,
                        initial_goto_duration=1.0,
                        sound=False,
                    )
                    outcome = "stopped" if self.stopped or stop_event.is_set() else "completed"
            finally:
                with self._state_lock:
                    self._active_robot = None
                neutral_ok = self.neutralize(reachy_mini)
                completed_at = self._clock()
                self._last_motion_at = completed_at
                self._last_cue_at[selection.cue] = completed_at
            return outcome if neutral_ok else "neutral_recovery_failed"

    @staticmethod
    def neutralize(reachy_mini: object) -> bool:
        """Attempt one fixed neutral pose without masking the prior motion result."""
        try:
            reachy_mini.goto_target(
                head=create_head_pose(),
                antennas=np.array([0.0, 0.0], dtype=float),
                duration=1.0,
                body_yaw=0.0,
            )
            return True
        except Exception as error:
            safe_log(
                "neutral_recovery_failed",
                name=type(error).__name__,
                code="neutral_recovery_failed",
                stage="neutralize",
            )
            return False
