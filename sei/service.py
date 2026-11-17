"""Validação de entradas e integração offline ML → CSP."""
import math
import re
from collections import Counter
import pandas as pd
from .schema import FEATURES
from .core import gerar_saida_ml, criar_sessoes, backtracking_csp


def validar_perfil(perfil):
    if not isinstance(perfil, dict) or set(perfil) != set(FEATURES):
        raise ValueError('Perfil deve conter exatamente as 22 colunas do notebook.')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in perfil.values()):
        raise ValueError('Perfil deve conter apenas números finitos, sem valores vazios.')
    return pd.DataFrame([perfil], columns=FEATURES)


def executar(pipeline, perfil, prioridades, horarios, max_por_dia=2, garantir_todas=True):
    aluno = validar_perfil(perfil)
    if not isinstance(prioridades, dict) or not prioridades:
        raise ValueError('Informe ao menos uma disciplina.')
    for nome, peso in prioridades.items():
        if not isinstance(nome, str) or not nome.strip() or '__' in nome:
            raise ValueError('Nome de disciplina inválido.')
        if isinstance(peso, bool) or not isinstance(peso, (int, float)) or not math.isfinite(peso) or peso <= 0:
            raise ValueError('Prioridades devem ser números positivos finitos.')
    if not isinstance(max_por_dia, int) or isinstance(max_por_dia, bool) or max_por_dia <= 0:
        raise ValueError('Limite diário deve ser inteiro positivo.')
    if not isinstance(horarios, list) or not horarios:
        raise ValueError('Informe ao menos um horário.')
    if any(not isinstance(h, str) or not re.fullmatch(r'(Seg|Ter|Qua|Qui|Sex|Sab|Dom) (?:[01]\d|2[0-3]):[0-5]\d', h) for h in horarios):
        raise ValueError('Horário inválido: use Seg a Dom e HH:MM.')
    if len(set(horarios)) != len(horarios):
        raise ValueError('Horários duplicados não são permitidos.')
    ml = gerar_saida_ml(pipeline, aluno)
    sessoes = criar_sessoes(ml['sessoes_semanais'], prioridades, garantir_todas=garantir_todas)
    # Todos os domínios têm os mesmos slots. Capacidade insuficiente já prova
    # inviabilidade e evita busca combinatória longa durante a apresentação.
    por_dia = Counter(h.split()[0] for h in horarios)
    capacidade = sum(min(qtd, max_por_dia) for qtd in por_dia.values())
    solucao = None
    if capacidade >= len(sessoes):
        solucao = backtracking_csp(sessoes, {s: list(horarios) for s in sessoes}, max_por_dia=max_por_dia)
    presentes = {s.rsplit('__', 1)[0] for s in (solucao or {})}
    return {'ml': ml, 'viavel': solucao is not None, 'cronograma': solucao,
            'disciplinas_sem_horario': [d for d in prioridades if d not in presentes]}
