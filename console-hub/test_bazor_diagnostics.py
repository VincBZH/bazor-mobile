"""Tests unitaires sans service reel ni depense API."""
import importlib.util
import pathlib
import urllib.error
import unittest

spec = importlib.util.spec_from_file_location("bazor_diag", pathlib.Path(__file__).with_name("bazor_diagnostics.py"))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

class DiagnosticsTests(unittest.TestCase):
    def test_core_signature(self):
        row, data = d.probe("core", "http://127.0.0.1:8775/api/v1/health", "core",
                            lambda _: (200, {"ok": True, "service": "BAZOR API", "mammouth": {"configured": True}}))
        self.assertEqual(row["etat"], "VERT")
        self.assertTrue(data["mammouth"]["configured"])
    def test_html_or_wrong_service_not_green(self):
        row, _ = d.probe("room", "http://127.0.0.1:8765/api/status", "room",
                         lambda _: (200, {"ok": True, "service": "BAZOR API"}))
        self.assertEqual(row["etat"], "JAUNE")
    def test_empty_models_not_green(self):
        row, _ = d.probe("ollama", "http://127.0.0.1:11434/api/tags", "ollama",
                         lambda _: (200, {"models": []}))
        self.assertEqual(row["etat"], "JAUNE")
    def test_404_not_green(self):
        def missing(_):
            raise urllib.error.HTTPError("http://127.0.0.1", 404, "missing", None, None)
        row, _ = d.probe("core", "http://127.0.0.1", "core", missing)
        self.assertEqual(row["etat"], "JAUNE")
    def test_no_connection_not_green(self):
        def missing(_):
            raise urllib.error.URLError("refused")
        row, _ = d.probe("core", "http://127.0.0.1", "core", missing)
        self.assertEqual(row["etat"], "GRIS")
    def test_no_automated_provider_call(self):
        requested = []
        def fake(url):
            requested.append(url)
            if ":8775/" in url:
                return 200, {"ok": True, "service": "BAZOR API", "mammouth": {"configured": True}}
            if ":11434/" in url:
                return 200, {"models": [{"name": "qwen2.5-coder:7b"}]}
            return 404, {}
        rows = d.build_report(fake)
        self.assertEqual(len(requested), len(d.CHECKS))
        self.assertTrue(all("127.0.0.1" in u for u in requested))
        self.assertEqual(next(r for r in rows if r["service"] == "Mammouth API")["etat"], "JAUNE")
        self.assertEqual(next(r for r in rows if r["service"] == "Ollama -> Mammouth -> Ollama")["etat"], "GRIS")

if __name__ == "__main__":
    unittest.main(verbosity=2)
