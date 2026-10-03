"""Offline authorization policy tests. Native Hello and Windows lock need PC validation."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from bazor_action_policy import DiagnosticGate, PermissionDenied, SAFE_ACTIONS


class GateTests(unittest.TestCase):
    def setUp(self):
        self.t = 100.0
        self.unlocked = True
        self.hello = True
        self.prompts = 0
        def hello():
            self.prompts += 1
            return self.hello
        self.gate = DiagnosticGate(hello, lambda: self.unlocked, lambda: self.t)

    def authorize(self, actions=None):
        self.gate.enable_from_local_ui(actions or {"ETAT_SERVICES"})

    def test_disabled_by_default(self):
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))
        self.assertFalse(self.gate.public_status()["enabled"])

    def test_hello_required_and_not_just_checkbox(self):
        self.hello = False
        with self.assertRaises(PermissionDenied):
            self.authorize()
        self.assertEqual(self.prompts, 1)
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))

    def test_cancelled_hello_clears_old_session(self):
        self.authorize()
        self.hello = False
        with self.assertRaises(PermissionDenied):
            self.authorize()
        self.assertFalse(self.gate.enabled)

    def test_read_only_scopes(self):
        self.authorize({"AUDIT_LANCEURS", "ETAT_SERVICES"})
        self.assertTrue(self.gate.allow("ETAT_SERVICES"))
        self.assertTrue(self.gate.allow("AUDIT_LANCEURS"))
        self.assertFalse(self.gate.allow("AUDIT_APPROFONDI"))
        self.assertFalse(self.gate.allow("DEPLOY"))

    def test_all_remote_operations_denied_even_if_session_active(self):
        self.authorize(SAFE_ACTIONS)
        for origin in ("github", "comment", "api", "remote", ""):
            self.assertFalse(self.gate.allow("ETAT_SERVICES", origin=origin))
        self.assertFalse(self.gate.allow("SHELL"))
        self.assertFalse(self.gate.allow("OPENAI_API"))

    def test_verified_owner_diagnostic_requires_active_hello(self):
        self.assertFalse(self.gate.allow("ETAT_SERVICES", origin="verified_github_owner"))
        self.authorize({"ETAT_SERVICES"})
        self.assertTrue(self.gate.allow("ETAT_SERVICES", origin="verified_github_owner"))
        self.assertFalse(self.gate.allow("SHELL", origin="verified_github_owner"))
        self.gate.panic()
        self.assertFalse(self.gate.allow("ETAT_SERVICES", origin="verified_github_owner"))

    def test_unauthorized_scope_denies_before_hello(self):
        with self.assertRaises(PermissionDenied):
            self.authorize({"ETAT_SERVICES", "SHELL"})
        self.assertEqual(self.prompts, 0)

    def test_invalid_ttl_fails_closed(self):
        for ttl in (0, -5, 901, True, "900"):
            with self.subTest(ttl=ttl), self.assertRaises(PermissionDenied):
                self.gate.enable_from_local_ui({"ETAT_SERVICES"}, ttl)
        self.assertFalse(self.gate.enabled)

    def test_expires_and_stays_revoked(self):
        self.authorize()
        self.t += 900
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))
        self.t -= 900
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))

    def test_explicit_disable_is_immediate(self):
        self.authorize()
        self.gate.disable()
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))

    def test_windows_lock_revokes(self):
        self.authorize()
        self.unlocked = False
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))
        self.unlocked = True
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))

    def test_windows_lock_event_revokes(self):
        self.authorize()
        self.gate.on_windows_lock()
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))

    def test_panic_denies_all_new_actions(self):
        self.authorize()
        self.gate.panic()
        self.assertFalse(self.gate.allow("ETAT_SERVICES"))
        with self.assertRaises(PermissionDenied):
            self.authorize()
        self.gate.clear_panic_from_local_ui()
        self.assertFalse(self.gate.enabled)
        self.authorize()
        self.assertTrue(self.gate.allow("ETAT_SERVICES"))

    def test_hello_exception_denied_without_detail(self):
        gate = DiagnosticGate(lambda: 1/0, lambda: True)
        with self.assertRaises(PermissionDenied) as err:
            gate.enable_from_local_ui({"ETAT_SERVICES"})
        self.assertEqual(str(err.exception), "HELLO_DENIED")

    def test_status_never_exposes_token(self):
        self.authorize()
        status = self.gate.public_status()
        self.assertEqual(status["allowed_actions"], ["ETAT_SERVICES"])
        self.assertNotIn("session_id", status)
        self.assertFalse(status["paid_api"])
        self.assertFalse(status["deployment"])
        self.assertFalse(status["shell"])

    def test_empty_scopes_rejected(self):
        with self.assertRaises(PermissionDenied):
            self.gate.enable_from_local_ui(set())


if __name__ == "__main__":
    unittest.main()
