"""Fluxos da interface com banco de testes isolado dos dados do usuário."""
import hashlib
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

TEMP = Path(__file__).resolve().parent / '.test-tmp'
TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEMP)

from streamlit.testing.v1 import AppTest
from sei.workspace import Workspace


class InterfaceTest(unittest.TestCase):
    def setUp(self):
        self.db_path = TEMP / f'ui-{uuid4().hex}.db'
        self.env = patch.dict(os.environ, {'SEI_DB_PATH': str(self.db_path)})
        self.env.start()
        self.addCleanup(self.env.stop)
        Workspace(self.db_path, seed_demo=True)

    def iniciar(self):
        app = AppTest.from_string('from app import main\nmain(require_login=False)', default_timeout=40).run()
        self.assertFalse(app.exception)
        return app

    def clicar(self, app, key):
        app.button(key=key).click().run()
        self.assertFalse(app.exception)

    def calendar(self, app):
        return next(m.value for m in app.markdown if m.value.startswith('<div class="calendar-scroll'))

    def test_calendario_inviabilidade_e_recuperacao(self):
        app = self.iniciar()
        self.assertEqual(self.calendar(app).count('class="event study"'), 4)
        self.assertEqual(app.metric[0].value, '4 h')
        self.assertEqual(app.metric[3].value, '1,88%')
        self.clicar(app, 'generate')
        original = Workspace(self.db_path).get('plan')['cronograma']
        store = Workspace(self.db_path)
        cfg = store.get('config')
        for row in cfg['routine'][1:]:
            row['Estudar'] = False
        store.save_config(cfg)
        app.run()
        self.assertNotIn('class="event study"', self.calendar(app))
        self.clicar(app, 'generate')
        self.assertTrue(any('Agenda inviável' in w.value for w in app.warning))
        self.assertNotIn('class="event study"', self.calendar(app))
        self.assertEqual(app.metric[0].value, '0 h')
        self.assertTrue(any('Matérias sem sessão' in i.value for i in app.info))
        for row in cfg['routine'][:5]:
            row['Estudar'] = True
        store.save_config(cfg)
        self.clicar(app, 'generate')
        self.assertEqual(self.calendar(app).count('class="event study"'), 4)
        self.assertEqual(Workspace(self.db_path).get('plan')['cronograma'], original)

    def test_cadastro_card_chat_e_persistencia(self):
        app = self.iniciar()
        self.clicar(app, 'nav_Matérias')
        app.text_input(key='subject_name').set_value('Matemática')
        next(b for b in app.button if b.label == 'Cadastrar matéria').click().run()
        self.assertFalse(app.exception)
        store = Workspace(self.db_path)
        sid = next(s['id'] for s in store.subjects() if s['name'] == 'Matemática')
        self.clicar(app, f'open_{sid}')
        self.assertFalse(any('prioridade' in t.label.lower() for t in app.expander))
        self.assertGreaterEqual(len(app.get('popover')), 2)
        app.chat_input[0].set_value('Como estudar matrizes?').run()
        self.assertFalse(app.exception)
        self.assertEqual(store.messages(sid)[0]['content'], 'Como estudar matrizes?')
        novo = self.iniciar()
        self.clicar(novo, f'short_{sid}')
        self.assertEqual(len(novo.chat_message), 2)

    def test_comando_chat_com_ajuste_local(self):
        app = self.iniciar()
        self.clicar(app, 'nav_Chatbot')
        app.chat_input[0].set_value('Adicionar mais uma hora na quarta-feira').run()
        self.assertFalse(app.exception)
        self.assertEqual(Workspace(self.db_path).get('config')['routine'][2]['Fim estudo'], '21:00')
        self.clicar(app, 'apply_hour')
        self.assertEqual(Workspace(self.db_path).get('config')['routine'][2]['Fim estudo'], '22:00')
        self.assertIsNone(Workspace(self.db_path).get('plan'))
        self.clicar(app, 'nav_Calendário')
        self.clicar(app, 'generate')
        self.assertEqual(self.calendar(app).count('class="event study"'), 4)

    def test_todas_paginas_e_grade(self):
        app = self.iniciar()
        for page in ['Matérias', 'Disponibilidade', 'Chatbot', 'Calendário']:
            self.clicar(app, f'nav_{page}')
        self.assertFalse(any(b.key == 'nav_Horários de aula' for b in app.button))
        self.clicar(app, 'nav_Disponibilidade')
        from datetime import time
        app.time_input(key='class_start_Seg_0').set_value(time(19,0))
        app.time_input(key='class_end_Seg_0').set_value(time(20,0))
        self.clicar(app, 'save_day')
        self.clicar(app, 'nav_Calendário')
        self.clicar(app, 'generate')
        plano = Workspace(self.db_path).get('plan')
        self.assertNotIn('Seg 19:00', plano['cronograma'].values())

    def test_urgencia_e_edicao_manual(self):
        app = self.iniciar()
        store = Workspace(self.db_path)
        s = store.subjects()[0]
        self.clicar(app, 'nav_Matérias')
        app.selectbox(key='urgency_' + s['id']).set_value(4)
        # Cada formulário de card tem o seu próprio submit.
        next(b for b in app.button if b.label == 'Salvar matéria').click().run()
        self.assertFalse(app.exception)
        self.clicar(app, 'nav_Calendário')
        self.clicar(app, 'generate')
        agenda = store.get('plan')['cronograma']
        self.assertGreater(sum(k.startswith(s['name'] + '__') for k in agenda), 1)
        self.clicar(app, 'edit_calendar')
        from datetime import time
        app.selectbox(key='manual_day_new').set_value('Qua')
        app.time_input(key='manual_start_new').set_value(time(19,0))
        self.clicar(app, 'manual_save')
        self.assertEqual(len(store.get('plan')['cronograma']), 5)
        self.assertTrue(store.get('plan')['manual'])

    def test_novo_chat_e_historico(self):
        app = self.iniciar()
        self.clicar(app, 'nav_Chatbot')
        first = app.session_state['conversation']
        app.chat_input[0].set_value('Primeira pergunta').run()
        self.clicar(app, 'new_chat')
        second = app.session_state['conversation']
        self.assertNotEqual(first, second)
        self.assertEqual(len(app.chat_message), 0)
        self.assertTrue(any('conversation-welcome' in m.value for m in app.markdown))
        self.clicar(app, 'conversation_' + first)
        self.assertEqual(len(app.chat_message), 2)

    def test_tema_escuro_persistencia_e_retorno_ao_claro(self):
        app = self.iniciar()
        store = Workspace(self.db_path)
        agenda = store.get('plan')
        self.assertFalse(app.toggle(key='dark_mode').value)
        # Último controle da barra lateral, depois da lista de matérias.
        self.assertEqual(app.sidebar.toggle[-1].key, 'dark_mode')
        app.toggle(key='dark_mode').set_value(True).run()
        self.assertFalse(app.exception)
        self.assertEqual(store.get('theme'), 'dark')
        self.assertEqual(store.get('plan'), agenda)
        for page in ['Matérias', 'Disponibilidade', 'Chatbot', 'Calendário']:
            self.clicar(app, 'nav_' + page)
            self.assertTrue(app.toggle(key='dark_mode').value)
        novo = self.iniciar()
        self.assertTrue(novo.toggle(key='dark_mode').value)
        novo.toggle(key='dark_mode').set_value(False).run()
        self.assertFalse(novo.exception)
        self.assertEqual(store.get('theme'), 'light')
        self.assertEqual(store.get('plan'), agenda)
        self.assertFalse(self.iniciar().toggle(key='dark_mode').value)

    def test_disponibilidade_em_lote_e_redirecionamento(self):
        app = self.iniciar()
        store = Workspace(self.db_path)
        antes = store.get('config')
        self.clicar(app, 'nav_Disponibilidade')
        app.radio(key='availability_scope').set_value('Todos os dias').run()
        app.checkbox(key='study_card_Seg_60_420').set_value(True)  # 07–08
        app.checkbox(key='study_card_Seg_60_1260').set_value(True)  # 21–22
        self.clicar(app, 'save_day')
        self.assertEqual(app.session_state['page'], 'Calendário')
        cfg = store.get('config')
        self.assertEqual(cfg['classes'], antes['classes'])
        self.assertEqual([r['Trabalha'] for r in cfg['routine']], [r['Trabalha'] for r in antes['routine']])
        for r in cfg['routine']:
            self.assertIn('07:00', r['study_slots'])
            self.assertIn('21:30', r['study_slots'])
        self.assertEqual(self.calendar(app).count('class="event study"'), 4)
        self.assertNotIn('Rotina de trabalho', self.calendar(app))
        self.assertNotIn('Aula ·', self.calendar(app))
        self.assertIn('07:00', self.calendar(app))

    def test_compromisso_bloqueia_e_sincroniza(self):
        from datetime import time
        app = self.iniciar()
        self.clicar(app, 'nav_Disponibilidade')
        app.number_input(key='commitment_count_Seg').set_value(1).run()
        app.text_input(key='commitment_title_Seg_0').set_value('Consulta')
        app.time_input(key='commitment_start_Seg_0').set_value(time(19,0))
        app.time_input(key='commitment_end_Seg_0').set_value(time(20,0))
        self.clicar(app, 'save_day')
        self.assertEqual(app.session_state['page'], 'Calendário')
        store = Workspace(self.db_path)
        self.assertNotIn('Seg 19:00', store.get('plan')['cronograma'].values())
        self.assertEqual(store.get('config')['commitments'][0]['title'], 'Consulta')
        self.assertNotIn('Consulta', self.calendar(app))

    def test_meia_hora_em_dias_especificos(self):
        app = self.iniciar()
        self.clicar(app, 'nav_Disponibilidade')
        app.radio(key='availability_scope').set_value('Vários dias').run()
        app.multiselect(key='availability_targets').set_value(['Sab','Dom'])
        app.segmented_control(key='availability_step').set_value(30).run()
        # O modelo é segunda; desmarca o padrão noturno e escolhe horários separados.
        for minuto in [1140,1170,1200,1230]:
            app.checkbox(key=f'study_card_Seg_30_{minuto}').set_value(False)
        for minuto in [420, 1320, 1410]:
            app.checkbox(key=f'study_card_Seg_30_{minuto}').set_value(True)
        self.clicar(app, 'save_day')
        cfg = Workspace(self.db_path).get('config')
        self.assertEqual(cfg['duration'], 30)
        self.assertEqual(cfg['routine'][5]['study_slots'], ['07:00','22:00','23:30'])
        self.assertNotIn('study_slots', cfg['routine'][0])

    def test_salvar_preserva_ajuste_manual_valido(self):
        app = self.iniciar()
        store = Workspace(self.db_path)
        s = store.subjects()[0]
        original = next(iter(store.get('plan')['cronograma']))
        store.edit_study(s['id'], 'Qua', '19:30', original)
        self.clicar(app, 'nav_Disponibilidade')
        app.checkbox(key='study_card_Seg_60_1260').set_value(True)
        self.clicar(app, 'save_day')
        self.assertIn('Qua 19:30', store.get('plan')['cronograma'].values())
        self.assertTrue(store.get('plan')['manual'])

    def test_sessoes_novas_offline_sem_treino(self):
        import joblib
        import streamlit as st
        conectar = socket.socket.connect
        def apenas_local(sock, endereco):
            if isinstance(endereco, tuple) and endereco[0] in ('127.0.0.1', '::1', 'localhost'):
                return conectar(sock, endereco)
            raise AssertionError('Rede externa proibida')
        arquivos = list(Path('artefatos').glob('*'))
        antes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in arquivos}
        with patch('socket.socket.connect', new=apenas_local), \
             patch('ucimlrepo.fetch_ucirepo', side_effect=AssertionError('Download proibido')), \
             patch('pandas.read_csv', side_effect=AssertionError('Base proibida')), \
             patch('sklearn.pipeline.Pipeline.fit', side_effect=AssertionError('Treino proibido')), \
             patch('joblib.load', wraps=joblib.load) as carregar:
            for _ in range(2):
                st.cache_resource.clear()
                app = self.iniciar()
                self.clicar(app, 'generate')
                self.assertEqual(self.calendar(app).count('class="event study"'), 4)
            self.assertEqual(carregar.call_count, 2)
        self.assertEqual(antes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in arquivos})


if __name__ == '__main__':
    unittest.main(verbosity=2)
