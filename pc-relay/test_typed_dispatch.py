"""Closed-vocabulary typed dispatcher tests; does not connect to GitHub."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).parent))

from bazor_action_policy import DiagnosticGate
from bazor_typed_dispatch import TypedDispatcher


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.unlocked = True
        self.now = 0.0
        self.gate = DiagnosticGate(lambda: True, lambda: self.unlocked,
                                   lambda: self.now)
        self.count = 0
        def run():
            self.count += 1
            return "OK"
        self.dispatch = TypedDispatcher(self.gate, {"ETAT_SERVICES": run})

    def test_no_hello_refuses_even_trusted_owner(self):
        out = self.dispatch.execute("ETAT_SERVICES",
                                    trusted_origin="verified_github_owner")
        self.assertEqual(out.code, "BLOCKED")
        self.assertEqual(self.count, 0)

    def test_hello_scoped_verified_owner_read_only(self):
        self.gate.enable_from_local_ui({"ETAT_SERVICES"})
        out = self.dispatch.execute("ETAT_SERVICES",
                                    trusted_origin="verified_github_owner")
        self.assertEqual(out.code, "OK")
        self.assertEqual(self.count, 1)
        self.assertNotIn("session_id", out.public_report())

    def test_untrusted_github_comment_cannot_invoke(self):
        self.gate.enable_from_local_ui({"ETAT_SERVICES"})
        out = self.dispatch.execute("ETAT_SERVICES", trusted_origin="github")
        self.assertEqual(out.code, "BLOCKED")
        self.assertEqual(self.count, 0)

    def test_arbitrary_shell_never_registered(self):
        with self.assertRaises(ValueError):
            TypedDispatcher(self.gate, {"POWERSHELL": lambda: "OK"})
        self.gate.enable_from_local_ui({"ETAT_SERVICES"})
        out = self.dispatch.execute("POWERSHELL",
                                    trusted_origin="verified_github_owner")
        self.assertEqual(out.action, "DENIED")
        self.assertEqual(self.count, 0)

    def test_panic_during_action_blocks_success(self):
        def panic():
            self.gate.panic()
            return "OK"
        dispatcher = TypedDispatcher(self.gate, {"ETAT_SERVICES": panic})
        self.gate.enable_from_local_ui({"ETAT_SERVICES"})
        out = dispatcher.execute("ETAT_SERVICES", trusted_origin="local_ui")
        self.assertEqual(out.code, "BLOCKED")

    def test_expiry_during_action_blocks_success(self):
        def expire():
            self.now += 901
            return "OK"
        dispatcher = TypedDispatcher(self.gate, {"ETAT_SERVICES": expire})
        self.gate.enable_from_local_ui({"ETAT_SERVICES"})
        out = dispatcher.execute("ETAT_SERVICES", trusted_origin="local_ui")
        self.assertEqual(out.code, "BLOCKED")

    def test_status_reflected_only_from_allowlist(self):
        self.gate.enable_from_local_ui({"ETAT_SERVICES"})
        dispatcher = TypedDispatcher(self.gate, {"ETAT_SERVICES": lambda: "API_KEY=SECRET"})
        out = dispatcher.execute("ETAT_SERVICES", trusted_origin="local_ui")
        self.assertEqual(out.code, "BLOCKED")
        self.assertNotIn("SECRET", out.public_report())


if __name__ == "__main__":
    unittest.main()
