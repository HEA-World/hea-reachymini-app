"""Validated local view of the canonical HEA/Pollen expression catalog."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any

_ALLOWED_CUE_FIELDS = {
    "cue",
    "emoji",
    "description",
    "official_move",
    "motion_enabled",
    "physical_review",
}
_ALLOWED_PHYSICAL_REVIEW = {"pending", "lab_only", "release_approved"}


class ExpressionCatalogError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise ExpressionCatalogError(f"invalid_reachy_expression_catalog:{message}")


def _load_catalog() -> dict[str, Any]:
    resource = files(__package__).joinpath("expression_catalog.json")
    try:
        raw = json.loads(resource.read_text(encoding="utf-8"))
    except Exception as error:
        raise ExpressionCatalogError("could_not_read_expression_catalog") from error

    if not isinstance(raw, dict) or raw.get("schema_version") != 2:
        _fail("unsupported_schema")
    dataset = raw.get("dataset")
    canonical_catalog = raw.get("canonical_cue_catalog")
    legacy_aliases = raw.get("legacy_cue_set_aliases")
    cues = raw.get("cues")
    if (
        not isinstance(dataset, dict)
        or not isinstance(canonical_catalog, dict)
        or not isinstance(legacy_aliases, dict)
        or not isinstance(cues, list)
    ):
        _fail("missing_sections")
    if canonical_catalog.get("id") != "reachy_emoji":
        _fail("invalid_canonical_catalog_id")
    if "reachy_emoji" in legacy_aliases:
        _fail("canonical_id_reused_as_legacy_alias")
    if canonical_catalog.get("status") != "preview":
        _fail("invalid_canonical_status")

    official_moves = dataset.get("official_emotion_moves")
    utility_moves = dataset.get("utility_system_moves")
    if not isinstance(official_moves, list) or not isinstance(utility_moves, list):
        _fail("invalid_move_inventory")
    if len(set(official_moves)) != len(official_moves):
        _fail("duplicate_official_move")
    if set(official_moves).intersection(utility_moves):
        _fail("utility_move_in_emotion_inventory")

    cues_by_name: dict[str, dict[str, Any]] = {}
    emoji_seen: set[str] = set()
    for item in cues:
        if not isinstance(item, dict):
            _fail("cue_not_object")
        if set(item) - _ALLOWED_CUE_FIELDS:
            _fail("forbidden_cue_field")
        cue = item.get("cue")
        emoji = item.get("emoji")
        move = item.get("official_move")
        if not isinstance(cue, str) or not cue or cue in cues_by_name:
            _fail(f"invalid_or_duplicate_cue:{cue}")
        if not isinstance(emoji, str) or not emoji or emoji in emoji_seen:
            _fail(f"invalid_or_duplicate_emoji:{cue}")
        if move not in official_moves:
            _fail(f"unknown_official_move:{cue}:{move}")
        if not isinstance(item.get("motion_enabled"), bool):
            _fail(f"invalid_motion_enabled:{cue}")
        if item.get("physical_review") not in _ALLOWED_PHYSICAL_REVIEW:
            _fail(f"invalid_physical_review:{cue}")
        if item["motion_enabled"] and item["physical_review"] == "pending":
            _fail(f"pending_motion_enabled:{cue}")
        cues_by_name[cue] = dict(item)
        emoji_seen.add(emoji)

    cue_sets = {"reachy_emoji": canonical_catalog, **legacy_aliases}
    for version, cue_set in cue_sets.items():
        if not isinstance(cue_set, dict):
            _fail(f"invalid_cue_set:{version}")
        if version != "reachy_emoji" and not re.fullmatch(r"reachy_emoji_v\d+", version):
            _fail(f"invalid_legacy_alias:{version}")
        if version != "reachy_emoji" and cue_set.get("status") != "legacy":
            _fail(f"invalid_legacy_status:{version}")
        names = cue_set.get("cues")
        if not isinstance(names, list) or len(set(names)) != len(names):
            _fail(f"invalid_cue_set:{version}")
        if any(name not in cues_by_name for name in names):
            _fail(f"unknown_cue_set_member:{version}")
    if len(canonical_catalog["cues"]) != len(cues_by_name):
        _fail("canonical_catalog_not_complete")
    return raw


CATALOG = _load_catalog()
CATALOG_REVISION = str(CATALOG["catalog_revision"])
CANONICAL_CUE_CATALOG_ID = str(CATALOG["canonical_cue_catalog"]["id"])
LEGACY_CUE_SET_ALIASES = tuple(CATALOG["legacy_cue_set_aliases"])
SUPPORTED_CUE_SET_VERSIONS = (CANONICAL_CUE_CATALOG_ID, *LEGACY_CUE_SET_ALIASES)
# Compatibility alias for the established request field and installed clients.
DEFAULT_CUE_SET_VERSION = CANONICAL_CUE_CATALOG_ID
OFFICIAL_EMOTIONS_DATASET = str(CATALOG["dataset"]["repo_id"])
OFFICIAL_DATASET_REVISION = str(CATALOG["dataset"]["revision"])
OFFICIAL_EMOTION_MOVES = frozenset(CATALOG["dataset"]["official_emotion_moves"])
_CUES_BY_NAME = {item["cue"]: item for item in CATALOG["cues"]}


def cue_definitions(cue_set_version: str) -> dict[str, dict[str, Any]]:
    if cue_set_version == CANONICAL_CUE_CATALOG_ID:
        cue_set = CATALOG["canonical_cue_catalog"]
    else:
        cue_set = CATALOG["legacy_cue_set_aliases"].get(cue_set_version)
    if cue_set is None:
        raise ExpressionCatalogError(f"unsupported_cue_set_version:{cue_set_version}")
    return {name: dict(_CUES_BY_NAME[name]) for name in cue_set["cues"]}


def motion_move_by_cue(cue_set_version: str) -> dict[str, str]:
    return {
        name: item["official_move"]
        for name, item in cue_definitions(cue_set_version).items()
        if item["motion_enabled"]
    }
