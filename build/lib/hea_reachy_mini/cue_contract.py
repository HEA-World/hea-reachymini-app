"""Fail-closed conversion from HEA semantic cues to local behavior ids."""

from __future__ import annotations

import threading
import re
from dataclasses import dataclass
from typing import Any

from .config import CUE_SET_VERSION, MAX_SENTENCES
from .expression_catalog import cue_definitions


@dataclass(frozen=True)
class CueSelection:
    """A validated local semantic selection; it contains no motion parameters."""

    cue: str
    emoji: str
    message_id: str
    sentence_index: int


@dataclass(frozen=True)
class AcceptedSentence:
    """A validated, ordered sentence event with an optional safe cue."""

    message_id: str
    sentence_index: int
    selection: CueSelection | None
    language: str | None


class CueGate:
    """Validate, deduplicate, and order sentence cue events."""

    def __init__(self, cue_set_version: str = CUE_SET_VERSION) -> None:
        self._cue_set_version = cue_set_version
        self._definitions = cue_definitions(cue_set_version)
        self._last_sentence_by_message: dict[str, int] = {}
        self._lock = threading.Lock()

    def accept_sentence(self, event: Any) -> AcceptedSentence | None:
        if not isinstance(event, dict) or event.get("type") != "reachy_sentence_ready":
            return None
        if event.get("cue_set_version") != self._cue_set_version:
            return None

        message_id = str(event.get("msg_id") or event.get("request_id") or "").strip()
        sentence_index = event.get("sentence_index")
        if not message_id or not isinstance(sentence_index, int):
            return None
        if sentence_index < 0 or sentence_index >= MAX_SENTENCES:
            return None

        raw_language = str(event.get("language") or "").strip().lower().replace("_", "-")
        base_language = raw_language.split("-", 1)[0]
        language = base_language if re.fullmatch(r"[a-z]{2,3}", base_language) else None

        with self._lock:
            last_index = self._last_sentence_by_message.get(message_id, -1)
            if sentence_index <= last_index:
                return None
            self._last_sentence_by_message[message_id] = sentence_index

        if "cue_item" not in event:
            return None
        cue_item = event["cue_item"]
        if cue_item is None:
            return AcceptedSentence(
                message_id=message_id,
                sentence_index=sentence_index,
                selection=None,
                language=language,
            )
        if not isinstance(cue_item, dict):
            return None
        cue = str(cue_item.get("cue") or "").strip()
        definition = self._definitions.get(cue)
        if definition is None:
            return None

        # Numeric fields from the network (including intensity) are deliberately
        # ignored. Only this local enum-like behavior id crosses the boundary.
        return AcceptedSentence(
            message_id=message_id,
            sentence_index=sentence_index,
            selection=CueSelection(
                cue=cue,
                emoji=definition["emoji"],
                message_id=message_id,
                sentence_index=sentence_index,
            ),
            language=language,
        )

    def accept_sentence_event(self, event: Any) -> CueSelection | None:
        """Compatibility helper for callers that only need an accepted cue."""
        accepted = self.accept_sentence(event)
        return accepted.selection if accepted is not None else None

    def select_local_preview(self, cue: str, message_id: str) -> CueSelection | None:
        """Resolve a lab-panel cue without accepting any motion parameters."""
        cue_name = str(cue or "").strip()
        definition = self._definitions.get(cue_name)
        if definition is None:
            return None
        return CueSelection(
            cue=cue_name,
            emoji=definition["emoji"],
            message_id=str(message_id),
            sentence_index=0,
        )
