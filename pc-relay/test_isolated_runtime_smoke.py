"""Mock-only tests for isolated 8875/8768 runtime inspection and Ollama consent."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_isolated_runtime_smoke as smoke
import bazor_multiai_oneclick as oneclick


class IsolatedRuntimeTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        for name in oneclick.CORE_FILES:
            p = self.root / "pc-relay" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# fake code\n", encoding="utf-8")
        self.sig = smoke.expected_signature(self.root)
        self.assertTrue(self.sig)
        self.data = {
            smoke.PRODUCTION_CORE: {
                "ok": True, "pid": 7, "runtime_signature": "old-production"},
            smoke.PRODUCTION_ROOM: {
                "ok": True, "pid": 8, "runtime_signature": "old-room"},
            smoke.ISOLATED_CORE: {
                "ok": True, "service": "BAZOR API",
                "runtime_signature": self.sig, "pid": 33,
                "core_path": "opaque", "capabilities": ["mammouth_ollama"]},
            smoke.LOCAL_MODELS: {"models": [
                {"name": "llama3.2:3b"}, {"name": "qwen2.5-coder:32b"}]},
            smoke.ISOLATED_ROOM: {
                "ok": True, "version": "2.4-core-relay",
                "engines": {"core": {"available": True, "port": 8875,
                    "runtime_signature": self.sig,
                    "configured_local_model": "llama3.2:3b"}}},
            "http://127.0.0.1:8768/api/chat": {
                "ok": True, "results": [{"provider": "ollama", "ok": True,
                    "model": "llama3.2:3b", "text": "BAZOR_LOCAL_OK"}]}
        }
        self.calls = []
        self.room_owner = 8
        self.owner = lambda port: self.room_owner if port == 8765 else None

    def fetch(self, url, payload=None, timeout=3):
        self.calls.append((url, payload))
        return self.data.get(url)

    def test_missing_stage_fails_without_outbound_calls(self):
        out = smoke.check(self.root / "missing", fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["core"], "STAGE_FILES_MISSING")
        self.assertNotIn(smoke.ISOLATED_CORE, [x[0] for x in self.calls])
        self.assertFalse(any(payload is not None for _, payload in self.calls))

    def test_read_only_checks_identity_without_chat(self):
        out = smoke.check(self.root, fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["result"], "IDENTITY_VERIFIED_CHAT_NOT_RUN")
        self.assertEqual(out["core"], "IDENTITY_VERIFIED")
        self.assertEqual(out["room"], "CONNECTED_TO_VERIFIED_CORE")
        self.assertEqual(out["local_chat"], "NOT_AUTHORIZED")
        self.assertEqual(out["production_core"], "UNCHANGED")
        self.assertEqual(out["production_room"], "UNCHANGED")
        self.assertFalse(any(payload is not None for _, payload in self.calls))

    def test_real_local_chat_only_after_explicit_consent(self):
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["result"], "PASS_REAL_LOCAL")
        self.assertEqual(out["local_chat"], "VERIFIED_REAL_LOCAL")
        writes = [(url, obj) for url, obj in self.calls if obj is not None]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], "http://127.0.0.1:8768/api/chat")
        self.assertEqual(writes[0][1]["target"], "ollama")
        self.assertEqual(out["paid_calls"], 0)
        self.assertEqual(out["deployment"], "NEVER_PERFORMED")

    def test_false_core_health_blocks_chat(self):
        self.data[smoke.ISOLATED_CORE]["runtime_signature"] = "wrong"
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["core"], "ISOLATED_ABSENT_OR_IDENTITY_MISMATCH")
        self.assertEqual(out["result"], "BLOCKED")
        self.assertFalse(any(payload is not None for _, payload in self.calls))

    def test_wrong_room_connection_blocks_chat(self):
        self.data[smoke.ISOLATED_ROOM]["engines"]["core"]["port"] = 8775
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["room"], "ISOLATED_ABSENT_OR_CORE_MISMATCH")
        self.assertFalse(any(payload is not None for _, payload in self.calls))

    def test_empty_ollama_models_blocks_chat(self):
        self.data[smoke.LOCAL_MODELS] = {"models": []}
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["ollama"], "NO_SMALL_MODEL")
        self.assertFalse(any(payload is not None for _, payload in self.calls))

    def test_wrong_ollama_reply_is_not_success(self):
        self.data["http://127.0.0.1:8768/api/chat"]["results"][0]["text"] = "Some misleading BAZOR_LOCAL_OK suffix"
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["local_chat"], "FAILED_OR_UNVERIFIABLE")
        self.assertEqual(out["result"], "BLOCKED")

    def test_changed_live_pid_blocks_even_if_ollama_passes(self):
        counts = {}
        def drifting(url, payload=None, timeout=3):
            counts[url] = counts.get(url, 0) + 1
            if url == smoke.PRODUCTION_CORE and counts[url] == 2:
                return {"ok": True, "pid": 99, "runtime_signature": "old-production"}
            return self.fetch(url, payload, timeout)
        out = smoke.check(self.root, allow_local_chat=True, fetch=drifting, owner=self.owner)
        self.assertEqual(out["production_core"], "CHANGED")
        self.assertEqual(out["result"], "BLOCKED_PRODUCTION_CHANGED")

    def test_unknown_production_owner_never_claimed_unchanged(self):
        self.room_owner = None
        self.data[smoke.PRODUCTION_ROOM] = {"ok": True, "version": "1.2"}
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch, owner=self.owner)
        self.assertEqual(out["production_room"], "NOT_VERIFIED")
        self.assertEqual(out["result"], "BLOCKED")

    def test_changed_live_room_pid_blocks_even_if_ollama_passes(self):
        calls = []
        def changing_owner(port):
            calls.append(port)
            return 8 if len(calls) == 1 else 19
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch,
                          owner=changing_owner)
        self.assertEqual(out["production_room"], "CHANGED")
        self.assertEqual(out["result"], "BLOCKED_PRODUCTION_CHANGED")

    def test_production_room_health_fallback(self):
        self.data[smoke.PRODUCTION_ROOM] = None
        self.data["http://127.0.0.1:8765/health"] = {"ok": True, "version": "1.2"}
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch,
                          owner=self.owner)
        self.assertEqual(out["production_room"], "UNCHANGED")
        self.assertEqual(out["result"], "PASS_REAL_LOCAL")

    def test_windows_netstat_owner_parses_local_listener(self):
        output = chr(10).join(("TCP 127.0.0.1:8765 0.0.0.0:0 EN_ECOUTE 8124",
                               "TCP 0.0.0.0:8765 0.0.0.0:0 EN_ECOUTE 9999"))
        result = MagicMock(returncode=0, stdout=output)
        with (patch.object(smoke.os, "name", "nt"),
              patch.object(smoke.subprocess, "run", return_value=result)):
            self.assertEqual(smoke.windows_listening_pid(8765), 8124)

    def test_missing_windows_owner_never_reports_stable(self):
        out = smoke.check(self.root, allow_local_chat=True, fetch=self.fetch,
                          owner=lambda port: None)
        self.assertEqual(out["local_chat"], "VERIFIED_REAL_LOCAL")
        self.assertEqual(out["production_room"], "NOT_VERIFIED")
        self.assertEqual(out["result"], "BLOCKED")

    def test_public_output_never_reflects_provider_secrets(self):
        fields = {"core": "API_KEY=SENSITIVE", "room": "C:\\private\\password",
                  "ollama": "SENSITIVE", "local_chat": "SENSITIVE",
                  "production_core": "SENSITIVE", "production_room": "SENSITIVE",
                  "result": "SENSITIVE"}
        msg = smoke.public_summary(fields)
        self.assertNotIn("SENSITIVE", msg)
        self.assertNotIn("password", msg)
        self.assertIn("PAID_AI_CALLS: ZERO", msg)


if __name__ == "__main__":
    unittest.main()
