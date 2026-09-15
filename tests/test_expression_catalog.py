import unittest

from hea_reachy_mini import __version__
from hea_reachy_mini.app_state import AppStateStore
from hea_reachy_mini.config import APP_VERSION
from hea_reachy_mini.expression_catalog import (
    CANONICAL_CUE_CATALOG_ID,
    CATALOG,
    DEFAULT_CUE_SET_VERSION,
    OFFICIAL_EMOTION_MOVES,
    SUPPORTED_CUE_SET_VERSIONS,
    cue_definitions,
    motion_move_by_cue,
)


class ExpressionCatalogTests(unittest.TestCase):
    def test_app_version_and_local_motion_legend_are_catalog_driven(self):
        self.assertEqual(__version__, APP_VERSION)
        state = AppStateStore().snapshot()
        self.assertEqual(state["cue_catalog_id"], "reachy_emoji")
        self.assertEqual(
            state["motion_allowlist"],
            [
                {"cue": "warm_smile", "emoji": "😊", "label": "Warm Smile"},
                {"cue": "thinking", "emoji": "🤔", "label": "Thinking"},
                {"cue": "agree", "emoji": "✅", "label": "Agree"},
                {"cue": "goodbye", "emoji": "👋", "label": "Goodbye"},
            ],
        )
        self.assertNotIn("official_move", state["motion_allowlist"][0])
        self.assertEqual(len(state["cue_catalog"]), 24)
        self.assertEqual(
            set(state["cue_catalog"][0]),
            {"cue", "emoji", "label", "description", "motion_enabled"},
        )
        self.assertNotIn("official_move", state["cue_catalog"][0])
        self.assertEqual(sum(item["motion_enabled"] for item in state["cue_catalog"]), 4)

    def test_catalog_inventories_upstream_and_uses_one_canonical_default(self):
        self.assertEqual(CANONICAL_CUE_CATALOG_ID, "reachy_emoji")
        self.assertEqual(DEFAULT_CUE_SET_VERSION, "reachy_emoji")
        self.assertEqual(
            SUPPORTED_CUE_SET_VERSIONS,
            ("reachy_emoji", "reachy_emoji_v1", "reachy_emoji_v2"),
        )
        self.assertEqual(len(OFFICIAL_EMOTION_MOVES), 81)
        self.assertEqual(len(CATALOG["dataset"]["utility_system_moves"]), 4)
        self.assertTrue(OFFICIAL_EMOTION_MOVES.isdisjoint(CATALOG["dataset"]["utility_system_moves"]))

    def test_canonical_catalog_has_24_unique_visual_semantics(self):
        v1 = cue_definitions("reachy_emoji_v1")
        canonical = cue_definitions("reachy_emoji")
        self.assertEqual(len(v1), 8)
        self.assertEqual(len(canonical), 24)
        self.assertTrue(set(v1).issubset(canonical))
        self.assertEqual(cue_definitions("reachy_emoji_v2"), canonical)
        self.assertEqual(len({item["emoji"] for item in canonical.values()}), 24)
        self.assertEqual(canonical["confused"]["emoji"], "😕")
        self.assertEqual(canonical["confused"]["official_move"], "confused1")

    def test_only_four_lab_recordings_are_motion_enabled(self):
        expected = {
            "warm_smile": "welcoming2",
            "thinking": "thoughtful2",
            "agree": "understanding2",
            "goodbye": "loving1",
        }
        self.assertEqual(motion_move_by_cue("reachy_emoji"), expected)
        self.assertEqual(motion_move_by_cue("reachy_emoji_v2"), expected)


if __name__ == "__main__":
    unittest.main()
