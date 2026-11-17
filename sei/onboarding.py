"""Distribuição de todas as vagas, equilibrada por matéria e aleatória por horário."""
import random
from collections import Counter
from .workspace import DIAS, minutos, CORES, slots_disponiveis


def distribuir(nomes, slots, pesos=None):
    if not nomes or not slots:
        raise ValueError('Cadastre pelo menos uma matéria e selecione um horário de estudo.')
    if len(set(n.casefold() for n in nomes)) != len(nomes) or any(not n.strip() or '__' in n for n in nomes):
        raise ValueError('Use nomes de matérias únicos e sem "__".')
    if len(set(slots)) != len(slots):
        raise ValueError('Não repita horários.')
    rng = random.SystemRandom()
    materias = list(nomes)
    rng.shuffle(materias)
    pesos = pesos or {n: 1 for n in nomes}
    total = sum(pesos[n] for n in nomes)
    quantidades = {n: len(slots) * pesos[n] // total for n in nomes}
    # Os inteiros são garantidos; sobras vão para matérias distintas sorteadas.
    sobras = len(slots) - sum(quantidades.values())
    for n in sorted(materias, key=lambda n: -(len(slots) * pesos[n] / total - quantidades[n]))[:sobras]:
        quantidades[n] += 1
    tarefas = [n for n in nomes for _ in range(quantidades[n])]
    rng.shuffle(tarefas)
    ordem = sorted(slots, key=lambda s: (DIAS.index(s.split()[0]), minutos(s.split()[1])))
    return [{'day': s.split()[0], 'start': s.split()[1], 'subject': n} for s,n in zip(ordem, tarefas)]


def plano_de_linhas(linhas, nomes, duration=60):
    contagem, agenda = Counter(), {}
    for row in linhas:
        nome = row['subject']
        contagem[nome] += 1
        agenda[f'{nome}__{contagem[nome]}'] = f"{row['day']} {row['start']}"
    return {'viavel': True, 'cronograma': agenda, 'duration': duration, 'source': 'balanced',
            'disciplinas_sem_horario': [n for n in nomes if not contagem[n]]}


def planejar_rotina(store):
    cfg, materias = store.get('config'), store.subjects()
    slots = slots_disponiveis(cfg)
    slots = [s for d in DIAS for s in [h for h in slots if h.startswith(d+' ')][:cfg['limit']]]
    fatores = {1:1, 2:2, 3:4, 4:8}
    nomes = [m['name'] for m in materias]
    linhas = distribuir(nomes, slots, {m['name']:m['priority'] * fatores[m['urgency']] for m in materias})
    return plano_de_linhas(linhas, nomes, cfg['duration'])


def aprovar(store, nomes, selecionados, linhas):
    esperado = {f'{d} {h}' for d,horas in selecionados.items() for h in horas}
    if len(linhas) != len(esperado) or {f"{r['day']} {r['start']}" for r in linhas} != esperado:
        raise ValueError('Os horários do plano não correspondem à disponibilidade.')
    distribuir(nomes, sorted(esperado))  # Valida nomes, disponibilidade e duplicatas.
    real = Counter(r['subject'] for r in linhas)
    if set(real) - set(nomes) or (max([real[n] for n in nomes]) - min([real[n] for n in nomes]) > 1):
        raise ValueError('A distribuição deve permanecer equilibrada.')
    if store.get('onboarding_done'):
        return
    # Cadastro e aprovação em uma transação: não deixa matérias pela metade.
    from uuid import uuid4
    import json
    cfg = store.get('config')
    for row in cfg['routine']:
        horas = selecionados.get(row['Dia'], [])
        row['Estudar'] = bool(horas)
        row['study_slots'] = sorted(h for start in horas for h in [start, f'{start[:2]}:30'])
    plano = plano_de_linhas(linhas, nomes)
    with store.conectar() as db:
        for i,nome in enumerate(nomes):
            db.execute('INSERT INTO subjects(id,name,priority,color,description,urgency) VALUES (?,?,?,?,?,?)',
                       (uuid4().hex,nome,1,CORES[i % len(CORES)],'',2))
        for key,value in {'config':cfg,'plan':plano,'planning_mode':'balanced','plan_status':'ready',
                          'error':None,'onboarding_done':True}.items():
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key,json.dumps(value,ensure_ascii=False)))
