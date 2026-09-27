import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from da_bazor import checkpoint, inspect, local_answer, report

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

if __name__ == '__main__':
    unittest.main()
