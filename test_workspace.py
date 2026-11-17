import copy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from sei.workspace import Workspace, slots_disponiveis
from sei.presentation import calendar_html


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        root = Path('.test-tmp')
        root.mkdir(exist_ok=True)
        self.path = root / f'workspace-{uuid4().hex}.db'
        self.store = Workspace(self.path)

    def test_slots_descontam_aulas_trabalho_e_duracao(self):
        cfg = self.store.get('config')
        self.assertEqual(len(slots_disponiveis(cfg)), 10)
        cfg['classes'][0].update(start='19:00', end='20:00')
        self.assertNotIn('Seg 19:00', slots_disponiveis(cfg))
        cfg['routine'][1].update({'Início trabalho': '19:30', 'Fim trabalho': '20:30'})
        self.assertFalse(any(s.startswith('Ter') for s in slots_disponiveis(cfg)))
        cfg['duration'] = 120
        self.assertEqual(sum(s.startswith('Qua') for s in slots_disponiveis(cfg)), 1)

    def test_arquivos_e_mensagens_persistem_sem_misturar_materias(self):
        a, b = self.store.subjects()[:2]
        self.store.add_file(a['id'], '../aula.txt', b'matrizes e vetores')
        self.store.add_file(a['id'], '../aula.txt', b'matrizes e vetores')
        self.store.message(a['id'], 'user', 'Minha dúvida')
        novo = Workspace(self.path)
        arquivos = novo.files(a['id'])
        self.assertEqual(len(arquivos), 1)
        self.assertEqual(arquivos[0]['name'], 'aula.txt')
        self.assertEqual(novo.file_content(arquivos[0]['id']), b'matrizes e vetores')
        self.assertEqual(len(novo.messages(a['id'])), 1)
        self.assertEqual(novo.files(b['id']), [])
        self.assertEqual(novo.messages(b['id']), [])
        with self.assertRaises(ValueError):
            novo.add_file(a['id'], 'vazio.txt', b'')

    def test_validacao_e_invalidacao(self):
        with self.assertRaises(ValueError):
            self.store.save_subject(' inteligência artificial ', 1, '#aabbcc')
        self.store.set('plan', {'antigo': True})
        cfg = self.store.get('config')
        cfg['duration'] = 90
        self.store.save_config(cfg)
        self.assertIsNone(self.store.get('plan'))
        bad = copy.deepcopy(cfg)
        bad['classes'].append(copy.deepcopy(bad['classes'][0]))
        with self.assertRaises(ValueError):
            self.store.save_config(bad)
        self.assertEqual(self.store.get('config'), cfg)

    def test_nomes_escapados_no_calendario(self):
        subjects = self.store.subjects()
        subjects[0]['name'] = '<script>alert(1)</script>'
        html = calendar_html(self.store.get('config'), subjects, None, date(2026, 11, 23), availability=True)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_editar_mover_adicionar_e_remover_estudo(self):
        from sei.core import gerar_saida_ml
        from sei.service import executar
        import joblib, json
        cfg = self.store.get('config')
        subjects = self.store.subjects()
        pipeline = joblib.load('artefatos/pipeline.joblib')
        perfil = json.loads(Path('artefatos/perfis.json').read_text(encoding='utf-8'))['original']
        plan = executar(pipeline, perfil, {s['name']: s['priority'] for s in subjects}, slots_disponiveis(cfg))
        self.store.set('plan', plan)
        original = next(iter(plan['cronograma']))
        self.store.edit_study(subjects[1]['id'], 'Qua', '19:30', original)
        self.assertIn('Qua 19:30', self.store.get('plan')['cronograma'].values())
        with self.assertRaises(ValueError):
            self.store.edit_study(subjects[0]['id'], 'Qua', '19:00')
        before = self.store.get('plan')
        with self.assertRaises(ValueError):
            self.store.edit_study(subjects[0]['id'], 'Seg', '10:00')
        self.assertEqual(self.store.get('plan'), before)
        self.store.edit_study(subjects[0]['id'], 'Qui', '19:00')
        agenda = self.store.get('plan')['cronograma']
        self.assertEqual(len(agenda), 5)
        key = next(k for k,v in agenda.items() if v == 'Qui 19:00')
        self.store.edit_study(subjects[0]['id'], 'Qui', '19:00', key, remove=True)
        self.assertEqual(len(self.store.get('plan')['cronograma']), 4)

    def test_fim_de_semana_e_conversas_separadas(self):
        cfg = self.store.get('config')
        self.assertEqual(len(cfg['routine']), 7)
        cfg['routine'][5]['Estudar'] = True
        self.store.save_config(cfg)
        self.assertTrue(any(s.startswith('Sab') for s in slots_disponiveis(cfg)))
        a, b = self.store.new_conversation(), self.store.new_conversation()
        self.store.message(a, 'user', 'Revisão para prova')
        self.assertEqual(self.store.messages(b), [])
        self.assertEqual(next(c['title'] for c in self.store.conversations() if c['id']==a), 'Revisão para prova')

    def test_multiplos_periodos_compromissos_e_meia_noite(self):
        cfg = self.store.get('config')
        cfg['duration'] = 30
        row = cfg['routine'][0]
        row['study_slots'] = ['07:00','07:30','19:00','19:30','23:30']
        cfg['commitments'] = [{'day':'Seg','title':'Consulta','start':'19:00','end':'19:30'}]
        self.store.save_config(cfg)
        slots = slots_disponiveis(cfg)
        for h in ['07:00','07:30','19:30','23:30']:
            self.assertIn('Seg ' + h, slots)
        self.assertNotIn('Seg 19:00', slots)
        self.assertNotIn('Seg 08:00', slots)
        html = calendar_html(cfg, self.store.subjects(), None, date(2026,11,23))
        self.assertNotIn('Compromisso ·', html)
        self.assertNotIn('Rotina de trabalho', html)
        self.assertNotIn('Aula ·', html)
        overview = calendar_html(cfg, self.store.subjects(), None, date(2026,11,23), show_work=True, availability=True)
        self.assertIn('Consulta', overview)
        del row['study_slots']
        row.update({'Início estudo':'22:00','Fim estudo':'00:00'})
        self.store.save_config(cfg)
        self.assertIn('Seg 23:30', slots_disponiveis(cfg))

    def test_calendario_compacto_oculta_lacunas(self):
        import re
        cfg = self.store.get('config')
        cfg['classes'] = []
        for row in cfg['routine']:
            row.update(Estudar=False, Trabalha=False)
        row = cfg['routine'][0]
        row.update(Estudar=True, study_slots=['00:00','00:30','22:00','22:30'])
        html = calendar_html(cfg, self.store.subjects(), None, date(2026,11,23))
        self.assertEqual(re.findall(r'<td class="time">(.*?)</td>', html), ['00:00–01:00','22:00–23:00'])
        row.update({'Trabalha':True,'Início trabalho':'08:00','Fim trabalho':'18:00'})
        cfg['classes'] = [{'subject':self.store.subjects()[0]['id'],'day':'Seg','start':'19:00','end':'22:00'}]
        overview = calendar_html(cfg, self.store.subjects(), None, date(2026,11,23), show_work=True, availability=True)
        self.assertEqual(re.findall(r'<td class="time">(.*?)</td>', overview),
                         ['00:00–01:00','08:00–18:00','19:00–22:00','22:00–23:00'])

    def test_meia_noite_aparece_como_zero_hora(self):
        import re
        from sei.workspace import horario
        self.assertEqual(horario(1440), '00:00')
        cfg = self.store.get('config')
        cfg['classes'] = []
        for row in cfg['routine']:
            row.update(Estudar=False, Trabalha=False)
        cfg['routine'][0].update(Estudar=True, study_slots=['23:00','23:30'])
        html = calendar_html(cfg, self.store.subjects(), None, date(2026,11,23))
        self.assertEqual(re.findall(r'<td class="time">(.*?)</td>', html), ['23:00–00:00'])
        self.assertNotIn('24:00', html)
        for row in cfg['routine']:
            row['Estudar'] = False
        empty = calendar_html(cfg, self.store.subjects(), None, date(2026,11,23))
        self.assertNotIn('<td class="time">', empty)
        self.assertIn('Nenhum horário cadastrado', empty)

    def test_migracao_preserva_banco_anterior(self):
        import sqlite3,json
        path = self.path.parent / f'legacy-{uuid4().hex}.db'
        with sqlite3.connect(path) as db:
            db.executescript('''CREATE TABLE subjects(id TEXT PRIMARY KEY,name TEXT,priority INTEGER,color TEXT,description TEXT);
                CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE files(id TEXT PRIMARY KEY,subject_id TEXT,name TEXT,content BLOB,created TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE messages(id INTEGER PRIMARY KEY,scope TEXT,role TEXT,content TEXT,created TEXT);''')
            cfg = self.store.get('config')
            cfg['routine'] = cfg['routine'][:5]
            db.execute('INSERT INTO settings VALUES (?,?)', ('config',json.dumps(cfg)))
            db.execute('INSERT INTO subjects VALUES (?,?,?,?,?)', ('s','Minha matéria',3,'#aabbcc',''))
            db.execute('INSERT INTO files(id,subject_id,name,content) VALUES (?,?,?,?)', ('f','s','texto.txt',b'material'))
            db.execute('INSERT INTO messages VALUES (?,?,?,?,?)', (1,'global','user','Histórico antigo','2026-11-17'))
        migrated = Workspace(path)
        self.assertEqual(len(migrated.get('config')['routine']), 7)
        self.assertEqual(migrated.subjects()[0]['urgency'], 2)
        self.assertEqual(migrated.files('s')[0]['origin'], 'Enviado')
        self.assertEqual(migrated.file_content('f'), b'material')
        self.assertEqual(migrated.messages(migrated.conversations()[0]['id'])[0]['content'], 'Histórico antigo')


if __name__ == '__main__':
    unittest.main(verbosity=2)
