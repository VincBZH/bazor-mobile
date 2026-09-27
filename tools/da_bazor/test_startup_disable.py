import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import uuid
import xml.etree.ElementTree as ET

from startup_disable import EXPECTED, apply, planned, restore, task_change, task_enabled, task_definition_signature

class StartupDisableTests(unittest.TestCase):
    def test_refuses_changed_or_extra_entry(self):
        prior = [{'kind': kind, 'id': code, 'status': 'CONFIGURÉ', 'private': {}} for kind, code in EXPECTED]
        self.assertEqual(len(planned(prior, prior)), 4)
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_CHANGED'):
            planned(prior + [{'kind': 'STARTUP_FOLDER', 'id': 'extra', 'status': 'PRÉSENT'}], prior)

    def test_task_action_change_is_detected(self):
        first = b'<Task><Triggers><CalendarTrigger/></Triggers><Actions><Exec><Command>one.exe</Command></Exec></Actions></Task>'
        second = first.replace(b'one.exe', b'two.exe')
        self.assertNotEqual(task_definition_signature(first), task_definition_signature(second))

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
            task.write_text('<Task><Settings><Enabled>true</Enabled></Settings><Actions><Exec><Command>safe.exe</Command></Exec></Actions></Task>')
            shortcut = root / 'BAZOR.lnk'
            shortcut.write_bytes(b'local shortcut')
            failed = root / 'second_task.xml'
            failed.write_text('<Task><Settings><Enabled>true</Enabled></Settings><Actions><Exec><Command>safe.exe</Command></Exec></Actions></Task>')
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
                task.write_text(f'<Task><Settings><Enabled>{str(enabled).lower()}</Enabled></Settings><Actions><Exec><Command>safe.exe</Command></Exec></Actions></Task>')
            with self.assertRaisesRegex(RuntimeError, 'injected task failure'):
                apply(manifest, folder, change=change)
            self.assertTrue(shortcut.exists())
            self.assertTrue(task.read_text().find('<Enabled>true</Enabled>') > -1)
            self.assertEqual(json.loads((folder / 'manifest.json').read_text())['phase'], 'RESTORED')

    @unittest.skipUnless(sys.platform == 'win32' and os.getenv('GITHUB_ACTIONS') == 'true',
                         'Disposable scheduled-task integration runs only on Windows CI')
    def test_real_windows_scheduler_disable_enable_on_disposable_task(self):
        name = '\\BAZOR_CI_' + uuid.uuid4().hex[:12]
        path = Path(os.environ['SystemRoot']) / 'System32' / 'Tasks' / name.lstrip('\\')
        created = False
        try:
            subprocess.run(['schtasks.exe', '/Create', '/TN', name, '/TR', 'cmd.exe /c exit 0',
                            '/SC', 'DAILY', '/ST', '23:59', '/F'],
                           check=True, capture_output=True, timeout=20)
            created = True
            before = path.read_bytes()
            self.assertTrue(task_enabled(path))
            task_change(name, False)
            self.assertFalse(task_enabled(path))
            after = path.read_bytes()
            if task_definition_signature(before) != task_definition_signature(after):
                def fields(raw):
                    found = {}
                    def visit(node, route):
                        key = route + '/' + node.tag.rsplit('}', 1)[-1]
                        found[key] = (tuple(sorted(node.attrib)), (node.text or '').strip())
                        for child in node:
                            visit(child, key)
                    visit(ET.fromstring(raw), '')
                    return found
                left, right = fields(before), fields(after)
                changed = sorted(k for k in left.keys() | right.keys() if left.get(k) != right.get(k))
                print('Disposable task XML changed fields:', changed)
            self.assertEqual(task_definition_signature(before), task_definition_signature(after))
            task_change(name, True)
            self.assertTrue(task_enabled(path))
        finally:
            if created:
                subprocess.run(['schtasks.exe', '/Delete', '/TN', name, '/F'],
                               capture_output=True, timeout=20)

if __name__ == '__main__':
    unittest.main()
