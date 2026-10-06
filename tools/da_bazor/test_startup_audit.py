import unittest
from startup_audit import looks_bazor, record, sanitized

class StartupAuditTests(unittest.TestCase):
    def test_detects_named_bazor_without_catching_other_apps(self):
        self.assertTrue(looks_bazor('BAZOR_AUTOPILOT_V6'))
        self.assertTrue(looks_bazor('C:/Users/test/BazorAIROOM/app.py'))
        self.assertTrue(looks_bazor('Wii AI Bridge'))
        self.assertFalse(looks_bazor('Ollama'))
        self.assertFalse(looks_bazor('Epic Games Launcher'))

    def test_public_report_excludes_commands_and_paths(self):
        entry = record('REGISTRY', 'BAZOR', 'PRÉSENT', {'command': r'C:\private\secret-token\bazor.exe'})
        report = sanitized([entry], ['TASKS_PARTIEL'])
        self.assertIn('COVERAGE: PARTIAL', report)
        self.assertNotIn('secret-token', report)
        self.assertNotIn('C:\\', report)
        self.assertIn('CHANGES: ZERO', report)
        self.assertIn('REBOOT_VERIFIED: NO', report)

if __name__ == '__main__':
    unittest.main()
