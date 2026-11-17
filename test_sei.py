import collections
import json
from pathlib import Path
import unittest
import joblib
from sei.core import criar_sessoes, backtracking_csp, forward_checking, escolher_variavel_mrv
from sei.schema import prioridades_disciplinas, horarios_disponiveis
from sei.service import executar

class FluxoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load('artefatos/pipeline.joblib')
        cls.perfil = json.loads(Path('artefatos/perfis.json').read_text(encoding='utf-8'))['original']

    def run_flow(self, **kwargs):
        args = dict(pipeline=self.pipeline, perfil=self.perfil,
                    prioridades=prioridades_disciplinas, horarios=horarios_disponiveis)
        args.update(kwargs)
        return executar(**args)

    def test_dez_horarios(self):
        r = self.run_flow()
        self.assertTrue(r['viavel'])
        self.assertEqual(r['ml']['sessoes_semanais'], 4)
        self.assertEqual(r['ml']['nivel_risco'], 'baixo')
        self.assertEqual(len(r['cronograma']), 4)
        slots = list(r['cronograma'].values())
        self.assertEqual(len(set(slots)), 4)
        self.assertTrue(set(slots) <= set(horarios_disponiveis))
        self.assertLessEqual(max(collections.Counter(s.split()[0] for s in slots).values()), 2)
        self.assertEqual(r['disciplinas_sem_horario'], [])

    def test_demo_offline(self):
        from unittest.mock import patch
        with patch('socket.socket.connect', side_effect=AssertionError('Acesso à rede')):
            pipeline = joblib.load('artefatos/pipeline.joblib')
            r = executar(pipeline, self.perfil, prioridades_disciplinas, horarios_disponiveis)
        self.assertTrue(r['viavel'])

    def test_dois_horarios(self):
        r = self.run_flow(horarios=horarios_disponiveis[:2])
        self.assertFalse(r['viavel'])
        self.assertIsNone(r['cronograma'])
        self.assertEqual(set(r['disciplinas_sem_horario']), set(prioridades_disciplinas))

    def test_entradas_invalidas(self):
        for args in [dict(perfil={}), dict(perfil=None), dict(prioridades={}),
                     dict(horarios=[]), dict(horarios=['Seg 19:00'] * 2),
                     dict(prioridades={'A': 0}), dict(prioridades={'A': float('nan')}),
                     dict(horarios=['Seg 25:00']), dict(max_por_dia=0),
                     dict(perfil={**self.perfil, 'GDP': None})]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.run_flow(**args)

    def test_mais_disciplinas_que_sessoes(self):
        r = self.run_flow(prioridades={str(i): 1 for i in range(6)})
        self.assertTrue(r['viavel'])
        self.assertEqual(r['disciplinas_sem_horario'], ['4', '5'])
        self.assertEqual(len(r['cronograma']), 4)

    def test_capacidade_diaria(self):
        r = self.run_flow(horarios=[f'Seg {h}:00' for h in range(10, 15)])
        self.assertFalse(r['viavel'])

    def test_muitos_slots_com_capacidade_insuficiente(self):
        from unittest.mock import patch
        slots = [f'{d} {h:02d}:{m:02d}' for d in ['Seg', 'Ter', 'Qua']
                 for h in range(24) for m in [0, 30]]
        # 144 slots não permitem oito sessões se cada dia comporta apenas duas.
        with patch('sei.service.gerar_saida_ml', return_value={'sessoes_semanais': 8}):
            r = self.run_flow(horarios=slots)
        self.assertFalse(r['viavel'])
        self.assertIsNone(r['cronograma'])

    def test_limites_risco(self):
        from sei.core import gerar_saida_ml
        import numpy as np
        class Modelo:
            named_steps = {'modelo': type('Classes', (), {'classes_': ['Dropout', 'Graduate']})()}
            def predict(self, x): return ['Graduate']
            def predict_proba(self, x): return np.array([[self.p, 1-self.p]])
        m = Modelo()
        for p, risco, sessoes in [(0.2999,'baixo',4), (0.30,'medio',6), (0.55,'alto',8)]:
            m.p = p
            r = gerar_saida_ml(m, None)
            self.assertEqual((r['nivel_risco'], r['sessoes_semanais']), (risco, sessoes))

    def test_mrv_forward_checking(self):
        self.assertEqual(escolher_variavel_mrv(['a', 'b'], {'a':[1,2], 'b':[1]}, {}), 'b')
        dominios = {'a':['Seg 19:00'], 'b':['Seg 19:00', 'Seg 20:00', 'Ter 19:00']}
        novo = forward_checking('a', 'Seg 19:00', dominios, {'a':'Seg 19:00'}, max_por_dia=1)
        self.assertEqual(novo['b'], ['Ter 19:00'])
        self.assertEqual(len(dominios['b']), 3)

if __name__ == '__main__':
    unittest.main(verbosity=2)
