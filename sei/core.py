"""Algoritmos extra?dos das c?lulas 55, 59 e 61 do notebook original."""
import numpy as np

def gerar_saida_ml(modelo, aluno_df):
    classe_predita = modelo.predict(aluno_df)[0]

    if not hasattr(modelo, "predict_proba"):
        raise ValueError("O modelo final precisa fornecer predict_proba para a integração atual.")

    probabilidades = modelo.predict_proba(aluno_df)[0]
    classes = list(modelo.named_steps["modelo"].classes_)

    prob_dict = {
        classe: float(probabilidades[i])
        for i, classe in enumerate(classes)
    }

    p_dropout = prob_dict.get("Dropout", 0.0)

    if p_dropout >= 0.55:
        nivel_risco = "alto"
        sessoes_semanais = 8
    elif p_dropout >= 0.30:
        nivel_risco = "medio"
        sessoes_semanais = 6
    else:
        nivel_risco = "baixo"
        sessoes_semanais = 4

    return {
        "classe_predita": classe_predita,
        "probabilidades": prob_dict,
        "probabilidade_dropout": p_dropout,
        "nivel_risco": nivel_risco,
        "sessoes_semanais": sessoes_semanais
    }

def criar_sessoes(total_sessoes, prioridades, garantir_todas=True):
    disciplinas = list(prioridades.keys())
    pesos = np.array([prioridades[d] for d in disciplinas], dtype=float)
    pesos = pesos / pesos.sum()

    quantidades = np.floor(pesos * total_sessoes).astype(int)

    # Garante pelo menos uma sessão para cada disciplina, quando possível.
    if garantir_todas and total_sessoes >= len(disciplinas):
        quantidades = np.maximum(quantidades, 1)

    # Ajusta até bater exatamente o total desejado.
    while quantidades.sum() < total_sessoes:
        idx = int(np.argmax(pesos - quantidades / max(total_sessoes, 1)))
        quantidades[idx] += 1

    while quantidades.sum() > total_sessoes:
        candidatos = [
            i for i, q in enumerate(quantidades)
            if q > 1
        ]
        if not candidatos:
            break
        idx = min(candidatos, key=lambda i: pesos[i])
        quantidades[idx] -= 1

    sessoes = []
    for disciplina, qtd in zip(disciplinas, quantidades):
        for i in range(1, int(qtd) + 1):
            sessoes.append(f"{disciplina}__{i}")

    return sessoes

def dia_do_slot(slot):
    return slot.split()[0]

def consistente(variavel, valor, atribuicao, max_por_dia=2):
    # Restrição 1: nenhum horário pode ser repetido.
    if valor in atribuicao.values():
        return False

    # Restrição 2: máximo de sessões por dia.
    dia = dia_do_slot(valor)
    usadas_no_dia = sum(
        1 for v in atribuicao.values()
        if dia_do_slot(v) == dia
    )

    if usadas_no_dia >= max_por_dia:
        return False

    return True

def forward_checking(variavel, valor, dominios, atribuicao, max_por_dia=2):
    novos_dominios = {
        var: list(vals)
        for var, vals in dominios.items()
    }

    novos_dominios[variavel] = [valor]
    dia = dia_do_slot(valor)

    for outra_var in novos_dominios:
        if outra_var == variavel or outra_var in atribuicao:
            continue

        # Remove o horário já utilizado.
        novos_dominios[outra_var] = [
            v for v in novos_dominios[outra_var]
            if v != valor
        ]

        # Se o dia atingiu o limite, remove os demais horários daquele dia.
        # 'atribuicao' já contém a nova atribuição, portanto não
        # adicionamos 'valor' novamente para não contar a sessão duas vezes.
        usadas_no_dia = sum(
            1 for v in atribuicao.values()
            if dia_do_slot(v) == dia
        )

        if usadas_no_dia >= max_por_dia:
            novos_dominios[outra_var] = [
                v for v in novos_dominios[outra_var]
                if dia_do_slot(v) != dia
            ]

        if len(novos_dominios[outra_var]) == 0:
            return None

    return novos_dominios

def escolher_variavel_mrv(variaveis, dominios, atribuicao):
    nao_atribuidas = [
        v for v in variaveis
        if v not in atribuicao
    ]

    return min(
        nao_atribuidas,
        key=lambda v: len(dominios[v])
    )

def backtracking_csp(
    variaveis,
    dominios,
    atribuicao=None,
    max_por_dia=2
):
    if atribuicao is None:
        atribuicao = {}

    if len(atribuicao) == len(variaveis):
        return atribuicao

    variavel = escolher_variavel_mrv(
        variaveis,
        dominios,
        atribuicao
    )

    for valor in dominios[variavel]:
        if consistente(
            variavel,
            valor,
            atribuicao,
            max_por_dia=max_por_dia
        ):
            nova_atribuicao = dict(atribuicao)
            nova_atribuicao[variavel] = valor

            novos_dominios = forward_checking(
                variavel,
                valor,
                dominios,
                nova_atribuicao,
                max_por_dia=max_por_dia
            )

            if novos_dominios is None:
                continue

            resultado = backtracking_csp(
                variaveis,
                novos_dominios,
                nova_atribuicao,
                max_por_dia=max_por_dia
            )

            if resultado is not None:
                return resultado

    return None
