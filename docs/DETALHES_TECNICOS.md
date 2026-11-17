# SEI — primeira etapa do protótipo

Registro técnico das etapas anteriores. Para os comandos e o roteiro da revisão final, consulte o [README atual](../README.md).

Fluxo Python: perfil acadêmico → pré-processamento → Regressão Logística → estimativa de evasão → carga semanal → distribuição por prioridade → CSP com Backtracking, MRV e Forward Checking. Interface local em Streamlit e demonstração por terminal.

## Interface Streamlit

```powershell
.\.venv\Scripts\python -m streamlit run app.py
```

Abra **http://127.0.0.1:8501** no navegador. Para encerrar, pressione Ctrl+C no terminal que executa o servidor. Se a porta já estiver ocupada, use `--server.port 8502` e abra a porta correspondente.

No VS Code, abra esta pasta em **Arquivo → Abrir Pasta**, selecione `.venv\Scripts\python.exe` em **Python: Select Interpreter** e execute o comando acima no terminal integrado (**Terminal → Novo Terminal**). Também há uma configuração pronta em **Executar e Depurar → SEI: interface Streamlit → F5**, com as extensões Python e Python Debugger instaladas.

As dependências da interface já estão instaladas neste ambiente e registradas em `requirements.txt`. Em outra máquina, use os comandos de instalação da seção seguinte. O app não faz download nem retreina o modelo: usa os artefatos locais da primeira etapa. A configuração desativa a telemetria do Streamlit, e nenhum recurso visual remoto é necessário.

Na tela, o perfil original, as quatro disciplinas e os dez horários do notebook começam preenchidos. Clique em **Gerar cronograma** para ver probabilidade de evasão **1,88%**, risco **baixo**, **4 sessões** e a agenda ordenada por dia e início. Faixa de risco e carga são identificadas como **regras do protótipo**.

Para demonstrar inviabilidade, deixe apenas **segunda-feira**, mantendo 19h e 20h e o limite de duas sessões por dia, e clique novamente. A interface mostra o aviso, remove a tabela anterior e lista as disciplinas sem sessão. Horários ou dias vazios também removem o resultado anterior e mostram uma validação. Edite a tabela para acrescentar/remover disciplinas e alterar pesos positivos; nomes repetidos são rejeitados. Quando houver mais disciplinas do que sessões, as que ficaram sem sessão são listadas.

Os horários de início selecionados se aplicam a todos os dias escolhidos. Cada horário representa um slot, como no notebook, sem cálculo de duração. Mudanças no formulário só são aplicadas ao clicar em **Gerar cronograma**; o resultado identifica o perfil usado na última geração.

Não foi encontrada logo na pasta. A interface usa a marca textual SEI e azul-escuro. Uma imagem local com `logo` no nome, na raiz ou em `assets/`, `imagens/` ou `images/`, será carregada automaticamente.

Validação: **13 testes aprovados**, sendo cinco da interface com Streamlit AppTest e oito do fluxo Python. Incluem sucesso → inviabilidade → recuperação, limpeza por entrada vazia, todos os perfis sem conexões externas e disciplinas sem sessão. O servidor foi iniciado e respondeu `200 ok` no health check. A página foi aberta no Chrome; a automação de cliques do navegador ficou limitada pelo serviço de captura do ambiente, portanto os cenários interativos foram verificados com AppTest.

## Executar

Os artefatos já estão preparados. Na raiz do projeto, no PowerShell:

```powershell
.\.venv\Scripts\python demo.py --horarios 10
.\.venv\Scripts\python demo.py --horarios 2
.\.venv\Scripts\python -m unittest -v
```

Em outro computador, instale primeiro as dependências (Python 3.14 usado nesta execução):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Neste ambiente, `ensurepip` falhou. A alternativa que funcionou:

```powershell
uv --cache-dir .uv-cache pip install --python .venv\Scripts\python.exe -r requirements.txt
```

A instalação requer internet; depois dela a demonstração carrega somente arquivos locais. O teste `test_demo_offline` bloqueia conexões de socket durante carregamento, previsão e planejamento.

## Preparar novamente

```powershell
# Preparação inteiramente local com a base preservada:
.\.venv\Scripts\python preparar.py --dados fontes\uci_697.csv
# Ou baixar novamente a base pública UCI 697:
.\.venv\Scripts\python preparar.py
```

O cliente `ucimlrepo` encontrou erro de cadeia de certificados neste Windows. A base foi obtida da URL oficial retornada pela API usando `curl.exe`, com validação normal de certificados do Windows, sem desativar TLS. Para repetir:

```powershell
curl.exe -L --fail 'https://archive.ics.uci.edu/api/dataset?id=697' -o fontes\uci_metadata.json
$uciMetadata = Get-Content fontes\uci_metadata.json -Raw | ConvertFrom-Json
curl.exe -L --fail $uciMetadata.data.data_url -o fontes\uci_697.csv
```

`preparar.py` salva em `artefatos/`: pipeline completo em `pipeline.joblib`, perfis em `perfis.json`, dados selecionados em `dados.csv`, índices de treino/teste em `divisao.json` e configurações, versões, métricas e hash dos dados em `metadados.json`. O treinamento não utiliza o teste. Os perfis `dropout`, `enrolled` e `graduate` são exemplos reais do teste, nomeados pela classe observada, sem garantia de previsão igual. Exemplo: `demo.py --perfil dropout`.

## Fidelidade ao notebook

Foi encontrado apenas `C:\Users\Administrador\Downloads\Marco2_Planejamento_Inteligente_Estudos_FINAL_CORRIGIDO.ipynb`, sem o sufixo `(2)` e fora da pasta do projeto. Esse arquivo foi somente lido e permanece no local original. SHA-256: `C6F148CD9E795485744316BDAAF16CF31D732CF8A7583147FD671EBF8E0A9616`.

- Célula 14: mesmas 22 entradas, nomes e ordem em `sei/schema.py`.
- Células 26 e 28: divisão estratificada 80/20, semente 42; OneHotEncoder com `handle_unknown='ignore'` em três colunas e StandardScaler nas outras 19.
- Células 47 e 53: Regressão Logística com `max_iter=2000`, `random_state=42`, demais parâmetros padrão. O notebook já selecionou esse modelo por F1 macro em validação cruzada estratificada de cinco folds no treino. A preparação treina diretamente o modelo escolhido; não refaz a comparação exploratória com árvore e k-NN.
- Célula 55: `Dropout >= 0.55` define risco alto e 8 sessões; `>= 0.30`, médio e 6; abaixo disso, baixo e 4. Evasão é localizada pelo nome da classe.
- Célula 59: distribuição proporcional com piso, garantia de uma sessão por disciplina quando possível e ajustes para atingir o total. Empates seguem a ordem das disciplinas.
- Célula 61: algoritmos extraídos para `sei/core.py`, preservando a ordem dos valores e desempate MRV. Não há choque de horários e há no máximo duas sessões por dia.

`sei/training.py` contém a construção e o treinamento reutilizáveis; `sei/service.py` valida e integra o fluxo. As prioridades são preferências do usuário, não inferidas da UCI. Horários são slots discretos de segunda a sexta no formato `Seg 19:00`, sem duração modelada. Vazios, duplicatas, números não finitos e prioridades não positivas geram `ValueError`. Agenda inviável é um resultado esperado: `viavel=False`, `cronograma=None`.

Quando há mais disciplinas do que sessões, `disciplinas_sem_horario` lista as que não receberam sessão. Em agenda inviável, todas são listadas, pois nenhuma atribuição completa foi encontrada. Exemplo:

```python
import json
from pathlib import Path
import joblib
from sei.service import executar
from sei.schema import horarios_disponiveis

modelo = joblib.load('artefatos/pipeline.joblib')
perfil = json.loads(Path('artefatos/perfis.json').read_text(encoding='utf-8'))['original']
resultado = executar(modelo, perfil, {str(i): 1 for i in range(6)}, horarios_disponiveis)
print(resultado['disciplinas_sem_horario'])  # ['4', '5']
```

## Resultados verificados

Perfil original: primeiro registro do teste, índice 1853. Foram preservados 3.539 registros de treino e 885 de teste.

| Cenário | Resultado |
|---|---|
| Perfil original | Graduate; evasão 1,8754408201808827%; risco baixo; 4 sessões |
| 10 horários | 4 sessões válidas, sem colisões e respeitando 2 por dia |
| 2 horários | Agenda inviável |
| Perfil, prioridades ou horários vazios | Rejeitados |
| Horários duplicados | Rejeitados |
| 6 disciplinas de peso igual e 4 sessões | Disciplinas `4` e `5` sem horário |
| 5 horários no mesmo dia | Agenda inviável pelo limite diário |

Agenda com 10 horários: Inteligência Artificial na segunda às 19h, Ciência de Dados na segunda às 20h, Banco de Dados na terça às 19h e Engenharia de Software na terça às 20h.

O notebook registra `0.018754408201636767`; esta execução obteve `0.018754408201808827`. A diferença é `1.7206e-11` ponto percentual, compatível com precisão numérica, sem mudança de decisão. Ambos arredondam para **1,88%**. Acurácia de teste `0.7333333333333333` e F1 macro `0.6352261904761906` reproduzem as métricas do notebook. As versões estão fixadas em `requirements.txt`.

Oito testes verificam os cenários acima, os limiares de risco, MRV e poda pelo limite diário, sem alteração dos domínios originais.
