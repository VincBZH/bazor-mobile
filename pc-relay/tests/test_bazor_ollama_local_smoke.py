"""Offline tests; no local services, shell or paid APIs required."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bazor_ollama_local_smoke as smoke


def fake_request(url, payload=None, timeout=None, *, echo=True, core_ok=True):
    assert url.startswith(("http://127.0.0.1:8775", "http://127.0.0.1:8765",
                           "http://127.0.0.1:11434"))
    if url.endswith("/api/v1/health"):
        return {"ok": core_ok}
    if url.endswith("/health"):
        return {"ok": True}
    if url.endswith("/api/tags"):
        return {"models": [{"name": "qwen2.5-coder:7b"}]}
    if url.endswith("/api/v1/chat"):
        assert payload["target"] == "ollama"
        assert payload["model"] == "qwen2.5-coder:7b"
        token = payload["text"].split("token: ", 1)[1]
        return {
            "ok": True,
            "target": "ollama",
            "ollama": {
                "ok": True,
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "answer": token if echo else "No token received",
            },
        }
    raise AssertionError("unexpected URL: " + url)


class TestLocalProbe(unittest.TestCase):
    def run_checked(self, request=fake_request, engine=True):
        with patch.object(smoke, "_action_engine_api_present", return_value=engine):
            return smoke.run_probe(request=request, nonce="BAZOR_LOCAL_TEST_NONCE")

    def test_pass_local_only(self):
        r = self.run_checked()
        self.assertEqual(r["status"], "LOCAL_ONLY_READY")
        self.assertEqual(r["model"], "qwen2.5-coder:7b")
        self.assertTrue(all(r["checks"].values()))
        self.assertFalse(r["paid_api_used"])
        self.assertFalse(r["mammouth_used"])
        self.assertFalse(r["action_engine_used"])
        self.assertEqual(r["files_changed"], 0)
        self.assertEqual(r["trio_ready"], "NOT_EVALUATED")

    def test_core_unavailable_blocks(self):
        def request(url, payload=None, timeout=None):
            return fake_request(url, payload, timeout, core_ok=False)
        r = self.run_checked(request=request)
        self.assertEqual(r["status"], "LOCAL_ONLY_BLOCKED")
        self.assertFalse(r["checks"]["core"])

    def test_missing_echo_blocks(self):
        def request(url, payload=None, timeout=None):
            return fake_request(url, payload, timeout, echo=False)
        r = self.run_checked(request=request)
        self.assertEqual(r["status"], "LOCAL_ONLY_BLOCKED")
        self.assertFalse(r["checks"]["core_ollama_response"])

    def test_engine_api_missing_blocks(self):
        r = self.run_checked(engine=False)
        self.assertEqual(r["status"], "LOCAL_ONLY_BLOCKED")
        self.assertFalse(r["checks"]["action_engine_api"])


if __name__ == "__main__":
    unittest.main()
