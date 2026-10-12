"""Offline, side-effect-free checks for GitHub queue -> Ollama receipt metadata."""
import ast
import json
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

WATCHER = Path(__file__).resolve().parents[1] / "pc-relay" / "bazor_github_watcher.py"


def functions_without_running_watcher():
    source = WATCHER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(WATCHER))  # parses the FULL watcher
    selected = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in ("ollama_queue_receipt", "core_chat")
    ]
    if len(selected) != 2:
        raise AssertionError("Required functions missing from watcher")
    scope = {
        "MARK": "[BAZOR-WATCHER-DONE]",
        "answer_text": lambda r: str((r.get("ollama") or {}).get("answer") or (r.get("ollama") or {}).get("error") or ""),
        "json": json,
        "urllib": __import__("urllib"),
        "CORE": "http://127.0.0.1:8775/api/v1/chat",
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(WATCHER), "exec"), scope)
    return scope


class QueueReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = functions_without_running_watcher()

    def test_true_proof_and_model_not_model_self_claim(self):
        response = {
            "ok": True, "target": "ollama",
            "ollama": {"ok": True, "provider": "ollama", "model": "qwen3:8b", "answer": "Je suis Claude."}
        }
        receipt = self.scope["ollama_queue_receipt"](response, 184, "qwen3:8b")
        self.assertIn("STATUS: MODEL_RESPONSE_RECEIVED", receipt)
        self.assertIn("MODEL_FROM_CORE: qwen3:8b", receipt)
        self.assertIn("MODEL_MATCH: true", receipt)

    def test_missing_model_is_blocked(self):
        resp = {"ok": True, "target": "ollama", "ollama": {"ok": True, "provider": "ollama", "answer": "Bonjour"}}
        self.assertIn("STATUS: BLOCKED", self.scope["ollama_queue_receipt"](resp, 184))

    def test_provider_error_is_blocked(self):
        resp = {"ok": True, "target": "ollama", "ollama": {"ok": False, "error": "ollama_offline"}}
        self.assertIn("PROVIDER_OK: false", self.scope["ollama_queue_receipt"](resp, 184))

    def test_wrong_model_is_flagged(self):
        resp = {"ok": True, "target": "ollama", "ollama": {"ok": True, "provider": "ollama", "model": "llama3.2:3b", "answer": "Bonjour"}}
        self.assertIn("MODEL_MATCH: false", self.scope["ollama_queue_receipt"](resp, 184, "qwen3:8b"))

    def test_long_answer_is_bounded(self):
        resp = {"ok": True, "target": "ollama", "ollama": {"ok": True, "provider": "ollama", "model": "qwen3:8b", "answer": "x" * 30000}}
        self.assertIn("[TRONQUE:", self.scope["ollama_queue_receipt"](resp, 184))

    def test_core_receives_requested_model(self):
        observed = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"ok":true,"target":"ollama","ollama":{"ok":true,"model":"qwen3:8b"}}'

        def fake_open(req, timeout=180):
            observed.append(json.loads(req.data))
            return Response()

        with patch("urllib.request.urlopen", side_effect=fake_open):
            self.scope["core_chat"]("Propose un scenario", model="qwen3:8b")
            self.scope["core_chat"]("Bonjour")
        self.assertEqual(observed[0]["model"], "qwen3:8b")
        self.assertNotIn("model", observed[1])
        self.assertEqual(observed[0]["target"], "ollama")


if __name__ == "__main__":
    unittest.main()
