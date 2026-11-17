"""SEI — calendário e espaço de estudos local em Streamlit."""
import copy
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import pandas as pd
import streamlit as st

from sei.service import executar
from sei.workspace import (Workspace, DIAS, CORES, URGENCIAS, minutos, fim_minutos, horario,
                           slots_disponiveis, study_intervals, bloqueios_dia, sobrepoe)
from sei.presentation import icon, tint, ROBOT, calendar_html

ROOT = Path(__file__).resolve().parent
PERFIS = {'original': 'Exemplo do notebook', 'dropout': 'Exemplo: evasão observada',
          'enrolled': 'Exemplo: matrícula ativa', 'graduate': 'Exemplo: formação concluída'}
PAGES = [('Calendário', 'calendar_month'), ('Matérias', 'auto_stories'),
         ('Disponibilidade', 'event_available'), ('Chatbot', 'forum')]
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho',
         'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


@st.cache_resource
def carregar_artefatos():
    return (joblib.load(ROOT / 'artefatos/pipeline.joblib'),
            json.loads((ROOT / 'artefatos/perfis.json').read_text(encoding='utf-8')))


def navegar(page, subject=None):
    st.session_state['page'] = page
    st.session_state['subject'] = subject


def alternar_tema(store):
    store.set('theme', 'dark' if st.session_state['dark_mode'] else 'light')


def gerar_plano(store, modelo, perfis, perfil):
    store.set('plan', None)
    store.set('error', None)
    config = store.get('config')
    config['profile'] = perfil
    store.set('config', config)
    try:
        subjects = store.subjects()
        fatores = {1: 1, 2: 2, 3: 4, 4: 8}
        resultado = executar(modelo, perfis[perfil],
                             {s['name']: s['priority'] * fatores[s['urgency']] for s in subjects},
                             slots_disponiveis(config), config['limit'],
                             garantir_todas=len({s['urgency'] for s in subjects}) == 1)
        resultado['duration'] = config['duration']
        store.set('plan', resultado)
        store.set('plan_status', 'ready')
    except ValueError as exc:
        store.set('error', str(exc))
        store.set('plan_status', 'error')


def salvar_disponibilidade(store, config, modelo, perfis):
    """Salva, recalcula e reaproveita ajustes manuais que continuam válidos."""
    from sei.core import backtracking_csp, consistente
    anterior = store.get('plan')
    duracao_anterior = store.get('config')['duration']
    store.save_config(config)
    gerar_plano(store, modelo, perfis, config['profile'])
    if not anterior or not anterior.get('manual') or not anterior.get('viavel') or duracao_anterior != config['duration']:
        return
    slots = slots_disponiveis(config)
    capacidade = sum(min(sum(s.startswith(d+' ') for s in slots), config['limit']) for d in DIAS)
    variaveis = list(anterior['cronograma'])
    if capacidade < len(variaveis):
        return  # A carga sugerida é recalculada; nunca mantém blocos fora da rotina.
    fixas = {}
    for sessao, slot in anterior['cronograma'].items():
        dia, h = slot.split()
        inicio, fim = minutos(h), minutos(h) + config['duration']
        row = next(r for r in config['routine'] if r['Dia'] == dia)
        dentro = any(a <= inicio and fim <= b for a,b in study_intervals(row))
        livre = not any(sobrepoe(inicio, fim, a,b) for a,b in bloqueios_dia(config, dia))
        sem_choque = not any(d == dia and sobrepoe(inicio, fim, minutos(t), minutos(t) + config['duration'])
                            for d,t in (v.split() for v in fixas.values()))
        if dentro and livre and sem_choque and consistente(sessao, slot, fixas, config['limit']):
            fixas[sessao] = slot
    candidatos = [v for v in slots if not any(d == v.split()[0] and sobrepoe(
        minutos(v.split()[1]), minutos(v.split()[1]) + config['duration'], minutos(h), minutos(h) + config['duration'])
        for d,h in (valor.split() for valor in fixas.values()))]
    dominios = {s: ([fixas[s]] if s in fixas else [v for v in candidatos if consistente(s, v, fixas, config['limit'])]) for s in variaveis}
    agenda = backtracking_csp(variaveis, dominios, fixas, config['limit'])
    if agenda is not None:
        anterior.update(cronograma=agenda, duration=config['duration'])
        presentes = {s.rsplit('__',1)[0] for s in agenda}
        anterior['disciplinas_sem_horario'] = [s['name'] for s in store.subjects() if s['name'] not in presentes]
        store.set('plan', anterior)


def page_header(title, subtitle, symbol, robot=True):
    st.markdown('<div class="page-heading notranslate" translate="no"><div>'
                f'<div class="page-title">{icon(symbol)}{escape(title)}</div>'
                + (f'<div class="subtitle">{escape(subtitle)}</div>' if subtitle else '')
                + '</div>' + (ROBOT if robot else '') + '</div>', unsafe_allow_html=True)


def sidebar(store):
    page = st.session_state.get('page', 'Calendário')
    with st.sidebar:
        st.markdown(f'<div class="brand">{icon("book")}<span class="brand-line"></span>SEI</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-subtitle notranslate" translate="no">Sistema de Ensino Inteligente</div>', unsafe_allow_html=True)
        for label, symbol in PAGES:
            st.button(label, icon=f':material/{symbol}:', key=f'nav_{label}', width='stretch',
                      type='primary' if page == label else 'secondary', on_click=navegar, args=(label,))
        st.divider()
        titulo, mais = st.columns([5, 1])
        titulo.markdown('**Minhas matérias**')
        mais.button('＋', key='new_shortcut', help='Cadastrar matéria', on_click=navegar, args=('Matérias',))
        for s in store.subjects():
            dot, botao = st.columns([.25, 3])
            dot.markdown(f'<div class="dot" style="background:{s["color"]};margin-top:20px"></div>', unsafe_allow_html=True)
            botao.button(s['name'], key=f'short_{s["id"]}', width='stretch',
                         on_click=navegar, args=('Matérias', s['id']))
        st.caption('Seu espaço de estudos, salvo neste computador.')
        st.divider()
        st.toggle('Modo escuro', value=store.get('theme', 'light') == 'dark',
                   key='dark_mode', on_change=alternar_tema, args=(store,))


def resumo(store, config, subjects, plan):
    sessoes = Counter(s.rsplit('__', 1)[0] for s in ((plan or {}).get('cronograma') or {}))
    total = sum(sessoes.values())
    a, b, c = st.columns(3)
    a.metric('Estudo na semana', f"{total * config['duration'] / 60:g} h")
    b.metric('Sessões de estudo', str(total))
    c.metric('Matérias no plano', str(sum(q > 0 for q in sessoes.values())))
    st.markdown('<div class="section-label">Cada matéria, seu tempo</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, s in enumerate(subjects):
        horas = sessoes[s['name']] * config['duration'] / 60
        cols[i % 2].markdown(
            f'<div class="legend"><span class="dot" style="background:{s["color"]}"></span>'
            f'<span>{escape(s["name"])}</span><span class="hours">{horas:g} h · {sessoes[s["name"]]} sessões</span></div>',
            unsafe_allow_html=True)
    st.caption(f"Cada sessão de estudo dura {config['duration']} minutos. O total acima não inclui aulas nem trabalho. "
               'Blocos com matéria são estudos; o contorno tracejado indica horários selecionados ainda livres. '
               'Trabalho, aulas e compromissos ficam apenas na Disponibilidade.')


def editor_estudo(store):
    plan, config = store.get('plan'), store.get('config')
    if not plan or not plan['viavel']:
        st.info('Gere um plano válido para adicionar ou alterar estudos.')
        return
    agenda = plan['cronograma']
    subjects = store.subjects()
    session = st.query_params.get('session')
    options = [None] + list(agenda)
    with st.container(border=True):
        st.subheader('Organizar estudo')
        original = st.selectbox('Sessão', options, index=options.index(session) if session in options else 0,
                                format_func=lambda s: '＋ Novo estudo' if s is None else f'{s.rsplit("__", 1)[0]} · {agenda[s]}',
                                key='editing_session')
        slot = agenda.get(original, st.query_params.get('slot', 'Seg|19:00').replace('|', ' '))
        day, start = slot.split() if len(slot.split()) == 2 else ('Seg', '19:00')
        try:
            minutos(start)
            if day not in DIAS:
                raise ValueError('Dia inválido')
        except ValueError:
            day, start = 'Seg', '19:00'
        nomes = [s['name'] for s in subjects]
        current = original.rsplit('__', 1)[0] if original else nomes[0]
        suffix = original or 'new'
        with st.form('edit_study_form'):
            s = st.selectbox('Matéria', subjects, index=nomes.index(current), format_func=lambda v: v['name'], key='manual_subject_' + suffix)
            a, b = st.columns(2)
            d = a.selectbox('Dia do estudo', DIAS, index=DIAS.index(day), key='manual_day_' + suffix)
            h = b.time_input('Início do estudo', value=datetime.strptime(start, '%H:%M').time(), step=1800, key='manual_start_' + suffix)
            st.caption(f"Duração: {config['duration']} min. Ajustes manuais podem mudar a carga realizada; a sugestão do modelo permanece visível.")
            salvar = st.form_submit_button('Salvar estudo', type='primary', key='manual_save')
            remover = st.form_submit_button('Remover sessão', disabled=original is None, key='manual_remove')
            if salvar or remover:
                try:
                    store.edit_study(s['id'], d, h.strftime('%H:%M'), original, remove=remover)
                    st.session_state.pop('editing_study', None)
                    st.query_params.clear()
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if st.button('Fechar editor', key='close_editor'):
            st.session_state.pop('editing_study', None)
            st.query_params.clear()
            st.rerun()


def calendario(store, modelo, perfis):
    config, subjects, plan = store.get('config'), store.subjects(), store.get('plan')
    title, mascote, action = st.columns([4.3, 1.3, 1.8], vertical_alignment='center')
    with title:
        page_header('Calendário', 'Uma semana organizada. Mais espaço para aprender.', 'calendar', robot=False)
    mascote.markdown(ROBOT, unsafe_allow_html=True)
    if action.button('Gerar plano', icon=':material/auto_awesome:', type='primary', width='stretch', key='generate'):
        gerar_plano(store, modelo, perfis, st.session_state.get('perfil', config['profile']))
        st.rerun()
    mode, anterior, periodo, proximo = st.columns([3, .4, 2.4, .4], vertical_alignment='center')
    with mode:
        modo = st.segmented_control('Visualização', ['Semana', 'Matérias'], default='Semana',
                                    key='view', label_visibility='collapsed')
    st.session_state.setdefault('week_offset', 0)
    if anterior.button('‹', key='prev_week', help='Semana anterior'):
        st.session_state['week_offset'] -= 1
    if proximo.button('›', key='next_week', help='Próxima semana'):
        st.session_state['week_offset'] += 1
    hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    monday = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state['week_offset'])
    friday = monday + timedelta(days=6)
    texto = (f'{monday.day}–{friday.day} de {MESES[friday.month-1]}' if monday.month == friday.month
             else f'{monday.day} de {MESES[monday.month-1]} – {friday.day} de {MESES[friday.month-1]}')
    periodo.markdown(f'**{texto} · {friday.year}**')
    st.caption('Semana padrão · os horários de estudo se repetem nas semanas exibidas.')
    st.caption('Visão compacta: períodos vazios entre os horários cadastrados são ocultados.')
    st.caption('Clique em um estudo para alterar matéria ou horário; clique em um campo livre para adicionar um estudo. Aqui aparecem apenas horários de estudo.')
    if store.get('error'):
        st.warning(store.get('error'))
    elif store.get('plan_status') == 'pending':
        st.info('Sua rotina mudou. Clique em “Gerar plano” para atualizar os estudos no calendário.')
    if plan and not plan['viavel']:
        st.warning('Agenda inviável: não há espaço para todas as sessões. Ajuste a disponibilidade ou o limite diário e gere novamente.')
    if plan and plan['disciplinas_sem_horario']:
        st.info('Matérias sem sessão: ' + ', '.join(plan['disciplinas_sem_horario']))
    if modo == 'Matérias':
        cards_materias(store, summary=True)
    else:
        st.markdown(calendar_html(config, subjects, plan, monday), unsafe_allow_html=True)
        if st.button('Adicionar ou editar estudo', key='edit_calendar'):
            st.session_state['editing_study'] = True
        if st.session_state.get('editing_study') or st.query_params.get('slot') or st.query_params.get('session'):
            editor_estudo(store)
    if plan and plan.get('manual'):
        st.caption('Plano com ajustes manuais. “Gerar plano” substitui esses ajustes por uma nova organização automática.')
    resumo(store, config, subjects, plan)
    with st.expander('Como o SEI montou seu plano'):
        perfil = st.selectbox('Perfil acadêmico de demonstração', list(perfis),
                              index=list(perfis).index(config['profile']),
                              format_func=lambda p: PERFIS.get(p, p), key='perfil')
        if perfil != config['profile']:
            st.info('Clique em “Gerar plano” para aplicar o perfil selecionado.')
        if plan:
            ml = plan['ml']
            a, b, c = st.columns(3)
            a.metric('Probabilidade estimada de evasão', f"{ml['probabilidade_dropout'] * 100:.2f}%".replace('.', ','))
            b.metric('Faixa de risco · regra do protótipo', {'baixo': 'Baixo', 'medio': 'Médio', 'alto': 'Alto'}[ml['nivel_risco']])
            c.metric('Carga sugerida · regra do protótipo', f"{ml['sessoes_semanais']} sessões")
            st.caption('Resultado para: ' + PERFIS.get(config['profile'], config['profile']))
        st.write('**1. Previsão:** pré-processamento + Regressão Logística do pipeline local. '
                 '**2. Regra do protótipo:** abaixo de 30% → 4 sessões; de 30% a menos de 55% → 6; a partir de 55% → 8. '
                 '**3. Planejamento:** distribuição por prioridade e CSP com Backtracking, MRV e Forward Checking.')
        st.caption('Urgência multiplica o peso de estudo (Baixa ×1, Normal ×2, Alta ×4, Crítica ×8). '
                   'Com urgências diferentes, a distribuição pode deixar matérias sem sessão para concentrar tempo nas mais urgentes.')
        st.caption(f"{len(slots_disponiveis(config))} horários de estudo disponíveis · máximo de {config['limit']} sessões por dia. "
                   'Trabalho, aulas e compromissos são descontados antes do CSP. A duração converte sessões em horas; não altera a previsão.')


def cards_materias(store, summary=False):
    subjects = store.subjects()
    plan = store.get('plan') or {}
    contagem = Counter(s.rsplit('__', 1)[0] for s in (plan.get('cronograma') or {}))
    columns = st.columns(3)
    for i, s in enumerate(subjects):
        with columns[i % 3], st.container(border=True):
            st.markdown(f'<div class="subject-card"><div class="subject-badge" style="--tint:{tint(s["color"])}">▤</div>'
                        f'<div class="subject-name">{escape(s["name"])}</div>'
                        f'<div class="subject-meta"><span class="urgency">Urgência {URGENCIAS[s["urgency"]]}</span> · {len(store.files(s["id"]))} arquivos'
                        f' · {contagem[s["name"]]} sessões</div></div>', unsafe_allow_html=True)
            st.button('Abrir matéria →', key=f'open_{s["id"]}', width='stretch',
                      on_click=navegar, args=('Matérias', s['id']))
            with st.popover('Urgência e dados', width='stretch'):
                form_materia(store, s)


def form_materia(store, subject=None):
    s = subject or {'name': '', 'priority': 2, 'urgency': 2, 'color': CORES[len(store.subjects()) % len(CORES)], 'description': ''}
    suffix = '_' + s['id'] if subject else ''
    with st.form('subject_form' + suffix, clear_on_submit=not bool(subject)):
        nome = st.text_input('Nome da matéria', value=s['name'], max_chars=90, key='subject_name' + suffix)
        urgencia = st.selectbox('Nível de urgência', list(URGENCIAS), index=s['urgency']-1,
                                format_func=lambda n: URGENCIAS[n], key='urgency' + suffix)
        peso = st.number_input('Peso de estudo', min_value=1, max_value=10, value=s['priority'], key='subject_priority' + suffix)
        cor = st.color_picker('Cor no calendário', value=s['color'], key='subject_color' + suffix)
        descricao = st.text_area('O que você está estudando?', value=s['description'], max_chars=1500)
        if st.form_submit_button('Salvar matéria' if subject else 'Cadastrar matéria', type='primary'):
            try:
                store.save_subject(nome, peso, cor, descricao, s.get('id'), urgency=urgencia)
                st.session_state['flash'] = 'Matéria salva. Gere o plano novamente para atualizar a semana.'
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def chat(store, scope, subject=None):
    st.caption('Modo demonstração · histórico local, sem IA generativa, pesquisa ou leitura automática dos arquivos.')
    mensagens = store.messages(scope)
    if not mensagens:
        st.markdown('<div class="conversation-welcome">' + ROBOT + '<strong>'
                    + (f'Vamos estudar {escape(subject["name"])}?' if subject else 'O que vamos organizar hoje?')
                    + '</strong></div>', unsafe_allow_html=True)
    for m in mensagens:
        with st.chat_message(m['role']):
            st.write(m['content'])
    mensagem = st.chat_input('Pergunte sobre a matéria…' if subject else 'O que vamos organizar hoje?',
                             key=f'chat_{scope}', max_chars=3000)
    if mensagem:
        store.message(scope, 'user', mensagem)
        proposta = None
        if not subject:
            dias_texto = {'segunda': 'Seg', 'terça': 'Ter', 'terca': 'Ter', 'quarta': 'Qua', 'quinta': 'Qui', 'sexta': 'Sex', 'sábado': 'Sab', 'sabado': 'Sab', 'domingo': 'Dom'}
            proposta = next((d for texto, d in dias_texto.items() if texto in mensagem.lower()), None)
            if not re.search(r'(adicion|mais|aument|coloc)', mensagem.lower()) or 'hora' not in mensagem.lower():
                proposta = None
        if proposta:
            st.session_state['proposal'] = proposta
            resposta = ('Demonstração de comando local: posso ampliar em 1 hora a janela de estudos de '
                        f'{proposta}. Confira o ajuste e clique em “Aplicar +1h” abaixo. '
                        'Depois, gere o plano novamente. A carga sugerida continua seguindo a regra do protótipo.')
        elif subject:
            arquivos = store.files(subject['id'])
            nomes = ', '.join(a['name'] for a in arquivos) or 'nenhum material enviado ainda'
            resposta = (f'Demonstração: sua dúvida foi salva no chat de {subject["name"]}. '
                        f'Materiais disponíveis neste espaço: {nomes}. '
                        'Ainda não analiso o conteúdo desses arquivos. Uma futura integração de IA poderá '
                        'buscar trechos, citar fontes e ajudar com resumos e exercícios.')
        else:
            resposta = ('Demonstração: salvei sua mensagem no histórico local. '
                        f'Você tem {len(store.subjects())} matérias cadastradas. '
                        'O comando demonstrativo disponível é “Adicionar mais uma hora na quarta-feira”. '
                        'Pesquisa nos materiais e respostas de IA ainda não estão conectadas.')
        store.message(scope, 'assistant', resposta)
        st.rerun()
    if not subject and st.session_state.get('proposal'):
        day = st.session_state['proposal']
        st.info(f'Ajuste proposto: {day} · +1h na janela de estudos.')
        aplicar, cancelar = st.columns(2)
        if aplicar.button('Aplicar +1h', type='primary', key='apply_hour'):
            cfg = copy.deepcopy(store.get('config'))
            row = next(r for r in cfg['routine'] if r['Dia'] == day)
            intervalos = study_intervals(row) or [(minutos(row['Início estudo']), fim_minutos(row['Fim estudo']))]
            ultimo = max(b for _,b in intervalos)
            fim = ultimo + 60
            if fim > 1440:
                st.error('Esse ajuste ultrapassa o fim do dia. Ajuste os horários em Disponibilidade.')
            else:
                row['Estudar'] = True
                row['Fim estudo'] = horario(fim)
                row['study_slots'] = sorted({horario(t) for a,b in intervalos for t in range(a,b,30)} |
                                           {horario(t) for t in range(ultimo,fim,30)})
                store.save_config(cfg)
                store.message(scope, 'assistant', f'Ajuste local aplicado: {day} até {row["Fim estudo"]}. Gere o plano no Calendário.')
                st.session_state.pop('proposal', None)
                st.rerun()
        if cancelar.button('Cancelar ajuste', key='cancel_hour'):
            st.session_state.pop('proposal', None)
            st.rerun()








def materias(store):
    sid = st.session_state.get('subject')
    subject = next((s for s in store.subjects() if s['id'] == sid), None)
    if not subject:
        page_header('Matérias', 'Organize seus conteúdos e defina o que precisa de mais atenção.', 'book')
        st.caption('Aumente a urgência para concentrar mais sessões nessa matéria ao gerar o plano. A carga total segue a regra do protótipo.')
        with st.expander('＋ Cadastrar nova matéria'):
            form_materia(store)
        cards_materias(store)
        return
    st.button('← Todas as matérias', on_click=navegar, args=('Matérias',), key='back_subjects')
    page_header(subject['name'], '', 'book')
    espaco, arquivos, adicionar = st.columns([3, 1.5, 1.6])
    files = store.files(sid)
    with arquivos, st.popover(f'Arquivos ({len(files)})', icon=':material/folder_open:', width='stretch'):
        st.markdown('**Arquivos desta matéria**')
        if not files:
            st.caption('Nenhum arquivo. Use “Adicionar arquivo”.')
        for f in files:
            st.caption(f"{f['origin']} · {f['size'] / 1024:.1f} KB")
            st.download_button(f['name'], store.file_content(f['id']), file_name=f['name'],
                               key=f'download_{f["id"]}', width='stretch')
    with adicionar, st.popover('Adicionar arquivo', icon=':material/upload_file:', width='stretch'):
        with st.form('upload_form', clear_on_submit=True):
            uploads = st.file_uploader('Selecione os materiais', accept_multiple_files=True,
                                       type=['pdf', 'txt', 'md', 'docx', 'pptx', 'csv', 'png', 'jpg'],
                                       max_upload_size=10, key=f'upload_{sid}')
            if st.form_submit_button('Salvar arquivos', type='primary'):
                try:
                    if not uploads or any(not f.size or f.size > 10 * 1024 * 1024 for f in uploads):
                        raise ValueError('Selecione arquivos com conteúdo, de até 10 MB cada.')
                    for f in uploads:
                        store.add_file(sid, f.name, f.getvalue())
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with st.form('note_form', clear_on_submit=True):
            nome = st.text_input('Título da anotação', max_chars=100)
            conteudo = st.text_area('Criar material de estudo', max_chars=20000)
            if st.form_submit_button('Criar anotação'):
                if not nome.strip() or not conteudo.strip():
                    st.error('Preencha título e conteúdo.')
                else:
                    store.add_file(sid, nome.strip() + '.md', conteudo.encode('utf-8'), origin='Criado')
                    st.rerun()
    chat(store, sid, subject)




def disponibilidade(store, modelo, perfis):
    page_header('Disponibilidade', 'Organize a rotina e escolha todos os horários em que pode estudar.', 'calendar')
    config, subjects = store.get('config'), store.subjects()
    hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    monday = hoje - timedelta(days=hoje.weekday())
    st.markdown(calendar_html(config, subjects, None, monday, show_work=True, availability=True), unsafe_allow_html=True)
    scope = st.radio('Organizar horários', ['Um dia', 'Vários dias', 'Todos os dias'], horizontal=True, key='availability_scope')
    requested = st.query_params.get('day')
    if requested in DIAS:
        st.session_state['routine_day'] = requested
        st.query_params.clear()
    d = st.selectbox('Dia para organizar' if scope == 'Um dia' else 'Dia usado como modelo', DIAS, key='routine_day',
                     format_func=lambda day: ['Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado','Domingo'][DIAS.index(day)])
    if scope == 'Todos os dias':
        targets = DIAS
        st.caption('O padrão escolhido será aplicado de segunda a domingo.')
    elif scope == 'Vários dias':
        targets = st.multiselect('Aplicar nos dias', DIAS, default=[d], key='availability_targets')
    else:
        targets = [d]
    categorias = ['Estudo', 'Trabalho', 'Faculdade / escola', 'Compromissos']
    tipos = categorias if scope == 'Um dia' else st.multiselect('Categorias para aplicar em conjunto', categorias,
                                                               default=['Estudo'], key='bulk_categories')
    if scope != 'Um dia':
        st.caption('Somente as categorias selecionadas serão substituídas nos dias escolhidos; as demais serão preservadas.')
    row = next(r for r in config['routine'] if r['Dia'] == d)
    aulas = [a for a in config['classes'] if a['day'] == d]
    compromissos = [a for a in config.get('commitments', []) if a['day'] == d]
    passo = st.segmented_control('Dividir o dia em cartões de', [30, 60],
                                  default=config['duration'] if config['duration'] in [30,60] else 60,
                                  required=True, format_func=lambda n: f'{n} minutos', key='availability_step')
    st.caption('Cada cartão selecionado será uma sessão disponível dessa duração. Você pode escolher períodos separados no mesmo dia.')
    a,b = st.columns(2)
    qtd = a.number_input('Quantidade de aulas neste dia', min_value=0, max_value=10, value=len(aulas), key='class_count_' + d) if 'Faculdade / escola' in tipos else len(aulas)
    qtd_comp = b.number_input('Quantidade de compromissos', min_value=0, max_value=10, value=len(compromissos), key='commitment_count_' + d) if 'Compromissos' in tipos else len(compromissos)
    def hora_input(value):
        return datetime.strptime('00:00' if value == '24:00' else value, '%H:%M').time()
    with st.form('availability_cards_' + d):
        novas, novos_comp = [], []
        trabalha, work_start, work_end = row['Trabalha'], hora_input(row['Início trabalho']), hora_input(row['Fim trabalho'])
        columns = st.columns(max(1, sum(t in tipos for t in categorias[1:])))
        coluna = 0
        if 'Trabalho' in tipos:
            with columns[coluna]:
                st.markdown('### Trabalho')
                trabalha = st.checkbox('Trabalho neste dia', value=row['Trabalha'], key='work_' + d)
                work_start = st.time_input('Entrada', value=work_start, key='work_start_' + d)
                work_end = st.time_input('Saída', value=work_end, key='work_end_' + d)
            coluna += 1
        if 'Faculdade / escola' in tipos:
            with columns[coluna]:
                st.markdown('### Faculdade / escola')
                if not qtd:
                    st.caption('Sem aulas. Aumente a quantidade acima para incluir matérias e horários.')
                ids = [s['id'] for s in subjects]
                for i in range(int(qtd)):
                    aula = aulas[i] if i < len(aulas) else {'subject': ids[0], 'start': '18:00', 'end': '19:00'}
                    s = st.selectbox(f'Matéria da aula {i+1}', subjects, index=ids.index(aula['subject']), format_func=lambda v:v['name'], key=f'class_subject_{d}_{i}')
                    inicio = st.time_input(f'Início da aula {i+1}', value=hora_input(aula['start']), key=f'class_start_{d}_{i}')
                    fim = st.time_input(f'Fim da aula {i+1}', value=hora_input(aula['end']), key=f'class_end_{d}_{i}')
                    novas.append({'day':d,'subject':s['id'],'start':inicio.strftime('%H:%M'),'end':fim.strftime('%H:%M')})
            coluna += 1
        if 'Compromissos' in tipos:
            with columns[coluna]:
                st.markdown('### Compromissos')
                if not qtd_comp:
                    st.caption('Consultas, deslocamentos e outras atividades também podem bloquear estudos.')
                for i in range(int(qtd_comp)):
                    c = compromissos[i] if i < len(compromissos) else {'title':'','start':'12:00','end':'13:00'}
                    nome = st.text_input(f'Compromisso {i+1}', value=c['title'], max_chars=100, key=f'commitment_title_{d}_{i}')
                    inicio = st.time_input(f'Início do compromisso {i+1}', value=hora_input(c['start']), key=f'commitment_start_{d}_{i}')
                    fim = st.time_input(f'Fim do compromisso {i+1}', value=hora_input(c['end']), key=f'commitment_end_{d}_{i}')
                    novos_comp.append({'day':d,'title':nome.strip(),'start':inicio.strftime('%H:%M'),'end':fim.strftime('%H:%M')})
        selecionados = []
        if 'Estudo' in tipos:
            st.markdown('### Selecione seus horários de estudo')
            st.caption('Marque quantos cartões quiser, inclusive manhã, tarde e noite. Trabalho, aulas e compromissos bloqueiam as partes ocupadas automaticamente.')
            intervalos = study_intervals(row)
            for base in range(0, 1440, passo * 6):
                cols = st.columns(6)
                for i, inicio in enumerate(range(base, min(base + passo * 6, 1440), passo)):
                    with cols[i], st.container(border=True):
                        marcado = any(a <= inicio and inicio + passo <= b for a,b in intervalos)
                        if st.checkbox(f'{horario(inicio)}–{horario(inicio + passo)}', value=marcado,
                                       key=f'study_card_{d}_{passo}_{inicio}'):
                            selecionados.extend(horario(t) for t in range(inicio, inicio + passo, 30))
        limite = st.number_input('Máximo de sessões de estudo por dia', min_value=1, max_value=48,
                                 value=config['limit'], key='availability_limit')
        st.caption('A duração dos cartões e o limite diário valem para a semana inteira. Fim às 00:00 significa meia-noite, encerrando o dia.')
        if st.form_submit_button('Salvar e abrir Calendário', type='primary', key='save_day'):
            try:
                if not targets or not tipos:
                    raise ValueError('Escolha ao menos um dia e uma categoria para salvar.')
                cfg = copy.deepcopy(config)
                for dia in targets:
                    r = cfg['routine'][DIAS.index(dia)]
                    if 'Trabalho' in tipos:
                        r.update({'Trabalha':trabalha,'Início trabalho':work_start.strftime('%H:%M'),'Fim trabalho':work_end.strftime('%H:%M')})
                    if 'Estudo' in tipos:
                        r['study_slots'] = list(selecionados)
                        r['Estudar'] = bool(selecionados)
                        if selecionados:
                            r['Início estudo'] = selecionados[0]
                            r['Fim estudo'] = horario(minutos(selecionados[-1]) + 30)
                    if 'Faculdade / escola' in tipos:
                        cfg['classes'] = [a for a in cfg['classes'] if a['day'] != dia] + [dict(a, day=dia) for a in novas]
                    if 'Compromissos' in tipos:
                        cfg['commitments'] = [a for a in cfg.get('commitments', []) if a['day'] != dia] + [dict(a, day=dia) for a in novos_comp]
                cfg.update(duration=passo, limit=int(limite))
                salvar_disponibilidade(store, cfg, modelo, perfis)
                navegar('Calendário')
                st.query_params.clear()
                st.session_state['flash'] = 'Disponibilidade salva e calendário atualizado automaticamente.'
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def chatbot(store):
    page_header('Chatbot', '', 'chat')
    a, b, _ = st.columns([1.5, 1.5, 4])
    with a, st.popover('Ver chats', icon=':material/history:', width='stretch'):
        conversas = store.conversations()
        if not conversas:
            st.caption('Nenhuma conversa salva ainda.')
        for c in conversas:
            if st.button(c['title'], key='conversation_' + c['id'], width='stretch'):
                st.session_state['conversation'] = c['id']
                st.session_state.pop('proposal', None)
                st.rerun()
    if b.button('Novo chat', icon=':material/add:', key='new_chat', width='stretch'):
        st.session_state['conversation'] = store.new_conversation()
        st.session_state.pop('proposal', None)
        st.rerun()
    if 'conversation' not in st.session_state:
        conversas = store.conversations()
        st.session_state['conversation'] = conversas[0]['id'] if conversas else store.new_conversation()
    chat(store, st.session_state['conversation'])


def main(db_path=None, demo=False):
    st.set_page_config(page_title='SEI | Sua semana de estudos', page_icon='📖', layout='wide', initial_sidebar_state='auto')
    store = Workspace(db_path or os.environ.get('SEI_DB_PATH', str(ROOT / 'dados/sei.db')))
    if demo:
        st.info('Demonstração online: seu espaço é separado dos demais visitantes. '
                'Os dados são temporários e podem desaparecer ao abrir uma nova sessão '
                'ou quando o servidor reiniciar. Use apenas materiais de demonstração.')
    escuro = st.session_state.get('dark_mode', store.get('theme', 'light') == 'dark')
    css = (ROOT / 'assets/sei.css').read_text(encoding='utf-8')
    if escuro:
        css += '\n' + (ROOT / 'assets/sei-dark.css').read_text(encoding='utf-8')
    css += '\n' + (ROOT / 'assets/sei-mobile.css').read_text(encoding='utf-8')
    st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)
    # A tradução automática altera os nós de texto controlados pelo React e pode
    # causar o removeChild exibido na captura. Mantém o app, já em português, fora da tradução.
    st.html('''<script>
        (() => {
        document.documentElement.setAttribute('translate','no');
        document.documentElement.classList.add('notranslate');
        let app = document.querySelector('.stApp');
        if (app) { app.setAttribute('translate','no'); app.classList.add('notranslate'); }
        if (!document.querySelector('meta[name="google"]')) {
            let meta=document.createElement('meta');meta.name='google';meta.content='notranslate';document.head.appendChild(meta);
        }
        })();
    </script>''', unsafe_allow_javascript=True)
    try:
        modelo, perfis = carregar_artefatos()
    except (OSError, ValueError, EOFError) as exc:
        st.error('Não foi possível carregar o pipeline ou os perfis locais. Prepare os artefatos antes da demonstração.')
        st.code('.\\.venv\\Scripts\\python preparar.py --dados fontes\\uci_697.csv')
        st.caption(str(exc))
        st.stop()
    if store.get('plan_status') == 'initial':
        gerar_plano(store, modelo, perfis, 'original')
    requested_page = st.query_params.get('page')
    if requested_page in {p[0] for p in PAGES}:
        st.session_state['page'] = requested_page
        del st.query_params['page']
    if st.session_state.get('page') == 'Horários de aula':
        st.session_state['page'] = 'Disponibilidade'
    sidebar(store)
    if st.session_state.get('flash'):
        st.success(st.session_state.pop('flash'))
    page = st.session_state.get('page', 'Calendário')
    if page == 'Calendário':
        calendario(store, modelo, perfis)
    elif page == 'Matérias':
        materias(store)
    elif page == 'Disponibilidade':
        disponibilidade(store, modelo, perfis)
    else:
        chatbot(store)


if __name__ == '__main__':
    main()
