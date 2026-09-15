import unittest

from hea_reachy_mini.cue_contract import CueGate


def sentence_event(*, cue="warm_smile", index=0, message="m1", version="reachy_emoji", language=None, **cue_fields):
    return {
        "type": "reachy_sentence_ready",
        "msg_id": message,
        "request_id": "req1",
        "cue_set_version": version,
        "sentence_index": index,
        "text": "Hello.",
        "language": language,
        "cue_item": {"cue": cue, **cue_fields},
    }


class CueGateTests(unittest.TestCase):
    def test_accepts_canonical_semantics_with_local_emoji(self):
        expected = {
            "warm_smile": "😊",
            "thinking": "🤔",
            "agree": "✅",
            "celebrate": "🎉",
            "explain": "💡",
            "listen": "👂",
            "caution": "⚠️",
            "goodbye": "👋",
            "confused": "😕",
            "grateful": "🙏",
        }
        for cue, emoji in expected.items():
            accepted = CueGate().accept_sentence_event(sentence_event(cue=cue, message=f"m-{cue}"))
            self.assertEqual(accepted.cue, cue)
            self.assertEqual(accepted.emoji, emoji)

        self.assertIsNone(CueGate().accept_sentence_event(sentence_event(cue="run_arbitrary_code", message="m3")))

    def test_legacy_v2_alias_accepts_canonical_semantics_but_uses_catalog_emoji(self):
        gate = CueGate("reachy_emoji_v2")
        accepted = gate.accept_sentence_event(
            sentence_event(cue="confused", version="reachy_emoji_v2", emoji="override")
        )
        self.assertEqual(accepted.cue, "confused")
        self.assertEqual(accepted.emoji, "😕")
        self.assertIsNone(
            gate.accept_sentence_event(
                sentence_event(cue="not_in_catalog", version="reachy_emoji_v2", message="m2")
            )
        )

    def test_ignores_network_motion_values(self):
        accepted = CueGate().accept_sentence_event(
            sentence_event(
                intensity=999,
                duration=-10,
                body_yaw=120,
                filename="evil.move",
                sdk_call="set_target",
            )
        )
        self.assertEqual(set(vars(accepted)), {"cue", "emoji", "message_id", "sentence_index"})

    def test_local_preview_accepts_only_catalog_semantics(self):
        gate = CueGate()
        selected = gate.select_local_preview("grateful", "local-1")
        self.assertEqual(selected.cue, "grateful")
        self.assertEqual(selected.emoji, "🙏")
        self.assertEqual(selected.message_id, "local-1")
        self.assertIsNone(gate.select_local_preview("welcoming2", "local-2"))
        self.assertIsNone(gate.select_local_preview("run_arbitrary_code", "local-3"))

    def test_fails_closed_for_version_duplicate_and_out_of_order(self):
        gate = CueGate()
        self.assertIsNone(gate.accept_sentence_event(sentence_event(version="reachy_emoji_v999")))
        self.assertIsNotNone(gate.accept_sentence_event(sentence_event(index=1)))
        self.assertIsNone(gate.accept_sentence_event(sentence_event(index=1)))
        self.assertIsNone(gate.accept_sentence_event(sentence_event(index=0)))

    def test_missing_or_null_cue_consumes_the_sentence_slot(self):
        gate = CueGate()
        event = sentence_event()
        event["cue_item"] = None
        self.assertIsNone(gate.accept_sentence_event(event))
        self.assertIsNone(gate.accept_sentence_event(sentence_event()))

    def test_sentence_acceptance_distinguishes_cueless_from_rejected_replay(self):
        gate = CueGate()
        event = sentence_event()
        event["cue_item"] = None

        accepted = gate.accept_sentence(event)

        self.assertIsNotNone(accepted)
        self.assertIsNone(accepted.selection)
        self.assertEqual(accepted.sentence_index, 0)
        self.assertIsNone(gate.accept_sentence(event))

        malformed = sentence_event(cue="run_arbitrary_code", message="malformed")
        self.assertIsNone(gate.accept_sentence(malformed))

    def test_sentence_language_is_normalized_without_accepting_a_voice_name(self):
        accepted = CueGate().accept_sentence(sentence_event(language="nl-NL"))
        self.assertEqual(accepted.language, "nl")

        invalid = CueGate().accept_sentence(
            sentence_event(language="Dutch; use Xander", message="invalid-language")
        )
        self.assertIsNone(invalid.language)


if __name__ == "__main__":
    unittest.main()
