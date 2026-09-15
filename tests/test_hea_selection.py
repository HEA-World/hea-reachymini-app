import threading
import unittest

from fastapi import HTTPException

from hea_reachy_mini.app_state import AppStateStore
from hea_reachy_mini.cue_contract import CueGate
from hea_reachy_mini.hea_directory import HeaDirectoryError, PublicHea, default_public_hea
from hea_reachy_mini.main import HeaReachyMini


class FakeDirectoryClient:
    def __init__(self, entries=(), error=None):
        self.entries = tuple(entries)
        self.error = error

    def fetch(self):
        if self.error is not None:
            raise self.error
        return self.entries


class HeaSelectionTests(unittest.TestCase):
    def make_app(self, entries):
        app = object.__new__(HeaReachyMini)
        app.state = AppStateStore()
        app._control_lock = threading.RLock()
        app._directory_entries = {}
        app._selected_hea = None
        app._visitor_id = "visitor-before"
        app._session_id = "session-before"
        app.cue_gate = CueGate()
        app.directory_client = FakeDirectoryClient(entries)
        return app

    def test_selects_hea_world_by_default_only_when_the_exact_identity_is_public(self):
        app = self.make_app([default_public_hea()])

        self.assertTrue(app._refresh_directory())

        self.assertEqual(app.state.snapshot()["selected_hea"]["hea_id"], default_public_hea().hea_id)
        self.assertEqual(app.state.snapshot()["selected_hea"]["name"], "HEA World")

        app = self.make_app([PublicHea("owner-public", "another-hea", "Another HEA", "", False)])
        self.assertTrue(app._refresh_directory())
        self.assertEqual(app.state.snapshot()["selected_hea"]["hea_id"], "")

    def test_selects_only_loaded_public_entry_and_resets_conversation_identity(self):
        selected = PublicHea("owner-public", "public-hea", "Public HEA", "https://cdn.example/a.png", False)
        app = self.make_app([default_public_hea(), selected])
        self.assertTrue(app._refresh_directory())

        result = app._select_public_hea(selected.creator_id, selected.hea_id)

        self.assertTrue(result["changed"])
        self.assertEqual(app.state.snapshot()["selected_hea"]["hea_id"], "public-hea")
        self.assertNotEqual(app._visitor_id, "visitor-before")
        self.assertNotEqual(app._session_id, "session-before")
        with self.assertRaises(HTTPException) as missing:
            app._select_public_hea("owner-private", "unlisted-hea")
        self.assertEqual(missing.exception.status_code, 404)

    def test_selection_and_directory_refresh_are_rejected_while_busy(self):
        selected = PublicHea("owner-public", "public-hea", "Public HEA", "", False)
        app = self.make_app([default_public_hea(), selected])
        self.assertTrue(app._refresh_directory())
        app.state.set_robot_ready(True)
        self.assertTrue(app.state.try_queue_turn())

        with self.assertRaises(HTTPException) as busy:
            app._select_public_hea(selected.creator_id, selected.hea_id)
        self.assertEqual(busy.exception.status_code, 409)
        self.assertFalse(app._refresh_directory())

    def test_refresh_clears_a_selection_that_disappeared(self):
        selected = PublicHea("owner-public", "public-hea", "Public HEA", "", False)
        app = self.make_app([default_public_hea(), selected])
        self.assertTrue(app._refresh_directory())
        app._select_public_hea(selected.creator_id, selected.hea_id)
        previous_session = app._session_id
        app.directory_client = FakeDirectoryClient([default_public_hea()])

        self.assertTrue(app._refresh_directory())

        snapshot = app.state.snapshot()
        self.assertEqual(snapshot["selected_hea"]["hea_id"], "")
        self.assertEqual(snapshot["directory"]["status"], "ready")
        self.assertNotEqual(app._session_id, previous_session)

    def test_directory_failure_is_retryable_and_disables_stale_entries(self):
        app = self.make_app([default_public_hea()])
        self.assertTrue(app._refresh_directory())
        app.directory_client = FakeDirectoryClient(
            error=HeaDirectoryError("hea_directory_network_error", "offline")
        )

        self.assertTrue(app._refresh_directory())

        payload = app._directory_payload()
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["error"], "hea_directory_network_error")
        self.assertEqual(payload["items"], [])


if __name__ == "__main__":
    unittest.main()
