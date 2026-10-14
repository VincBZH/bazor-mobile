"""Regression guard: a verified one-shot Ollama smoke must not trigger autochain blocked.

Parse source as text because importing the Watcher starts its polling loop.
"""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "bazor_github_watcher.py"

class TestOneShotAutohain(unittest.TestCase):
    def test_ollama_smoke_normal_terminal(self):
        source = SOURCE.read_text(encoding="utf-8")
        guard = 'if not is_last and str(task_id).upper() != "BAZOR-OLLAMA-LOCAL-SMOKE-001":'
        self.assertEqual(source.count(guard), 1)
        pos = source.index(guard)
        self.assertIn("[BAZOR-AUTOCHAIN-BLOCKED]", source[pos:pos+500])

    def test_other_tasks_still_report_blocking(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("Aucune étape suivante autorisée.", source)
        self.assertIn("DEFAULT_RECOVERY requis", source)

if __name__=="__main__":
    unittest.main()
