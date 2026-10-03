import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from da_bazor import checkpoint, inspect, local_answer, report, allowed_destination
from create_desktop_launcher import launcher_content

class DaBazorTests(unittest.TestCase):
    def test_http_200_false_is_not_green(self):
        def probe(url):
            if url.endswith('/api/tags'):
                return {'models': []}
            return {'ok': False}
        state = inspect(probe)
        self.assertEqual(state['ollama'], 'AUCUN_MODÈLE')
        self.assertEqual(state['core'], 'ÉCHEC_DÉCLARÉ')
        self.assertEqual(state['room'], 'ÉCHEC_DÉCLARÉ')

    def test_room_probe_uses_v24_status_endpoint(self):
        urls = []
        def probe(url):
            urls.append(url)
            if url.endswith('/api/tags'):
                return {'models': []}
            return {'ok': True}
        inspect(probe)
        self.assertIn('http://127.0.0.1:8765/api/status', urls)
        self.assertNotIn('http://127.0.0.1:8765/health', urls)

    def test_fallback_uses_distinct_local_model(self):
        calls = []
        def sender(prompt, model):
            calls.append(model)
            if model == 'llama3.2:3b':
                raise TimeoutError()
            return 'réponse'
        model, answer = local_answer('salut', ['llama3.2:3b', 'qwen2.5-coder:7b'], sender)
        self.assertEqual((model, answer), ('qwen2.5-coder:7b', 'réponse'))
        self.assertEqual(calls, ['llama3.2:3b', 'qwen2.5-coder:7b'])

    def test_no_false_delivery(self):
        state = inspect(lambda url: {'models': [{'name': 'llama3.2:3b'}]} if url.endswith('/api/tags') else {'ok': True})
        self.assertIn('aucun livrable certifié', report(state))
        self.assertEqual(local_answer('x', ['autre'], lambda q, m: 'non')[0], 'BLOQUÉ')

    def test_checkpoint_keeps_delivery_blocked_even_when_services_respond(self):
        state = {'ollama': 'MODÈLES_DISPONIBLES', 'models': ['llama3.2:3b'],
                 'core': 'SONDE_OK_SEULEMENT', 'room': 'SONDE_OK_SEULEMENT'}
        with TemporaryDirectory() as folder:
            result = checkpoint(state, Path(folder))
            self.assertEqual(result['projects'][1]['diagnostic'], 'SONDES_LOCALES_OK')
            self.assertTrue(all(x['delivery'] == 'NON_CERTIFIÉ' for x in result['projects']))
            self.assertEqual(json.loads((Path(folder) / 'checkpoint.json').read_text())['external_paid_calls'], 0)

    def test_local_menu_opens_only_probed_allowlisted_destinations(self):
        state = inspect(lambda url: {'models': [{'name': 'llama3.2:3b'}]} if url.endswith('/api/tags') else {'ok': True},
                        lambda url: url.endswith('/system_stats'))
        self.assertEqual(allowed_destination('comfy', state), 'http://127.0.0.1:8188')
        self.assertIsNone(allowed_destination('studio', state))
        self.assertIsNone(allowed_destination('https://example.com', state))
        self.assertEqual(allowed_destination('room', state), 'http://127.0.0.1:8765')

    def test_failed_health_disables_navigation_even_when_http_200(self):
        state = inspect(lambda url: {'models': []} if url.endswith('/api/tags') else {'ok': False}, lambda url: False)
        self.assertIsNone(allowed_destination('room', state))
        self.assertIsNone(allowed_destination('core', state))

    def test_desktop_launcher_quotes_path_and_refuses_cmd_expansion(self):
        content = launcher_content(Path(r'C:\Program Files\Python\python.exe'), Path(r'C:\Users\Vincent\Da Bazor\da_bazor.py'))
        self.assertIn('"C:\\Program Files\\Python\\python.exe"', content)
        self.assertIn('"C:\\Users\\Vincent\\Da Bazor\\da_bazor.py"', content)
        with self.assertRaises(ValueError):
            launcher_content(Path(r'C:\Users\100%\python.exe'), Path(r'C:\Da Bazor\da_bazor.py'))

if __name__ == '__main__':
    unittest.main()
