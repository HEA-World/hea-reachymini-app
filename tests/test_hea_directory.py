import json
import unittest

from hea_reachy_mini.hea_directory import HeaDirectoryClient, HeaDirectoryError


class FakeResponse:
    def __init__(self, payload, *, status=200, content_type="application/json"):
        self.payload = payload
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.closed = False

    def iter_content(self, chunk_size=16_384):
        for index in range(0, len(self.payload), max(1, min(chunk_size, 7))):
            yield self.payload[index : index + max(1, min(chunk_size, 7))]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def encoded(rows):
    return json.dumps(rows).encode("utf-8")


class HeaDirectoryClientTests(unittest.TestCase):
    def test_fetch_validates_deduplicates_sorts_and_sanitizes_public_rows(self):
        response = FakeResponse(
            encoded(
                [
                    {
                        "creator_id": "owner-z",
                        "hea_id": "zeta-1",
                        "hea_displayed_name": " Zeta\u0000 Guide ",
                        "hea_avatar_url": "http://unsafe.example/avatar.png",
                    },
                    {
                        "creator_id": "owner-a",
                        "hea_id": "alpha-1",
                        "hea_name": "Alpha",
                        "hea_avatar_url": "https://cdn.example/avatar.png",
                        "beta": True,
                    },
                    {
                        "creator_id": "owner-a",
                        "hea_id": "alpha-1",
                        "hea_displayed_name": "Alpha updated",
                        "hea_avatar_url": "https://cdn.example/new.png",
                    },
                    {"creator_id": "../private", "hea_id": "bad", "hea_name": "Invalid"},
                ]
            )
        )
        session = FakeSession(response)

        entries = HeaDirectoryClient(endpoint="https://example.invalid/directory.json", session=session).fetch()

        self.assertEqual([entry.name for entry in entries], ["Alpha updated", "Zeta Guide"])
        self.assertEqual(entries[0].key, ("owner-a", "alpha-1"))
        self.assertEqual(entries[0].avatar_url, "https://cdn.example/new.png")
        self.assertEqual(entries[1].avatar_url, "")
        self.assertTrue(response.closed)
        self.assertTrue(session.calls[0][1]["stream"])

    def test_oversized_and_non_list_directories_fail_closed(self):
        oversized = FakeResponse(b"[] " * 10)
        with self.assertRaises(HeaDirectoryError) as too_large:
            HeaDirectoryClient(session=FakeSession(oversized), max_bytes=8).fetch()
        self.assertEqual(too_large.exception.code, "hea_directory_too_large")

        invalid_shape = FakeResponse(encoded({"creator_id": "owner"}))
        with self.assertRaises(HeaDirectoryError) as bad_shape:
            HeaDirectoryClient(session=FakeSession(invalid_shape)).fetch()
        self.assertEqual(bad_shape.exception.code, "hea_directory_invalid_shape")

    def test_empty_valid_set_and_http_failure_are_structured(self):
        invalid_rows = FakeResponse(encoded([{"creator_id": "bad/id", "hea_id": "private"}]))
        with self.assertRaises(HeaDirectoryError) as empty:
            HeaDirectoryClient(session=FakeSession(invalid_rows)).fetch()
        self.assertEqual(empty.exception.code, "hea_directory_empty")

        unavailable = FakeResponse(b"", status=503)
        with self.assertRaises(HeaDirectoryError) as http_error:
            HeaDirectoryClient(session=FakeSession(unavailable)).fetch()
        self.assertEqual(http_error.exception.code, "hea_directory_http_error")
        self.assertEqual(http_error.exception.http, 503)


if __name__ == "__main__":
    unittest.main()
