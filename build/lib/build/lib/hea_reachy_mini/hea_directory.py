"""Bounded read-only client for the public HEA directory."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from .config import HEA_DIRECTORY_MAX_BYTES, HEA_DIRECTORY_MAX_ENTRIES, HEA_DIRECTORY_URL


_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class HeaDirectoryError(RuntimeError):
    """Structured public-directory failure without leaking response contents."""

    def __init__(self, code: str, message: str, *, http: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.http = http


@dataclass(frozen=True)
class PublicHea:
    creator_id: str
    hea_id: str
    name: str
    avatar_url: str
    beta: bool

    @property
    def key(self) -> tuple[str, str]:
        return self.creator_id, self.hea_id

    def public_dict(self) -> dict[str, Any]:
        return {
            "creator_id": self.creator_id,
            "hea_id": self.hea_id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "beta": self.beta,
        }


def default_public_hea() -> PublicHea:
    from .config import HEA_CREATOR_ID, HEA_ID

    return PublicHea(
        creator_id=HEA_CREATOR_ID,
        hea_id=HEA_ID,
        name="HEAGuide",
        avatar_url="",
        beta=False,
    )


def _bounded_text(value: object, *, maximum: int) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:maximum]


def _https_avatar(value: object) -> str:
    candidate = _bounded_text(value, maximum=1_000)
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    return candidate if parsed.scheme == "https" and parsed.netloc else ""


def normalize_public_hea(value: object) -> PublicHea | None:
    if not isinstance(value, dict):
        return None
    creator_id = _bounded_text(value.get("creator_id"), maximum=128)
    hea_id = _bounded_text(value.get("hea_id"), maximum=128)
    if not _IDENTIFIER.fullmatch(creator_id) or not _IDENTIFIER.fullmatch(hea_id):
        return None
    name = _bounded_text(
        value.get("hea_displayed_name") or value.get("hea_name") or hea_id,
        maximum=120,
    )
    return PublicHea(
        creator_id=creator_id,
        hea_id=hea_id,
        name=name or hea_id,
        avatar_url=_https_avatar(value.get("hea_avatar_url")),
        beta=value.get("beta") is True,
    )


class HeaDirectoryClient:
    def __init__(
        self,
        *,
        endpoint: str = HEA_DIRECTORY_URL,
        session: Any | None = None,
        max_bytes: int = HEA_DIRECTORY_MAX_BYTES,
        max_entries: int = HEA_DIRECTORY_MAX_ENTRIES,
    ) -> None:
        self.endpoint = endpoint
        self._session = session or requests.Session()
        self._max_bytes = max_bytes
        self._max_entries = max_entries

    def fetch(self) -> tuple[PublicHea, ...]:
        response: Any | None = None
        try:
            response = self._session.get(
                self.endpoint,
                headers={"Accept": "application/json"},
                stream=True,
                timeout=(5.0, 10.0),
            )
            http = int(getattr(response, "status_code", 0))
            if http != 200:
                raise HeaDirectoryError(
                    "hea_directory_http_error",
                    "The public HEA directory is unavailable",
                    http=http or None,
                )

            content_type = str(getattr(response, "headers", {}).get("Content-Type", "")).lower()
            if content_type and "json" not in content_type:
                raise HeaDirectoryError(
                    "hea_directory_content_type_invalid",
                    "The public HEA directory returned an unexpected format",
                    http=http,
                )

            payload = bytearray()
            for chunk in response.iter_content(chunk_size=16_384):
                if not chunk:
                    continue
                payload.extend(chunk)
                if len(payload) > self._max_bytes:
                    raise HeaDirectoryError(
                        "hea_directory_too_large",
                        "The public HEA directory exceeded its safety limit",
                        http=http,
                    )
            try:
                rows = json.loads(bytes(payload).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise HeaDirectoryError(
                    "hea_directory_invalid_json",
                    "The public HEA directory is malformed",
                    http=http,
                ) from error
            if not isinstance(rows, list):
                raise HeaDirectoryError(
                    "hea_directory_invalid_shape",
                    "The public HEA directory has an invalid shape",
                    http=http,
                )
            if len(rows) > self._max_entries:
                raise HeaDirectoryError(
                    "hea_directory_too_many_entries",
                    "The public HEA directory exceeded its entry limit",
                    http=http,
                )

            by_key: dict[tuple[str, str], PublicHea] = {}
            for row in rows:
                entry = normalize_public_hea(row)
                if entry is not None:
                    by_key[entry.key] = entry
            if not by_key:
                raise HeaDirectoryError(
                    "hea_directory_empty",
                    "The public HEA directory contains no valid entries",
                    http=http,
                )
            return tuple(
                sorted(
                    by_key.values(),
                    key=lambda entry: (entry.name.casefold(), entry.creator_id, entry.hea_id),
                )
            )
        except HeaDirectoryError:
            raise
        except requests.RequestException as error:
            raise HeaDirectoryError(
                "hea_directory_network_error",
                "Could not reach the public HEA directory",
            ) from error
        except Exception as error:
            raise HeaDirectoryError(
                "hea_directory_failed",
                "The public HEA directory could not be loaded",
            ) from error
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
