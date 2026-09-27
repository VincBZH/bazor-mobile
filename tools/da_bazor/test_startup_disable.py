import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from startup_disable import EXPECTED, apply, planned, restore

class StartupDisableTests(unittest.TestCase):
    def test_refuses_changed_or_extra_entry(self):
        prior = [{'kind': kind, 'id': code, 'status': 'CONFIGURÉ', 'private': {}} for kind, code in EXPECTED]
        self.assertEqual(len(planned(prior, prior)), 4)
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_CHANGED'):
            planned(prior + [{'kind': 'STARTUP_FOLDER', 'id': 'extra', 'status': 'PRÉSENT'}], prior)

    def test_moves_only_two_shortcuts_and_restores_on_failure(self):
        with TemporaryDirectory() as base:
            root = Path(base)
            names = [code for kind, code in EXPECTED if kind == 'STARTUP_FOLDER']
            files = []
            for name in names:
                file = root / (name + '.lnk')
                file.write_text('fake shortcut')
                files.append(file)
            # Test transaction engine against controlled synthetic entries.
            from startup_disable import digest, atomic_json
            folder = root / 'backup'
            folder.mkdir()
            entries = []
            for n, file in enumerate(files):
                copy = folder / f'entry_{n}.bin'
                copy.write_bytes(file.read_bytes())
                entries.append({'id': names[n], 'kind': 'STARTUP_FOLDER', 'name': file.name,
                                'source': str(file), 'copy': copy.name,
                                'sha256': digest(file.read_bytes()), 'was_enabled': True})
            manifest = {'schema': 1, 'phase': 'BACKED_UP', 'records': entries}
            atomic_json(folder / 'manifest.json', manifest)
            apply(manifest, folder, change=lambda *_: self.fail('task called'))
            self.assertTrue(all(not file.exists() for file in files))
            restore(manifest, folder, change=lambda *_: self.fail('task called'))
            self.assertTrue(all(file.read_text() == 'fake shortcut' for file in files))

    def test_partial_failure_restores_disabled_task_and_moved_shortcut(self):
        with TemporaryDirectory() as base:
            root = Path(base)
            from startup_disable import digest, atomic_json
            folder = root / 'backup'
            folder.mkdir()
            task = root / 'task.xml'
            task.write_text('<Task><Settings><Enabled>true</Enabled></Settings></Task>')
            shortcut = root / 'BAZOR.lnk'
            shortcut.write_bytes(b'local shortcut')
            failed = root / 'second_task.xml'
            failed.write_text('<Task><Settings><Enabled>true</Enabled></Settings></Task>')
            entries = []
            for n, (kind, path) in enumerate((('SCHEDULED_TASK', task),
                                              ('STARTUP_FOLDER', shortcut),
                                              ('SCHEDULED_TASK', failed))):
                copy = folder / f'entry_{n}.bin'
                raw = path.read_bytes()
                copy.write_bytes(raw)
                entries.append({'id': str(n), 'kind': kind, 'name': path.name,
                                'source': str(path), 'copy': copy.name,
                                'sha256': digest(raw), 'was_enabled': True})
            manifest = {'schema': 1, 'phase': 'BACKED_UP', 'records': entries}
            atomic_json(folder / 'manifest.json', manifest)
            def change(name, enabled):
                if name == failed.name and not enabled:
                    raise RuntimeError('injected task failure')
                task.write_text(f'<Task><Settings><Enabled>{str(enabled).lower()}</Enabled></Settings></Task>')
            with self.assertRaisesRegex(RuntimeError, 'injected task failure'):
                apply(manifest, folder, change=change)
            self.assertTrue(shortcut.exists())
            self.assertTrue(task.read_text().find('<Enabled>true</Enabled>') > -1)
            self.assertEqual(json.loads((folder / 'manifest.json').read_text())['phase'], 'RESTORED')

if __name__ == '__main__':
    unittest.main()
