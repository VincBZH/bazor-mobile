"""Tests isolés : pas de requêtes réseau, aucun service démarré."""
import importlib.util
import pathlib
import socket
import sys
import unittest
import urllib.error

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "console-hub"))
from bazor_diagnostics import CORE, OLLAMA, ROOM, ROOM_CHAT, ROOM_LINK, State, diagnose, test_local_chat


class FakeClient:
    def __init__(self, overrides=None):
        self.calls = []
        self.responses = {
            CORE: (200, {"ok": True, "ollama": {"online": True}}),
            ROOM: (200, {"ok": True, "version": "3.1.0-beta.1"}),
            ROOM_LINK: (200, {"core": True, "ollama": True}),
            OLLAMA: (200, {"models": [{"name": "llama3.2:3b"}]}),
            ROOM_CHAT: (200, {"ok": True, "answer": "BAZOR_OK"}),
        }
        if overrides:
            self.responses.update(overrides)

    def request(self, url, data=None):
        self.calls.append((url, data))
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


class DiagnosticsTests(unittest.TestCase):
    def test_all_gets_green_without_post(self):
        fake = FakeClient()
        report = diagnose(fake)
        self.assertEqual(report["overall"].state, State.GREEN)
        self.assertEqual(len(fake.calls), 4)
        self.assertTrue(all(data is None for _, data in fake.calls))

    def test_core_explicit_false_is_red(self):
        self.assertEqual(diagnose(FakeClient({CORE: (200, {"ok": False})}))["core"].state, State.RED)

    def test_core_unknown_schema_is_yellow(self):
        self.assertEqual(diagnose(FakeClient({CORE: (200, {"unexpected": 1})}))["core"].state, State.YELLOW)

    def test_core_ollama_offline_is_partial(self):
        self.assertEqual(diagnose(FakeClient({CORE: (200, {"ok": True, "ollama": {"online": False}})}))["core"].state, State.YELLOW)

    def test_room_false_is_red(self):
        self.assertEqual(diagnose(FakeClient({ROOM: (200, {"ok": False})}))["room"].state, State.RED)

    def test_room_missing_ok_is_yellow(self):
        self.assertEqual(diagnose(FakeClient({ROOM: (200, {"status": "ok"})}))["room"].state, State.YELLOW)

    def test_ollama_empty_models_is_yellow(self):
        self.assertEqual(diagnose(FakeClient({OLLAMA: (200, {"models": []})}))["ollama"].state, State.YELLOW)

    def test_ollama_bad_schema_is_yellow(self):
        self.assertEqual(diagnose(FakeClient({OLLAMA: (200, {"models": {}})}))["ollama"].state, State.YELLOW)

    def test_ollama_http_500_returns_red_not_crash(self):
        e = urllib.error.HTTPError(OLLAMA, 500, "server", {}, None)
        self.assertEqual(diagnose(FakeClient({OLLAMA: e}))["ollama"].state, State.RED)

    def test_link_not_green_if_core_red_despite_declared_ready(self):
        report = diagnose(FakeClient({CORE: (200, {"ok": False})}))
        self.assertEqual(report["core"].state, State.RED)
        self.assertEqual(report["link"].state, State.YELLOW)

    def test_link_missing_dependency_is_yellow(self):
        self.assertEqual(diagnose(FakeClient({ROOM_LINK: (200, {"core": True, "ollama": False})}))["link"].state, State.YELLOW)

    def test_link_missing_fields_is_yellow(self):
        self.assertEqual(diagnose(FakeClient({ROOM_LINK: (200, {"ok": True})}))["link"].state, State.YELLOW)

    def test_link_http_404_is_partial_not_room_down(self):
        result = diagnose(FakeClient({ROOM_LINK: (404, {})}))
        self.assertEqual(result["room"].state, State.GREEN)
        self.assertEqual(result["link"].state, State.YELLOW)

    def test_room_down_skips_link(self):
        fake = FakeClient({ROOM: urllib.error.URLError("connection refused")})
        self.assertEqual(diagnose(fake)["link"].state, State.GRAY)
        self.assertNotIn(ROOM_LINK, [url for url, _ in fake.calls])

    def test_probe_exception_gray(self):
        self.assertEqual(diagnose(FakeClient({CORE: ValueError("unexpected") }))["core"].state, State.GRAY)

    def test_chat_explicit_post_success(self):
        fake = FakeClient()
        self.assertEqual(test_local_chat(fake).state, State.GREEN)
        self.assertEqual(fake.calls, [(ROOM_CHAT, {"text": "Réponds uniquement BAZOR_OK"})])

    def test_chat_explicit_post_other_text_yellow(self):
        self.assertEqual(test_local_chat(FakeClient({ROOM_CHAT: (200, {"ok": True, "answer": "bonjour"})})).state, State.YELLOW)

    def test_chat_explicit_post_unconfirmed_red(self):
        self.assertEqual(test_local_chat(FakeClient({ROOM_CHAT: (200, {"ok": False, "answer": "BAZOR_OK"})})).state, State.RED)

    def test_chat_http_500_red(self):
        e = urllib.error.HTTPError(ROOM_CHAT, 500, "server", {}, None)
        self.assertEqual(test_local_chat(FakeClient({ROOM_CHAT: e})).state, State.RED)

    def test_chat_missing_answer_yellow(self):
        self.assertEqual(test_local_chat(FakeClient({ROOM_CHAT: (200, {"ok": True})})).state, State.YELLOW)


if __name__ == "__main__":
    unittest.main()
