"""Real localhost HTTP test with a fake Core: no provider calls, no money."""
import importlib.util
import json
import pathlib
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

path = pathlib.Path(__file__).resolve().parent / "app" / "room_v2_server.py"
spec = importlib.util.spec_from_file_location("room_v2_server", path)
room = importlib.util.module_from_spec(spec)
spec.loader.exec_module(room)


class FakeCore(BaseHTTPRequestHandler):
    chat_calls = []
    configured = False
    offline = False
    fail_mammouth = False
    fail_ollama = False
    fail_notrack = False
    notrack_configured = False

    def respond(self, body, status=200):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        return self.respond({
            "ok": True, "service": "BAZOR API",
            "ollama": {"online": not self.offline, "models": ["qwen2.5-coder:7b"]},
            "mammouth": {"configured": self.configured,
                         "budget": {"blocked": False, "remaining_usd": 4}},
            "notrack": {"configured": self.notrack_configured, "blocked": False,
                        "daily_call_cap": 2, "remaining_calls": 2},
        })

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.chat_calls.append(body)
        result = {"ok": True}
        if body.get("target") in ("ollama", "both"):
            result["ollama"] = ({"ok": False, "provider": "ollama", "error": "ollama_failed"}
                if self.fail_ollama else {"ok": True, "provider": "ollama", "model": "qwen2.5-coder:7b",
                                        "answer": "OLLAMA_OK"})
        if body.get("target") in ("mammouth", "both"):
            result["mammouth"] = (
                {"ok": False, "provider": "mammouth", "error": "http_401"} if self.fail_mammouth
                else {"ok": True, "provider": "mammouth", "model": "mistral-small-3.2-24b-instruct",
                      "answer": "MAMMOUTH_OK", "http_status": 200}
            )
        if body.get("target") == "notrack":
            result["notrack"] = (
                {"ok": False, "provider": "notrack", "error": "notrack_failed", "http_status": 503}
                if self.fail_notrack else
                {"ok": True, "provider": "notrack", "model": "notrack-uncensored",
                 "answer": "NOTRACK_OK", "http_status": 200}
            )
        self.respond(result)

    def log_message(self, *args):
        pass


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = ThreadingHTTPServer(("127.0.0.1", 0), FakeCore)
        cls.room = ThreadingHTTPServer(("127.0.0.1", 0), room.Handler)
        room._core_origin = lambda: "http://127.0.0.1:" + str(cls.core.server_port)
        for service in (cls.core, cls.room):
            threading.Thread(target=service.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:" + str(cls.room.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.core.shutdown()
        cls.room.shutdown()
        cls.core.server_close()
        cls.room.server_close()

    def setUp(self):
        FakeCore.chat_calls = []
        FakeCore.configured = False
        FakeCore.offline = False
        FakeCore.fail_mammouth = False
        FakeCore.fail_ollama = False
        FakeCore.fail_notrack = False
        FakeCore.notrack_configured = False

    def post(self, payload):
        req = urllib.request.Request(self.url + "/api/chat", json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as r:
            return r.code, json.load(r)

    def test_ollama_actual_chat(self):
        status, body = self.post({"target": "ollama", "text": "Bonjour"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["results"][0]["model"], "qwen2.5-coder:7b")
        self.assertEqual(FakeCore.chat_calls[0]["target"], "ollama")

    def test_mammouth_requires_positive_consent(self):
        FakeCore.configured = True
        status, body = self.post({"target": "mammouth", "text": "Bonjour"})
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "external_consent_required")
        self.assertEqual(FakeCore.chat_calls, [])

    def test_missing_key_cannot_trigger_paid_call(self):
        status, body = self.post({"target": "mammouth", "text": "Bonjour", "allow_external": True})
        self.assertEqual(status, 503)
        self.assertEqual(body["error"], "mammouth_key_missing_on_core")
        self.assertEqual(FakeCore.chat_calls, [])

    def test_both_with_consent(self):
        FakeCore.configured = True
        status, body = self.post({"target": "both", "text": "Bonjour", "allow_external": True})
        self.assertEqual(status, 200)
        self.assertEqual([r["provider"] for r in body["results"]], ["ollama", "mammouth"])
        self.assertTrue(all(r["ok"] for r in body["results"]))
        self.assertEqual([c["target"] for c in FakeCore.chat_calls], ["ollama", "mammouth"])
        self.assertEqual(FakeCore.chat_calls[1]["profile"], "light")
        self.assertIn("OLLAMA_OK", FakeCore.chat_calls[1]["text"])

    def test_partial_failure_cannot_be_green(self):
        FakeCore.configured = True
        FakeCore.fail_mammouth = True
        status, body = self.post({"target": "both", "text": "Bonjour", "allow_external": True})
        self.assertEqual(status, 502)
        self.assertFalse(body["ok"])
        self.assertTrue(body["results"][0]["ok"])
        self.assertFalse(body["results"][1]["ok"])

    def test_local_failure_does_not_trigger_paid_review(self):
        FakeCore.configured = True
        FakeCore.fail_ollama = True
        status, body = self.post({"target": "both", "text": "Bonjour", "allow_external": True})
        self.assertEqual(status, 502)
        self.assertFalse(body["results"][0]["ok"])
        self.assertEqual([c["target"] for c in FakeCore.chat_calls], ["ollama"])

    def test_gpt_is_manual_handoff_not_fake_api(self):
        status, body = self.post({"target": "gpt", "text": "Question publique"})
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "manual_handoff")
        self.assertEqual(FakeCore.chat_calls, [])

    def test_notrack_requires_consent_and_configuration(self):
        status, body = self.post({"target": "notrack", "text": "Question publique"})
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "external_consent_required")
        self.assertEqual(FakeCore.chat_calls, [])
        status, body = self.post({"target": "notrack", "text": "Question publique", "allow_external": True})
        self.assertEqual(status, 503)
        self.assertEqual(body["error"], "notrack_not_configured_on_core")
        self.assertEqual(FakeCore.chat_calls, [])
        FakeCore.notrack_configured = True
        status, body = self.post({"target": "notrack", "text": "Question publique", "allow_external": True})
        self.assertEqual(status, 200)
        self.assertEqual(body["results"][0]["provider"], "notrack")
        self.assertEqual(body["results"][0]["model"], "notrack-uncensored")
        self.assertEqual(FakeCore.chat_calls[0]["target"], "notrack")

    def test_notrack_then_ollama_real_sequence_contract(self):
        FakeCore.notrack_configured = True
        status, body = self.post({"target": "notrack_ollama", "text": "Résous ce problème", "allow_external": True})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual([r["provider"] for r in body["results"]], ["notrack", "ollama"])
        self.assertEqual([c["target"] for c in FakeCore.chat_calls], ["notrack", "ollama"])
        self.assertIn("NOTRACK_OK", FakeCore.chat_calls[1]["text"])
        self.assertIn("STRATEGIE NOTRACK", FakeCore.chat_calls[1]["text"])

    def test_notrack_failure_falls_back_to_ollama_without_false_strategy(self):
        FakeCore.notrack_configured = True
        FakeCore.fail_notrack = True
        status, body = self.post({"target": "notrack_ollama", "text": "Résous ce problème", "allow_external": True})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "fallback_complete")
        self.assertEqual(body["strategist"], "notrack_unavailable")
        self.assertEqual(body["delegated_to"], "ollama")
        self.assertEqual([c["target"] for c in FakeCore.chat_calls], ["notrack", "ollama"])
        self.assertIn("NOTRACK INDISPONIBLE", FakeCore.chat_calls[1]["text"])
        self.assertNotIn("STRATEGIE NOTRACK", FakeCore.chat_calls[1]["text"])

    def test_notrack_missing_configuration_falls_back_to_ollama(self):
        status, body = self.post({"target": "notrack_ollama", "text": "Question", "allow_external": True})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "fallback_complete")
        self.assertEqual(body["results"][0]["error"], "notrack_not_configured_on_core")
        self.assertEqual([c["target"] for c in FakeCore.chat_calls], ["ollama"])
        self.assertIn("NOTRACK INDISPONIBLE", FakeCore.chat_calls[0]["text"])

    def test_offline_ollama_cannot_be_green(self):
        FakeCore.offline = True
        status, body = self.post({"target": "ollama", "text": "Question"})
        self.assertEqual(status, 503)
        self.assertEqual(body["error"], "ollama_not_confirmed_by_core")
        self.assertEqual(FakeCore.chat_calls, [])

    def test_reject_oversized_prompt(self):
        status, body = self.post({"target": "ollama", "text": "X"*5000})
        self.assertEqual(status, 400)
        self.assertEqual(FakeCore.chat_calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
