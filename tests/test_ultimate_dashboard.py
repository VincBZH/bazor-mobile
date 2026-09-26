"""Tests du code sans créer une vraie fenêtre Tk sur un serveur CI headless."""
import ast
import importlib.util
import threading
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

class FakeWidget:
    def __init__(self, *args, **kwargs):
        self.options = kwargs.copy()
        self.callbacks = []

    def pack(self, *args, **kwargs):
        self.options["pack"] = kwargs

    def grid(self, *args, **kwargs):
        self.options["grid"] = kwargs

    def grid_columnconfigure(self, *args, **kwargs):
        pass

    def config(self, **kwargs):
        self.options.update(kwargs)

    def heading(self, name, **kwargs):
        self.options["heading_" + name] = kwargs

    def title(self, value):
        self.options["title"] = value

    def geometry(self, value):
        self.options["geometry"] = value

    def after(self, ms, callback):
        self.callbacks.append((ms, callback))


class FakeHub:
    def __init__(self, centralize=False):
        assert centralize is False
        self.root = FakeWidget()
        self.stop_evt = threading.Event()
        self.tree = FakeWidget()
        self.build_ui()

    def build_ui(self):
        self.tree = FakeWidget()


class DashboardWidgetTests(unittest.TestCase):
    def make_hub(self):
        fake_parent = types.ModuleType("bazor_console_hub")
        fake_parent.Hub = FakeHub
        original = sys.modules.get("bazor_console_hub")
        sys.modules["bazor_console_hub"] = fake_parent
        try:
            spec = importlib.util.spec_from_file_location("bazor_ultimate_fake_test", DIR / "bazor_ultimate_dashboard.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        finally:
            if original is None:
                del sys.modules["bazor_console_hub"]
            else:
                sys.modules["bazor_console_hub"] = original
        mod.tk = types.SimpleNamespace(LabelFrame=FakeWidget, Frame=FakeWidget, Label=FakeWidget)
        mod.ttk = types.SimpleNamespace(Button=FakeWidget)
        return mod, mod.UltimateHub()

    def test_panel_is_built_on_real_hub_subclass_shape(self):
        mod, hub = self.make_hub()
        self.assertEqual(set(hub.diag_labels), {"core", "room", "ollama", "link"})
        self.assertEqual(hub.tree.options["heading_status"]["text"], "ÉTAT HISTORIQUE (PORT)")
        self.assertEqual(hub.root.options["title"], "BAZOR ULTIMATE — Centre de contrôle")
        self.assertFalse(hub.diag_busy)
        self.assertFalse(hub.chat_busy)
        self.assertEqual(len(hub.root.callbacks), 3)

    def test_report_updates_all_widgets_without_network(self):
        from bazor_diagnostics import Check, State
        _, hub = self.make_hub()
        report = {k: Check(k, State.GREEN, "simulation OK") for k in ("core", "room", "ollama", "link", "overall")}
        hub._show_report(report)
        self.assertIn("VERT", hub.diag_summary.options["text"])
        self.assertTrue(all("simulation OK" in x.options["text"] for x in hub.diag_labels.values()))

    def test_chat_test_runs_only_after_explicit_click(self):
        from bazor_diagnostics import Check, State
        mod, hub = self.make_hub()
        calls = []
        mod.test_local_chat = lambda: calls.append("POST") or Check("Conversation", State.GREEN, "simulation BAZOR_OK")
        class SynchronousThread:
            def __init__(self, target, daemon):
                self.target = target
            def start(self):
                self.target()
        mod.threading = types.SimpleNamespace(Thread=SynchronousThread)
        self.assertEqual(calls, [])
        hub.start_chat_test()
        self.assertEqual(calls, ["POST"])
        hub._poll_diag_queue()
        self.assertIn("VERT", hub.chat_result.options["text"])
        self.assertFalse(hub.chat_busy)


if __name__ == "__main__":
    unittest.main()
