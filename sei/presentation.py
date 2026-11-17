"""Calendário HTML local; todos os textos cadastrados são escapados."""
from datetime import timedelta
from html import escape
from urllib.parse import urlencode
from .workspace import DIAS, minutos, fim_minutos, horario

PATHS = {
    'calendar': '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v5M17 3v5M3 11h18"/>',
    'book': '<path d="M12 6C9 3 5 3 2 5v15c4-2 7-2 10 0 3-2 6-2 10 0V5c-3-2-7-2-10 1Zm0 0v14"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 6v7l4 2"/>',
    'chat': '<path d="M20 16a3 3 0 0 1-3 3H8l-5 3V6a3 3 0 0 1 3-3h11a3 3 0 0 1 3 3Z"/><path d="M7 8h9M7 12h6"/>',
}


def icon(name):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{PATHS[name]}</svg>'


def tint(color):
    values = [int(color[i:i+2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(v * .23 + 255 * .77):02x}' for v in values)


ROBOT = '''<svg class="robot" viewBox="0 0 220 170" xmlns="http://www.w3.org/2000/svg" aria-label="Assistente SEI lendo um livro">
<path d="M25 135C-8 104 39 71 94 54S208 23 206 75s-17 76-64 75-89 11-117-15" fill="#bef2db"/>
<g stroke="#132340" stroke-width="3" stroke-linejoin="round"><path d="m126 29 5-16"/><circle cx="133" cy="10" r="7" fill="#7de5cc"/>
<rect x="71" y="30" width="98" height="76" rx="37" fill="#fff"/><rect x="82" y="48" width="76" height="43" rx="20" fill="#172c43"/>
<path d="M97 72q6-12 13 0m17 0q6-12 13 0" fill="none" stroke="#a8f1d5"/>
<rect x="63" y="54" width="14" height="31" rx="7" fill="#8db8ff"/><rect x="163" y="54" width="14" height="31" rx="7" fill="#8db8ff"/>
<path d="M85 106q-24 19-18 40h96q4-25-17-39" fill="#fff"/>
<path d="M68 105q23-2 48 10 22-14 48-10l-8 51q-22-4-41 4-21-9-42-9Z" fill="#244cb5"/>
<path d="m116 115-1 45"/><path d="M127 127v16q7-3 15 0v-16q-8-3-15 0Z" stroke="#fff" fill="none" stroke-width="2"/>
<circle cx="71" cy="128" r="11" fill="#fff"/><circle cx="162" cy="135" r="11" fill="#fff"/>
<path d="m40 38 11 9m1-25 6 12m-32 19 13 2" stroke="#2b6e5c"/></g></svg>'''


def calendar_html(config, subjects, plan, monday, show_work=False, availability=False):
    by_id = {s['id']: s for s in subjects}
    by_name = {s['name']: s for s in subjects}
    events = []
    if availability:
        for a in config['classes']:
            s = by_id[a['subject']]
            events.append((a['day'], minutos(a['start']), fim_minutos(a['end']), 'Aula', s))
        for c in config.get('commitments', []):
            events.append((c['day'], minutos(c['start']), fim_minutos(c['end']), 'Compromisso',
                           {'name': c['title'], 'color': '#e99ba9'}))
    if plan and plan['viavel']:
        for sessao, slot in plan['cronograma'].items():
            d, h = slot.split()
            s = by_name.get(sessao.rsplit('__', 1)[0])
            if s:
                events.append((d, minutos(h), minutos(h) + config['duration'], 'Estudo', s))
    if availability and show_work:
        for r in config['routine']:
            if r['Trabalha']:
                events.append((r['Dia'], minutos(r['Início trabalho']), fim_minutos(r['Fim trabalho']),
                               'Trabalho', {'name': 'Rotina de trabalho', 'color': '#a7afc2'}))
    from .workspace import slots_disponiveis
    slots = slots_disponiveis(config)
    livres = {(d, minutos(h)) for d, h in (slot.split() for slot in slots)}
    boundaries = {t for e in events for t in (e[1], e[2])}
    for _, h in livres:
        boundaries.update([h, h + config['duration']])
    limites = sorted(boundaries)
    # Só os intervalos realmente ocupados/disponíveis entram na grade. Não
    # preenche o intervalo entre madrugada e noite com linhas vazias.
    periodos = [(a,b) for a,b in zip(limites, limites[1:]) if
                any(e[1] < b and a < e[2] for e in events) or
                any(h < b and a < h + config['duration'] for _,h in livres)]
    head = '<thead><tr><th></th>' + ''.join(
        f'<th><a class="day-link" target="_self" href="?{urlencode({"page": "Disponibilidade", "day": d})}">{d} {(monday + timedelta(days=i)).day}<small>{["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][i]}</small></a></th>'
        for i, d in enumerate(DIAS)) + '</tr></thead>'
    rows = []
    for hora, fim_linha in periodos:
        cells = [f'<td class="time">{horario(hora)}–{horario(fim_linha)}</td>']
        for d in DIAS:
            encontrados = [e for e in events if e[0] == d and e[1] <= hora < e[2]]
            conteudo = ''
            for _, inicio, fim, tipo, s in encontrados:
                css = 'study' if tipo == 'Estudo' else 'class'
                if tipo == 'Estudo':
                    sessao = next(k for k, v in plan['cronograma'].items() if v == f'{d} {horario(inicio)}')
                    query = {'page': 'Calendário', 'session': sessao}
                else:
                    query = {'page': 'Disponibilidade', 'day': d}
                conteudo += f'<a class="event-link" target="_self" href="?{escape(urlencode(query), quote=True)}" title="Editar {tipo.lower()}">'
                conteudo += (f'<div class="event {css}" style="--color:{s["color"]};--tint:{tint(s["color"])}">'
                             f'<b>{"▤" if tipo == "Estudo" else "◇"} {tipo} ·</b>{escape(s["name"])}'
                             f'<small>{horario(inicio)}–{horario(fim)} · editar</small></div></a>')
            if not conteudo:
                disponivel = any(d == dia and h <= hora < h + config['duration'] for dia, h in livres)
                if disponivel:
                    inicio_livre = next(h for dia, h in sorted(livres) if dia == d and h <= hora < h + config['duration'])
                    query = {'page': 'Disponibilidade', 'day': d} if availability else {'page': 'Calendário', 'slot': f'{d}|{horario(inicio_livre)}'}
                    conteudo = (f'<a class="event-link" target="_self" href="?{escape(urlencode(query), quote=True)}">'
                                '<div class="free">＋ Livre para estudar</div></a>')
                else:
                    conteudo = '<div class="empty-slot"></div>'
            cells.append(f'<td>{conteudo}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    if not rows:
        rows.append('<tr><td colspan="8" class="calendar-empty">Nenhum horário cadastrado para exibir.</td></tr>')
    return '<div class="calendar-scroll notranslate" translate="no"><table class="week-grid">' + head + '<tbody>' + ''.join(rows) + '</tbody></table></div>'
