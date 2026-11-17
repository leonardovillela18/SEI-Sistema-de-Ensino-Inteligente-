"""Contas, sessão de um dia e onboarding real, sem dados demonstrativos."""
import os
from collections import Counter
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from streamlit.testing.v1 import AppTest
from sei.accounts import Accounts
from sei.onboarding import distribuir, aprovar
from sei.workspace import Workspace, slots_disponiveis


class CloudTest(unittest.TestCase):
    def setUp(self):
        self.root = Path('.test-tmp') / ('accounts-' + uuid4().hex)
        self.env = patch.dict(os.environ, {'SEI_DATA_DIR':str(self.root.resolve())})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.accounts = Accounts(self.root)

    def test_senhas_sessoes_expiracao_e_isolamento(self):
        a = self.accounts.register('Ana','ANA@example.com','senha1234')
        b = self.accounts.register('Bruno','b@example.com','senha1234')
        with self.accounts.connect() as db:
            rows = db.execute('SELECT salt,password FROM users').fetchall()
        self.assertNotEqual(rows[0]['password'], 'senha1234')
        self.assertNotEqual(rows[0]['password'], rows[1]['password'])
        with self.assertRaises(ValueError):
            self.accounts.login('ana@example.com','errada')
        token = self.accounts.login('ana@example.com','senha1234')
        self.assertEqual(self.accounts.user(token)['id'],a)
        with patch('sei.accounts.time.time',return_value=__import__('time').time()+86401):
            self.assertIsNone(self.accounts.user(token))
        wa,wb = Workspace(self.accounts.workspace_path(a)),Workspace(self.accounts.workspace_path(b))
        self.assertEqual(wa.subjects(),[])
        self.assertEqual(slots_disponiveis(wa.get('config')),[])
        wa.save_subject('Matemática',1,'#a78bfa')
        self.assertEqual(wb.subjects(),[])
        self.accounts.logout(token)
        self.assertIsNone(self.accounts.user(token))

    def test_distribuicao_sobras_fim_semana_e_aprovacao(self):
        for qtd in [1,5,7,12,168]:
            slots = [f'{d} {h:02}:00' for d in ['Seg','Ter','Qua','Qui','Sex','Sab','Dom'] for h in range(24)][:qtd]
            rows = distribuir(['A','B','C','D','E'],slots)
            counts = Counter(r['subject'] for r in rows)
            self.assertLessEqual(max(counts[n] for n in 'ABCDE')-min(counts[n] for n in 'ABCDE'),1)
            self.assertEqual(len(rows),qtd)
            self.assertEqual(len({(r['day'],r['start']) for r in rows}),qtd)
        store = Workspace(self.root/'empty.db')
        chosen = {'Seg':['19:00'],'Sab':['23:00'],'Dom':['00:00']}
        rows = distribuir(['A','B'],['Seg 19:00','Sab 23:00','Dom 00:00'])
        aprovar(store,['A','B'],chosen,rows)
        self.assertTrue(store.get('onboarding_done'))
        self.assertEqual(len(store.subjects()),2)
        self.assertTrue(all(s['urgency']==2 for s in store.subjects()))
        self.assertEqual(set(slots_disponiveis(store.get('config'))),{'Seg 19:00','Sab 23:00','Dom 00:00'})
        aprovar(store,['A','B'],chosen,rows)
        self.assertEqual(len(store.subjects()),2)
        with self.assertRaises(ValueError):
            distribuir([],['Seg 19:00'])
        with self.assertRaises(ValueError):
            distribuir(['A','a'],['Seg 19:00'])

    def test_cadastro_onboarding_troca_login_e_logout(self):
        app = AppTest.from_file('app_cloud.py',default_timeout=40).run()
        self.assertFalse(app.exception)
        self.assertEqual(list(self.root.glob('usuarios/*')),[])
        app.button(key='hello_continue').click().run()
        app.button(key='toggle_signup').click().run()
        app.text_input(key='signup_name').set_value('Ana')
        app.text_input(key='account_email').set_value('ana@example.com')
        app.text_input(key='account_password').set_value('senha1234')
        app.button(key='account_submit').click().run()
        self.assertFalse(app.exception)
        app.text_area(key='setup_names_input').set_value('A\nB\nC\nD\nE')
        app.button(key='setup_subjects_next').click().run()
        app.button(key='setup_build').click().run()
        self.assertTrue(app.error)
        for d in ['Seg','Ter','Qua','Qui','Sex']:
            app.checkbox(key=f'study_card_setup_{d}_19').check()
        app.button(key='setup_build').click().run()
        self.assertFalse(app.exception)
        before = [dict(r) for r in app.session_state['setup_preview']]
        self.assertEqual(len(before),5)
        self.assertEqual(len({r['subject'] for r in before}),5)
        app.checkbox(key='swap_0').check()
        app.checkbox(key='swap_1').check().run()
        app.button(key='setup_swap').click().run()
        self.assertFalse(app.exception)
        after = app.session_state['setup_preview']
        self.assertEqual(after[0]['subject'],before[1]['subject'])
        self.assertEqual(after[1]['subject'],before[0]['subject'])
        app.button(key='setup_approve').click().run()
        self.assertFalse(app.exception)
        uid = self.accounts.user(app.session_state['session_token'])['id']
        store = Workspace(self.accounts.workspace_path(uid))
        self.assertEqual(len(store.subjects()),5)
        self.assertEqual(len(store.get('plan')['cronograma']),5)
        self.assertNotIn('ml', store.get('plan'))
        app.button(key='logout').click().run()
        self.assertFalse(app.exception)
        app.button(key='hello_continue').click().run()
        app.text_input(key='account_email').set_value('ana@example.com')
        app.text_input(key='account_password').set_value('senha1234')
        app.button(key='account_submit').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(m.value.startswith('<div class="calendar-scroll') for m in app.markdown))
        fresh = AppTest.from_file('app_cloud.py',default_timeout=40).run()
        self.assertFalse(fresh.exception)
        self.assertTrue(any(b.key=='hello_continue' for b in fresh.button))


if __name__ == '__main__':
    unittest.main()
