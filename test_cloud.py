"""Valida a entrada de hospedagem com bancos separados por sessão."""
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from sei.workspace import Workspace


class CloudTest(unittest.TestCase):
    def test_sessoes_isoladas_sem_preparacao(self):
        with patch('sei.training.treinar', side_effect=AssertionError('treino no deploy')), \
             patch('socket.create_connection', side_effect=AssertionError('rede no deploy')):
            a = AppTest.from_file('app_cloud.py', default_timeout=40).run()
            self.assertFalse(a.exception)
            pa = Path(a.session_state['_demo_directory'].name) / 'sei.db'
            store = Workspace(pa)
            self.assertEqual(len(store.get('plan')['cronograma']), 4)
            store.set('theme', 'dark')
            a.run()
            self.assertFalse(a.exception)
            self.assertEqual(a.session_state['_demo_directory'].name, str(pa.parent))
            b = AppTest.from_file('app_cloud.py', default_timeout=40).run()
            self.assertFalse(b.exception)
            pb = Path(b.session_state['_demo_directory'].name) / 'sei.db'
            self.assertNotEqual(pa, pb)
            self.assertEqual(Workspace(pb).get('theme', 'light'), 'light')
            self.assertEqual(len(Workspace(pb).get('plan')['cronograma']), 4)


if __name__ == '__main__':
    unittest.main()
