"""Tests du code sans créer une vraie fenêtre Tk sur un serveur CI headless."""
import ast
import pathlib
import sys
import types
import unittest

DIR = pathlib.Path(__file__).resolve().parents[1] / "console-hub"
sys.path.insert(0, str(DIR))

class DashboardTests(unittest.TestCase):
    def test_dashboard_source_compiles(self):
        source = (DIR / "bazor_ultimate_dashboard.py").read_text(encoding="utf-8")
        compile(source, str(DIR / "bazor_ultimate_dashboard.py"), "exec")

    def test_subclasses_existing_hub_without_launching_at_import(self):
        source = (DIR / "bazor_ultimate_dashboard.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(any(isinstance(n, ast.ClassDef) and n.name == "UltimateHub"
                            and any(isinstance(x, ast.Name) and x.id == "Hub" for x in n.bases)
                            for n in tree.body))
        self.assertTrue(any(isinstance(n, ast.If) and n.test
                            for n in tree.body))

    def test_manual_chat_button_is_separate_from_auto_refresh(self):
        source = (DIR / "bazor_ultimate_dashboard.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "UltimateHub")
        periodic = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_periodic_diagnostics")
        self.assertNotIn("test_local_chat", ast.unparse(periodic))
        worker = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_chat_worker")
        self.assertIn("test_local_chat", ast.unparse(worker))

if __name__ == "__main__":
    unittest.main()
