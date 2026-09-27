"""Offline tests for read-only BAZOR compatibility preflight. No network or paid API."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_compat_preflight as pre


class CompatibilityPreflightTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        self.core = self.root / "BAZOR" / "Core"
        self.room = self.root / "BazorAIROOM"
        self.core.mkdir(parents=True)
        self.room.mkdir(parents=True)
        (self.core / "DEMARRER_BAZOR_PC_RELAY.cmd").write_text("@echo off\n", encoding="utf-8")
        (self.room / "DEMARRER_BAZOR_AI_ROOM.cmd").write_text("@echo off\n", encoding="utf-8")
        for name in ("chat_history.json", "control.json", "projects.json", "state.json"):
            (self.room / name).write_text("{}", encoding="utf-8")

    def backup(self, missing=()):
        path = self.root / "BAZOR" / "Backups" / "PRE_MULTI_IA_test.zip"
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as zipped:
            for name in pre.CRITICAL_BACKUP:
                if name in missing:
                    continue
                label, filename = name.split("/", 1)
                source = (self.core if label == "Core" else self.room) / filename
                zipped.write(source, arcname=name)
        return path

    def stage(self, bad_python=False):
        folder = self.root / "BAZOR" / "Staging" / "multiia_v24_test"
        for file in pre.REQUIRED_STAGE:
            path = folder / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("def certification_reply_ok(value):\n    return bool(value)\n"
                            if file.endswith("bazor_bridge.py") else "pass\n", encoding="utf-8")
        if bad_python:
            (folder / "pc-relay" / "bad.py").write_text("def broken(:", encoding="utf-8")
        return folder

    def test_backup_restore_to_temporary_only(self):
        archive = self.backup()
        original = (self.room / "control.json").read_bytes()
        report = pre.restore_test(archive, self.root / "BAZOR" / "Reports", self.core, self.room)
        self.assertEqual(report["backup"], "RESTORE_SIMULATED")
        self.assertEqual(report["entries"], len(pre.CRITICAL_BACKUP))
        self.assertFalse(report["live_data_drift"])
        self.assertEqual((self.room / "control.json").read_bytes(), original)
        self.assertEqual(list((self.root / "BAZOR" / "Reports").glob("bazor_restore_*")), [])

    def test_modified_live_data_blocks_gate(self):
        archive = self.backup()
        (self.room / "control.json").write_text('{"changed": true}', encoding="utf-8")
        report = pre.restore_test(archive, self.root / "BAZOR" / "Reports", self.core, self.room)
        self.assertEqual(report["backup"], "RESTORE_SIMULATED")
        self.assertTrue(report["live_data_drift"])

    def test_missing_critical_file_invalidates_backup(self):
        archive = self.backup(missing=("AI_Room/chat_history.json",))
        report = pre.restore_test(archive, self.root / "BAZOR" / "Reports", self.core, self.room)
        self.assertEqual(report["backup"], "INVALID")

    def test_rejects_zip_slip_and_symlink(self):
        self.assertFalse(pre.safe_member(zipfile.ZipInfo("../private.txt")))
        self.assertFalse(pre.safe_member(zipfile.ZipInfo("C:/private.txt")))
        self.assertFalse(pre.safe_member(zipfile.ZipInfo("folder\\private.txt")))
        self.assertFalse(pre.safe_member(zipfile.ZipInfo("/etc/passwd")))
        info = zipfile.ZipInfo("AI_Room/danger")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.assertFalse(pre.safe_member(info))

    def test_zip_slip_never_writes_file(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            for member in pre.CRITICAL_BACKUP:
                zipped.writestr(member, "{}")
            zipped.writestr("../private.txt", "do not extract")
        result = pre.restore_test(archive, self.root / "reports", self.core, self.room)
        self.assertEqual(result["backup"], "INVALID")
        self.assertFalse((self.root / "private.txt").exists())

    def test_stage_identification_and_syntax(self):
        stage = self.stage()
        digest = pre.sha16(stage / pre.REQUIRED_STAGE[0])
        report = pre.stage_test(stage, expected_hash=digest)
        self.assertEqual(report["stage"], "OK")
        self.assertEqual(report["syntax_errors"], 0)
        self.assertEqual(pre.stage_test(stage)["stage"], "PATCH_MISMATCH")

    def test_stage_syntax_error_blocks(self):
        stage = self.stage(bad_python=True)
        report = pre.stage_test(stage, expected_hash=pre.sha16(stage / pre.REQUIRED_STAGE[0]))
        self.assertEqual(report["stage"], "SYNTAX_ERRORS")
        self.assertEqual(report["syntax_errors"], 1)

    def test_invalid_private_json_detected_without_contents(self):
        (self.room / "projects.json").write_text('{"PRIVATE_TOKEN":', encoding="utf-8")
        report = pre.json_files_test(self.room)
        self.assertEqual(report["projects.json"], "INVALID")
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(report))

    def test_public_output_does_not_reflect_untrusted_paths_or_tokens(self):
        private = r"C:\Users\someone\secret\TOKEN=LEAK_ME"
        report = {
            "gate": "BLOCKED", "stage": {"stage": private, "python_files": 1,
                "syntax_errors": 0, "patch_hash16": private},
            "restore": {"backup": "INVALID", "entries": 12, "live_data_drift": False},
            "health": {"core_8775": private, "room_8765": "RESPONDS",
                       "ollama_11434": "HAS_MODELS"},
        }
        output = pre.public_summary(report)
        self.assertNotIn("LEAK_ME", output)
        self.assertNotIn("someone", output)
        self.assertNotIn("TOKEN", output)
        self.assertIn("RUNTIME_CERTIFIED: NO", output)

    def test_json_data_and_installed_files_preserved(self):
        archive = self.backup()
        stage = self.stage()
        before = {x: x.read_bytes() for x in (
            self.core / "DEMARRER_BAZOR_PC_RELAY.cmd",
            self.room / "chat_history.json",
            self.room / "projects.json",
        )}
        # Prevent test from performing network: fixed fake local states.
        old_probe = pre.probe
        pre.probe = lambda url, models=False: "HAS_MODELS" if models else "RESPONDS"
        try:
            report = pre.audit(self.root, stage, archive,
                               expected_hash=pre.sha16(stage / pre.REQUIRED_STAGE[0]))
        finally:
            pre.probe = old_probe
        self.assertEqual(report["gate"], "READY_FOR_ISOLATED_TEST")
        self.assertFalse(report["runtime_certified"])
        self.assertEqual(report["deployment"], "NEVER_PERFORMED")
        self.assertTrue(all(x.read_bytes() == data for x, data in before.items()))


if __name__ == "__main__":
    unittest.main()
