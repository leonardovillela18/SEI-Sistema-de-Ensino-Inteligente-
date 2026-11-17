"""Boas-vindas, autenticação e primeira semana aprovada pelo estudante."""
from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo
import streamlit as st
from .accounts import Accounts
from .workspace import Workspace, DIAS, horario
from .onboarding import distribuir, aprovar, plano_de_linhas
from .presentation import ROBOT, calendar_html


def sair(accounts):
    accounts.logout(st.session_state.get('session_token', ''))
    st.session_state.clear()
    st.query_params.clear()


def trocar(escolhidas):
    a,b = escolhidas
    linhas = st.session_state['setup_preview']
    linhas[a]['subject'],linhas[b]['subject'] = linhas[b]['subject'],linhas[a]['subject']
    for i in escolhidas:
        st.session_state[f'swap_{i}'] = False


def entrada(root):
    accounts = Accounts(root)
    user = accounts.user(st.session_state.get('session_token'))
    if not user:
        # Não reutiliza widgets, matérias ou conversas da conta anterior.
        if st.session_state.get('active_user'):
            st.session_state.clear()
            st.query_params.clear()
        if not st.session_state.get('greeted'):
            st.markdown('<div class="hello-robot">' + ROBOT + '<h1>Oi! Eu sou o SEI 👋</h1>'
                        '<p>Vamos encontrar tempo para aprender?</p></div>', unsafe_allow_html=True)
            if st.button('Vamos começar', type='primary', key='hello_continue'):
                st.session_state['greeted'] = True
                st.rerun()
            return None
        st.markdown('<div class="auth-brand">' + ROBOT + '<h1>Seu espaço de estudos</h1></div>', unsafe_allow_html=True)
        creating = st.session_state.get('create_account', False)
        st.caption('Sessão válida por 24 horas. Ao sair ou abrir uma nova sessão, entre novamente.')
        with st.form('account_form'):
            if creating:
                name = st.text_input('Seu nome', max_chars=100, key='signup_name')
            email = st.text_input('Email', max_chars=254, key='account_email')
            password = st.text_input('Senha', type='password', max_chars=128, key='account_password')
            if creating:
                st.caption('Use pelo menos 8 caracteres. Contas e dados deste protótipo ficam no servidor '
                           'e podem ser perdidos se a hospedagem reiniciar. O email não é verificado nesta versão.')
            submitted = st.form_submit_button('Criar conta' if creating else 'Entrar', type='primary', key='account_submit')
        if submitted:
            try:
                if creating:
                    accounts.register(name,email,password)
                token = accounts.login(email,password)
                # Nunca guarda a senha no estado após autenticar.
                st.session_state.clear()
                st.session_state['session_token'] = token
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if st.button('Já tenho conta' if creating else 'Quero começar a estudar', key='toggle_signup'):
            st.session_state['create_account'] = not creating
            st.session_state.pop('account_password', None)
            st.rerun()
        return None
    st.session_state['active_user'] = user['id']
    store = Workspace(accounts.workspace_path(user['id']))
    if not store.get('onboarding_done'):
        configurar(store,user)
        with st.sidebar:
            st.caption(user['name'])
            st.button('Sair', key='logout_setup', on_click=sair, args=(accounts,))
        return None
    return store, user, accounts


def configurar(store, user):
    step = st.session_state.get('setup_step', 1)
    st.markdown('<div class="page-heading"><div><h1>Vamos montar sua semana</h1>'
                f'<p>Olá, {escape(user["name"])}!</p></div>' + ROBOT + '</div>', unsafe_allow_html=True)
    st.progress(step / 3, text=f'Passo {step} de 3 · ' + {1:'Suas matérias',2:'Seu tempo',3:'Revisar e aprovar'}[step])
    if step == 1:
        with st.form('subjects_setup'):
            text = st.text_area('Quais matérias você quer estudar?', placeholder='Uma matéria por linha',
                                value=st.session_state.get('setup_names_text',''), key='setup_names_input', height=180)
            st.caption('Informe apenas os nomes. Todas começam com urgência Normal.')
            if st.form_submit_button('Escolher meus horários', type='primary', key='setup_subjects_next'):
                nomes = [s.strip() for s in text.splitlines() if s.strip()]
                if not nomes or len(nomes)>50 or any(len(n)>100 or '__' in n for n in nomes) or len(set(n.casefold() for n in nomes)) != len(nomes):
                    st.error('Informe de 1 a 50 matérias, com nomes únicos de até 100 caracteres e sem "__".')
                else:
                    st.session_state['setup_names_text'] = text
                    st.session_state['setup_names'] = nomes
                    st.session_state['setup_step'] = 2
                    st.rerun()
    elif step == 2:
        st.subheader('Escolha seus horários livres')
        st.caption('Cartões de 60 minutos. Selecione quantos quiser em cada dia; sábado e domingo são opcionais.')
        days = st.multiselect('Dias em que posso estudar', DIAS, default=st.session_state.get('setup_days',DIAS[:5]), key='setup_days_widget')
        if not days:
            st.info('Selecione pelo menos um dia.')
        selecionados = {}
        for d in days:
            with st.expander(d, expanded=len(days)==1):
                horas = []
                for base in range(0,24,6):
                    cols = st.columns(6)
                    for i,h in enumerate(range(base,base+6)):
                        with cols[i], st.container(border=True):
                            if st.checkbox(f'{horario(h*60)}–{horario((h+1)*60)}',
                                           value=horario(h*60) in st.session_state.get('setup_slots',{}).get(d,[]),
                                           key=f'study_card_setup_{d}_{h}'):
                                horas.append(horario(h*60))
                selecionados[d] = horas
                st.caption(f'{len(horas)} h selecionadas em {d}')
        total = sum(map(len,selecionados.values()))
        st.metric('Tempo semanal disponível', f'{total} h')
        if st.button('Montar meu calendário', type='primary', key='setup_build'):
            if not total:
                st.error('Selecione pelo menos um horário de estudo.')
            else:
                st.session_state['setup_days'] = days
                st.session_state['setup_slots'] = selecionados
                st.session_state['setup_preview'] = distribuir(st.session_state['setup_names'],[f'{d} {h}' for d,horas in selecionados.items() for h in horas])
                st.session_state['setup_step'] = 3
                st.rerun()
        if st.button('Voltar às matérias', key='setup_back_names'):
            st.session_state['setup_slots'] = selecionados
            st.session_state['setup_days'] = days
            st.session_state['setup_step'] = 1
            st.rerun()
    else:
        linhas = st.session_state['setup_preview']
        nomes = st.session_state['setup_names']
        st.subheader('Esta semana combina com você?')
        from collections import Counter
        contagem = Counter(r['subject'] for r in linhas)
        st.write(' · '.join(f'{n}: {contagem[n]} h' for n in nomes))
        sem = [n for n in nomes if not contagem[n]]
        if sem:
            st.warning('Sem sessão nesta semana: ' + ', '.join(sem) + '. Adicione horários para contemplar mais matérias.')
        st.caption('A divisão garante a mesma quantidade inteira por matéria. As horas restantes são sorteadas. '
                   'Para inverter, selecione duas sessões e clique em “Trocar matérias”.')
        escolhidas = []
        for d in DIAS:
            itens = [(i,r) for i,r in enumerate(linhas) if r['day']==d]
            if itens:
                st.markdown(f'**{d}**')
                cols = st.columns(2)
                for j,(i,row) in enumerate(itens):
                    with cols[j%2], st.container(border=True):
                        if st.checkbox(f"{row['start']}–{horario(int(row['start'][:2])*60+60)} · {row['subject']}", key=f'swap_{i}'):
                            escolhidas.append(i)
        st.button('Trocar matérias', disabled=len(escolhidas)!=2, key='setup_swap',
                  on_click=trocar, args=(escolhidas,))
        if st.button('Aprovar e começar a estudar', type='primary', key='setup_approve'):
            aprovar(store,nomes,st.session_state['setup_slots'],linhas)
            for key in list(st.session_state):
                if key.startswith(('setup_','swap_','study_card_setup_')):
                    del st.session_state[key]
            st.session_state['page'] = 'Calendário'
            st.rerun()
        if st.button('Alterar disponibilidade', key='setup_back_slots'):
            st.session_state['setup_step'] = 2
            st.rerun()
