import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bazor_studio_observer as observer
import bazor_studio_trace_bridge as trace_bridge


class ObserverTests(unittest.TestCase):
    def test_public_trace_never_contains_private_content(self):
        private = "NomSabrinaConfidentiel secret-prompt-unique"
        report = {
            "phase": private, "task_id": private, "time": private, "watcher_head": private,
            "ports": [{"port": 8191, "command": private}],
            "studio_probes": {"/api/jobs": {"ok": True, "http": 200, "detail": private}},
            "studio_jobs": [{"status": "failed", "prompt": private, "output": private},
                            {"status": private, "prompt": private}],
            "comfy": {"recent": [{"status": "error", "nodes": [{"inputs": {"text": private}}],
                                   "outputs": [{"filename": private}]}]},
            "files": {"workflows.py": {"sha256": "a" * 64, "hits": [{"text": private}]}},
            "frontend_context": [{"lines": [{"text": private}]}],
            "logs": [{"name": private, "tail": private}],
            "task_diag": [{"body": private}],
        }
        published = trace_bridge._markdown(report)
        self.assertNotIn(private, published)
        self.assertNotIn("NomSabrina", published)
        self.assertNotIn("secret-prompt", published)
        self.assertIn('"studio_jobs_count": 2', published)
        self.assertIn('"failed": 1', published)
        self.assertIn('"other": 1', published)

    def test_existing_services_and_log_error_are_correlated_without_full_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            studio = root / "Studio"
            (studio / "logs").mkdir(parents=True)
            (studio / "logs" / "server.log").write_text(
                "2026-09-29 09:00 ERROR SaveVideo failed\n", encoding="utf-8"
            )
            jobs = [{"id": "j1", "prompt_id": "p1", "status": "failed", "params": {
                "prompt": "sk-TOKENEXAMPLE123456789 un paysage très détaillé avec une forêt, du vent et de la lumière",
                "width": 608, "height": 352, "frames": 124}}]
            history = {"p1": {"status": {"status_str": "error", "messages": [
                ["execution_error", {"exception_message": "SaveVideo: codec unavailable"}]
            ]}, "prompt": [0, "x", {"node": {"class_type": "MiniMaxH3ImageToVideo",
                    "inputs": {"width": 608, "height": 352, "length": 124,
                               "text": "sk-TOKENEXAMPLE123456789 un paysage très détaillé avec une forêt, du vent et de la lumière"}}}]}}
            with patch.object(observer, "request_json", side_effect=[(jobs, None), (history, None)]):
                result = observer.poll_once(root / "reports", studio, root / "Comfy")
            self.assertEqual(result["jobs"][0]["prompt_id"], result["history"][0]["prompt_id"])
            self.assertEqual(result["history"][0]["dimensions"][0]["width"], 608)
            self.assertIn("SaveVideo", result["console_errors"][0]["message"])
            stored = (root / "reports" / "latest.json").read_text(encoding="utf-8")
            self.assertNotIn("sk-TOKENEXAMPLE", stored)
            self.assertIn("<clé masquée>", stored)
            self.assertNotIn("de la lumière", stored)
            with patch.object(observer, "request_json", side_effect=[(jobs, None), (history, None)]):
                observer.poll_once(root / "reports", studio, root / "Comfy")
            events = (root / "reports" / "events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(events), 3, "Un deuxième passage identique ne duplique pas les événements")

    def test_absent_services_do_not_abort_report_and_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(observer, "request_json", side_effect=[(None, "connection refused"),
                                                                      (None, "connection refused")]), \
                 patch.object(observer, "probe_service", return_value=False):
                result = observer.poll_once(root / "out", root / "Studio", root / "Comfy")
            self.assertFalse(result["studio"]["reachable"])
            self.assertFalse(result["comfy"]["reachable"])
            self.assertTrue((root / "out" / "latest.json").is_file())
            self.assertIsNone(observer._safe_output(root / "Comfy", {
                "type": "output", "subfolder": "..", "filename": "private.png"
            }))


if __name__ == "__main__":
    unittest.main()
