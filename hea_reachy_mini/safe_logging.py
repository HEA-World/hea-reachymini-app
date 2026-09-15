"""Small structured logger with an allowlisted, text-free metadata contract."""

from __future__ import annotations

import json
import re
from typing import Any

from .config import APP_VERSION


_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _token(value: object | None) -> str | None:
    if value is None:
        return None
    candidate = str(value)
    return candidate if _SAFE_TOKEN.fullmatch(candidate) else "invalid_identifier"


def safe_log(
    event: str,
    *,
    name: object | None = None,
    code: object | None = None,
    http: int | None = None,
    requestId: object | None = None,
    stage: object | None = None,
    cue: object | None = None,
    sentenceIndex: int | None = None,
    count: int | None = None,
    status: object | None = None,
) -> None:
    """Emit one JSON record; the signature intentionally cannot accept user text."""
    payload: dict[str, Any] = {
        "app": "hea_reachy_mini",
        "appVersion": APP_VERSION,
        "event": _token(event),
    }
    token_fields = {
        "name": name,
        "code": code,
        "requestId": requestId,
        "stage": stage,
        "cue": cue,
        "status": status,
    }
    for key, value in token_fields.items():
        safe_value = _token(value)
        if safe_value is not None:
            payload[key] = safe_value
    if isinstance(http, int):
        payload["http"] = http
    if isinstance(sentenceIndex, int):
        payload["sentenceIndex"] = sentenceIndex
    if isinstance(count, int):
        payload["count"] = count
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True), flush=True)
