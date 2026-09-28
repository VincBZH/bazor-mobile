import unittest

import bazor_live_readiness as live


class Identity:
    def __init__(self, component, pid, port, owned=True, sha="a"*64):
        self.component = component
        self.pid = pid
        self.port = port
        self.owned_by_current_user = owned
        self.executable_sha256 = sha


class LiveReadinessTests(unittest.TestCase):
    def test_room_uses_real_v24_status_endpoint(self):
        self.assertEqual(live.SPECS["room"].health_path, "/api/status")
        self.assertNotEqual(live.SPECS["room"].health_path, "/health")

    def test_valid_identity_requires_owner_port_and_sha(self):
        self.assertEqual(
            live._identity_state(Identity("core", 42, 8775), "core", 8775), "OK")
        self.assertEqual(
            live._identity_state(Identity("core", 42, 8775, owned=False), "core", 8775),
            "BLOCKED")
        self.assertEqual(
            live._identity_state(Identity("core", 42, 9999), "core", 8775), "BLOCKED")
        self.assertEqual(
            live._identity_state(Identity("core", 42, 8775, sha="short"), "core", 8775),
            "BLOCKED")

    def test_readiness_needs_every_gate(self):
        pre = {"gate": "READY_FOR_ISOLATED_TEST"}
        self.assertEqual(
            live.decide(pre, "OK", "OK", "HAS_MODELS", "nt"),
            "READY_FOR_AUTHORIZATION_REVIEW")
        for args in (
            ({"gate": "BLOCKED"}, "OK", "OK", "HAS_MODELS", "nt"),
            (pre, "BLOCKED", "OK", "HAS_MODELS", "nt"),
            (pre, "OK", "BLOCKED", "HAS_MODELS", "nt"),
            (pre, "OK", "OK", "NO_MODELS", "nt"),
            (pre, "OK", "OK", "HAS_MODELS", "posix"),
        ):
            self.assertNotEqual(live.decide(*args), "READY_FOR_AUTHORIZATION_REVIEW")

    def test_public_summary_never_leaks_local_identity(self):
        report = {
            "platform": "WINDOWS",
            "preflight_gate": "READY_FOR_ISOLATED_TEST",
            "core_identity": "OK",
            "room_identity": "OK",
            "ollama": "HAS_MODELS",
            "readiness": "READY_FOR_AUTHORIZATION_REVIEW",
            "local_identity": {"core": {"pid": 123, "executable_sha256": "secret"}},
        }
        text = live.public_summary(report)
        self.assertIn("READINESS: READY_FOR_AUTHORIZATION_REVIEW", text)
        self.assertNotIn("123", text)
        self.assertNotIn("secret", text)
        self.assertIn("PROCESS_MUTATION: DISABLED", text)
        self.assertIn("AUTHORIZATION_ISSUED: NO", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
