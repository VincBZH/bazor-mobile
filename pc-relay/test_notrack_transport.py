from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import notrack_client


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = json.dumps(payload).encode("utf-8")
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


class NoTrackClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = mock.patch.dict(os.environ, {
            "BAZOR_DATA_DIR": self.tmp.name,
            "BAZOR_NOTRACK_ENABLED": "1",
            "BAZOR_NOTRACK_DAILY_CALL_CAP": "2",
            "NOTRACK_API_KEY": "sk-notrack-TEST-SECRET",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        notrack_client.DATA_DIR = Path(self.tmp.name)

    def test_disabled_by_default_gate(self):
        os.environ["BAZOR_NOTRACK_ENABLED"] = "0"
        result = notrack_client.chat("hello")
        self.assertEqual(result["error"], "notrack_disabled")

    def test_positive_local_cap_is_required(self):
        os.environ["BAZOR_NOTRACK_DAILY_CALL_CAP"] = "0"
        result = notrack_client.chat("hello")
        self.assertEqual(result["error"], "notrack_explicit_cap_required")

    def test_success_uses_fixed_provider_and_never_returns_key(self):
        payload = {
            "model": "notrack-uncensored",
            "choices": [{"message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1},
        }
        with mock.patch("notrack_client.urllib.request.urlopen", return_value=FakeResponse(payload)):
            result = notrack_client.chat("hello", request_id="r1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "notrack")
        self.assertEqual(result["model"], "notrack-uncensored")
        self.assertEqual(result["answer"], "OK")
        self.assertNotIn("TEST-SECRET", json.dumps(result))
        self.assertEqual(result["status"]["attempted_calls"], 1)
        self.assertEqual(result["status"]["successful_calls"], 1)

    def test_401_is_classified_and_redacted(self):
        body = json.dumps({"error": {"type": "invalid_key", "message": "sk-notrack-TEST-SECRET invalid"}}).encode()
        err = urllib.error.HTTPError(notrack_client.NOTRACK_URL, 401, "Unauthorized", {}, io.BytesIO(body))
        with mock.patch("notrack_client.urllib.request.urlopen", side_effect=err):
            result = notrack_client.chat("hello")
        self.assertEqual(result["error"], "notrack_auth")
        self.assertEqual(result["provider_error_type"], "invalid_key")
        self.assertNotIn("TEST-SECRET", json.dumps(result))

    def test_local_daily_cap_blocks_third_attempt(self):
        ok = {"model": "notrack-uncensored", "choices": [{"message": {"content": "OK"}}]}
        with mock.patch("notrack_client.urllib.request.urlopen", return_value=FakeResponse(ok)):
            self.assertTrue(notrack_client.chat("one")["ok"])
            self.assertTrue(notrack_client.chat("two")["ok"])
            third = notrack_client.chat("three")
        self.assertEqual(third["error"], "notrack_daily_cap_reached")


if __name__ == "__main__":
    unittest.main(verbosity=2)
