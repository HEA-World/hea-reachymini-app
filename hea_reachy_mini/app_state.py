"""Thread-safe local UI state. User text is never written to logs."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from .config import APP_VERSION, CUE_CATALOG_ID
from .expression_catalog import cue_definitions


class AppStateStore:
    def __init__(self) -> None:
        definitions = cue_definitions(CUE_CATALOG_ID)
        cue_catalog = [
            {
                "cue": cue,
                "emoji": definition["emoji"],
                "label": cue.replace("_", " ").title(),
                "description": definition["description"],
                "motion_enabled": definition["motion_enabled"],
            }
            for cue, definition in definitions.items()
        ]
        motion_allowlist = [
            {"cue": item["cue"], "emoji": item["emoji"], "label": item["label"]}
            for item in cue_catalog
            if item["motion_enabled"]
        ]
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "version": APP_VERSION,
            "cue_catalog_id": CUE_CATALOG_ID,
            "hea_id": "",
            "selected_hea": {
                "creator_id": "",
                "hea_id": "",
                "name": "Choose a public HEA",
                "avatar_url": "",
                "beta": False,
            },
            "directory": {
                "status": "not_loaded",
                "count": 0,
                "error": None,
            },
            "robot_ready": False,
            "hea_status": "not_checked",
            "status": "starting",
            "busy": False,
            "stopped": False,
            "turn_id": 0,
            "answer": "",
            "cues": [],
            "cue_catalog": cue_catalog,
            "motion_allowlist": motion_allowlist,
            "speech": {
                "available": False,
                "engine": "macos_say_offline",
                "status": "not_checked",
                "language": None,
                "voice": None,
                "error": None,
            },
            "error": None,
            "request_id": None,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self._state,
                "cues": list(self._state["cues"]),
                "cue_catalog": [dict(item) for item in self._state["cue_catalog"]],
                "motion_allowlist": [dict(item) for item in self._state["motion_allowlist"]],
                "speech": dict(self._state["speech"]),
                "selected_hea": dict(self._state["selected_hea"]),
                "directory": dict(self._state["directory"]),
            }

    def diagnostics_snapshot(self) -> dict[str, Any]:
        """Return a reviewable support payload with conversation data excluded."""
        snapshot = self.snapshot()
        selected = snapshot["selected_hea"]
        error = snapshot.get("error") or {}
        recent_outcomes = [
            {
                "cue": item.get("cue"),
                "sentence_index": item.get("sentence_index"),
                "motion_outcome": item.get("outcome"),
                "motion_cue": item.get("motion_cue"),
                "speech_outcome": item.get("speech_outcome"),
                "speech_language": item.get("speech_language"),
                "speech_voice": item.get("speech_voice"),
            }
            for item in snapshot["cues"]
        ]
        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "app": "hea_reachy_mini",
            "app_version": snapshot["version"],
            "cue_catalog_id": snapshot["cue_catalog_id"],
            "status": snapshot["status"],
            "busy": snapshot["busy"],
            "stopped": snapshot["stopped"],
            "robot_ready": snapshot["robot_ready"],
            "hea_status": snapshot["hea_status"],
            "directory": {
                "status": snapshot["directory"].get("status"),
                "count": snapshot["directory"].get("count"),
                "error_code": snapshot["directory"].get("error"),
            },
            "selected_public_hea": {
                "creator_id": selected.get("creator_id"),
                "hea_id": selected.get("hea_id"),
                "name": selected.get("name"),
                "beta": selected.get("beta") is True,
            },
            "speech": snapshot["speech"],
            "error": {
                "code": error.get("code"),
                "request_id": snapshot.get("request_id"),
            },
            "recent_sentence_outcomes": recent_outcomes,
            "excluded": [
                "question",
                "answer",
                "sentence_text",
                "audio",
                "visitor_id",
                "session_id",
                "raw_exception",
            ],
        }

    def set_directory_status(self, status: str, *, count: int = 0, error: str | None = None) -> None:
        with self._lock:
            self._state["directory"].update(status=status, count=max(0, int(count)), error=error)

    def select_hea(self, entry: dict[str, Any], *, clear_conversation: bool = True) -> bool:
        with self._lock:
            if self._state["busy"]:
                return False
            selected = {
                "creator_id": str(entry.get("creator_id") or ""),
                "hea_id": str(entry.get("hea_id") or ""),
                "name": str(entry.get("name") or entry.get("hea_id") or "HEA"),
                "avatar_url": str(entry.get("avatar_url") or ""),
                "beta": entry.get("beta") is True,
            }
            updates: dict[str, Any] = {
                "hea_id": selected["hea_id"],
                "selected_hea": selected,
            }
            if clear_conversation:
                updates.update(
                    hea_status="not_checked",
                    answer="",
                    cues=[],
                    error=None,
                    request_id=None,
                )
            self._state.update(updates)
            return True

    def clear_hea_selection(self) -> bool:
        return self.select_hea(
            {
                "creator_id": "",
                "hea_id": "",
                "name": "Choose a public HEA",
                "avatar_url": "",
                "beta": False,
            }
        )

    def set_speech_available(self, available: bool, *, error: str | None = None) -> None:
        with self._lock:
            self._state["speech"].update(
                available=bool(available),
                status="ready" if available else "unavailable",
                error=error,
            )

    def set_speech_status(
        self,
        status: str,
        *,
        error: str | None = None,
        language: str | None = None,
        voice: str | None = None,
    ) -> None:
        with self._lock:
            self._state["speech"].update(
                status=status,
                error=error,
                language=language,
                voice=voice,
            )

    def set_robot_ready(self, ready: bool) -> None:
        with self._lock:
            self._state["robot_ready"] = bool(ready)
            if ready and not self._state["busy"] and not self._state["stopped"]:
                self._state["status"] = "ready"

    def try_queue_turn(self) -> int | None:
        with self._lock:
            if self._state["busy"] or self._state["stopped"] or not self._state["robot_ready"]:
                return None
            turn_id = int(self._state["turn_id"]) + 1
            self._state.update(
                busy=True,
                status="queued",
                turn_id=turn_id,
                answer="",
                cues=[],
                error=None,
                request_id=None,
            )
            return turn_id

    def try_queue_preview(self) -> bool:
        with self._lock:
            if self._state["busy"] or self._state["stopped"] or not self._state["robot_ready"]:
                return False
            self._state.update(
                busy=True,
                status="queued",
                cues=[],
                error=None,
                request_id=None,
            )
            return True

    def set_status(self, status: str) -> None:
        with self._lock:
            if not self._state["stopped"]:
                self._state["status"] = status

    def append_answer(self, delta: str) -> None:
        with self._lock:
            self._state["answer"] += delta

    def record_sentence(
        self,
        cue: str | None,
        emoji: str | None,
        sentence_index: int,
        outcome: str,
        speech_outcome: str,
        text: str,
        speech_language: str | None = None,
        speech_voice: str | None = None,
        motion_cue: str | None = None,
    ) -> None:
        with self._lock:
            cues = self._state["cues"]
            cues.append(
                {
                    "cue": cue,
                    "emoji": emoji,
                    "sentence_index": sentence_index,
                    "outcome": outcome,
                    "speech_outcome": speech_outcome,
                    "speech_language": speech_language,
                    "speech_voice": speech_voice,
                    "motion_cue": motion_cue,
                    "text": str(text or "")[:1_000],
                }
            )
            del cues[:-16]

    def record_cue(self, cue: str, emoji: str, sentence_index: int, outcome: str, text: str) -> None:
        self.record_sentence(cue, emoji, sentence_index, outcome, "not_requested", text)

    def complete(self, *, answer: str, request_id: str | None) -> None:
        with self._lock:
            self._state.update(
                busy=False,
                status="complete",
                answer=answer,
                error=None,
                request_id=request_id,
                hea_status="ready",
            )

    def complete_preview(self) -> None:
        with self._lock:
            self._state.update(busy=False, status="complete", error=None, request_id=None)

    def fail(self, *, code: str, message: str, request_id: str | None) -> None:
        with self._lock:
            self._state.update(
                busy=False,
                status="error",
                error={"code": code, "message": message},
                request_id=request_id,
                hea_status="unavailable",
            )

    def stop(self) -> None:
        with self._lock:
            self._state.update(stopped=True, status="stopped")

    def finish_stopped(self) -> None:
        with self._lock:
            self._state.update(stopped=True, busy=False, status="stopped")

    def try_resume(self) -> bool:
        with self._lock:
            if self._state["busy"]:
                return False
            self._state.update(stopped=False, status="ready", error=None)
            return True
