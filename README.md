# SEI — apresentação do protótipo

Aplicativo local com calendário semanal, matérias, arquivos, chats demonstrativos, disponibilidade e grade de aulas. Regressão Logística → estimativa de evasão → regra de carga semanal → planejamento com CSP. O pipeline já está treinado; a demonstração não baixa dados nem treina modelos.

## Como usar a nova interface

**Tema:** a última opção da barra lateral, abaixo de **Minhas matérias**, é **Modo escuro**. Ative para usar o visual escuro em todas as telas; desative para voltar ao claro. A preferência é salva em `dados/sei.db` e reaplicada em novas sessões, sem alterar matérias, horários ou plano.

- **Calendário:** semana de segunda a domingo com **somente estudos e horários selecionados livres**, em visão compacta: as linhas mostram início e fim e não incluem lacunas vazias. Selecionar 00:00–01:00 e 22:00–23:00 produz apenas esses dois intervalos, sem todas as horas intermediárias. A Disponibilidade também compacta trabalho, aulas e compromissos. Clique em um estudo para trocar matéria/dia/horário ou remover a sessão; clique em um espaço livre para adicionar. **Gerar plano** refaz a organização automática. A rotina se repete nas semanas exibidas.
- **Matérias:** cadastre nome, cor, peso de estudo e **urgência** (Baixa, Normal, Alta, Crítica). Edite em **Urgência e dados** nos cards, sem mostrar essa configuração dentro da conversa. Com urgências diferentes, pesos são multiplicados por 1/2/4/8 e a distribuição pode concentrar sessões nas matérias urgentes, deixando outras sem sessão. A carga total de 4/6/8 continua vindo da regra de risco; com níveis iguais, a garantia de uma sessão por matéria, quando possível, é preservada.
- **Dentro da matéria:** conversa em largura total, campo de mensagem no rodapé e **Arquivos** / **Adicionar arquivo** no alto à direita. Os arquivos enviados e as anotações criadas aparecem juntos, identificados por origem. Upload/download local, até 10 MB por arquivo. **Criar anotação** salva um material Markdown escrito por você. Atalhos em **Minhas matérias** abrem o mesmo espaço.
- **Disponibilidade:** escolha **Um dia**, **Vários dias** ou **Todos os dias**. Na edição em lote, escolha um dia como modelo, os dias de destino e as categorias a copiar (por padrão, apenas Estudo; demais dados são preservados). Preencha trabalho, matérias/aulas e **Compromissos** como consultas e outras atividades. Escolha a quantidade de aulas e compromissos antes de preencher os horários.
- **Cartões de estudo:** escolha **30 ou 60 minutos** e marque horários ao longo do dia, inclusive vários períodos separados. Cada cartão é uma sessão disponível, dessa duração. Trabalho, aulas e compromissos bloqueiam partes ocupadas. A meia-noite é sempre exibida como **00:00**: o último cartão é **23:00–00:00** ou **23:30–00:00**. No campo de fim, 00:00 encerra o dia. Duração e limite diário valem para toda a semana.
- **Salvar e abrir Calendário:** salva e atualiza o plano automaticamente, voltando ao Calendário. Aumentar, reduzir ou mover os cartões atualiza os horários livres e os estudos; blocos fora da nova disponibilidade não permanecem na agenda. Ajustes manuais compatíveis são preservados quando a duração não muda e ainda há capacidade; caso contrário, o plano é recalculado. A carga sugerida continua sendo 4/6/8 sessões, portanto selecionar mais cartões cria mais opções livres, sem obrigar o agente a ocupar todas.
- **Chatbot:** **Ver chats** reabre históricos, **Novo chat** inicia uma conversa separada com o robô estudando. As respostas continuam demonstrativas. “Adicionar mais uma hora na quarta-feira” propõe ampliar a janela em 1h; **Aplicar +1h** faz o ajuste local. Gere o plano novamente. Isso acrescenta disponibilidade; a carga sugerida continua vindo da regra de risco.

Os chats **não usam IA generativa nem pesquisam/leem os arquivos** nesta versão. Os arquivos são armazenados e podem ser baixados. Cadastro, configurações, arquivos, mensagens e plano ficam em **`dados/sei.db`**, um único espaço pessoal compartilhado pelas abas do navegador. No modo local não há login ou separação por usuário. Para publicação demonstrativa, use `app_cloud.py`, descrito ao final.

O banco anterior é migrado automaticamente, preservando matérias, arquivos, históricos e horários existentes. O robô aparece em todas as telas e o subtítulo **Sistema de Ensino Inteligente** fica abaixo da marca na lateral. A tabela editável foi retirada da Disponibilidade. Para evitar o erro de `removeChild` associado à tradução automática sobre o React, a página já em português é marcada como não traduzível; após atualizar esta versão, recarregue com **Ctrl+F5** e mantenha a tradução do navegador desligada neste endereço.

## Preparar no Windows, antes da apresentação

No PowerShell, na pasta do projeto, com Python **3.14 de 64 bits**:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-preparacao.txt
# Só para gerar novamente os arquivos do modelo, usando a base local:
.\.venv\Scripts\python preparar.py --dados fontes\uci_697.csv
```

Os arquivos em `artefatos/` já estão prontos: não é necessário executar `preparar.py` novamente. Para baixar a base durante a preparação, use `preparar.py` sem `--dados`. Se `ensurepip` falhar neste Windows, use `uv --cache-dir .uv-cache pip install --python .venv\Scripts\python.exe -r requirements.txt` após criar o ambiente.

## Iniciar o SEI

```powershell
.\.venv\Scripts\python -m streamlit run app.py --server.port 8501
```

Abra **http://127.0.0.1:8501**. Encerre com **Ctrl+C**. Se a porta estiver ocupada, encerre o servidor anterior ou troque para `--server.port 8502` e abra a nova porta.

No VS Code: **Arquivo → Abrir Pasta**, selecione este projeto e use **Terminal → Novo Terminal** para executar o comando. Também pode escolher **Executar e Depurar → SEI: interface Streamlit → F5** (extensões Python e Python Debugger).

## Roteiro para a banca — 2min50s

| Tempo | Ação e explicação |
|---|---|
| 0:00–0:25 | Abra o **Calendário**: quatro estudos, aulas e horários livres. Mostre **4 h** semanais e a legenda com **1 h por matéria** (sessões padrão de 60 min). |
| 0:25–0:55 | Abra **Como o SEI montou seu plano**: perfil do notebook, evasão **1,88%** pelo modelo, **risco baixo / 4 sessões** pelas regras do protótipo. A explicação identifica a montagem com **CSP + Backtracking + MRV + Forward Checking**. |
| 0:55–1:20 | Clique num estudo para editar ou num campo livre para adicionar. Mostre que as horas por matéria acompanham os ajustes. |
| 1:20–1:55 | Em **Disponibilidade**, mostre os sete dias e o formulário com trabalho, matérias das aulas e tempo livre. Explique a ligação com os espaços livres do Calendário. |
| 1:55–2:20 | Em **Matérias**, mostre a urgência no card; abra a matéria para ver a conversa e o menu de arquivos no alto à direita. |
| 2:20–2:50 | No **Chatbot**, mostre **Novo chat**, o robô e **Ver chats**; envie “Adicionar mais uma hora na quarta-feira” e mostre a proposta. IA e pesquisa nos materiais continuam demonstrativas. |

## O que levar para funcionar offline

- `app.py`, pastas `sei/` e **`assets/`**, e `.streamlit/config.toml`.
- `artefatos/pipeline.joblib` e `artefatos/perfis.json` (necessários à demonstração); leve também `metadados.json` para consultar a origem e as métricas.
- **`dados/sei.db`** para levar seus cadastros, arquivos, chats e plano; sem ele, o app cria um espaço novo com o exemplo. Faça a cópia com o app encerrado. `requirements.txt`, este README e `.vscode/launch.json` (opcional, para F5).
- **Python e dependências já instalados no computador da apresentação.** A pasta `.venv` não é portável entre computadores: prepare o ambiente no destino antes de ficar sem internet.

Para instalar em outro Windows sem internet, prepare antes uma pasta `wheels/` em Windows com o mesmo Python/arquitetura: `python -m pip download -r requirements.txt -d wheels`. Leve-a e instale no destino com `.\.venv\Scripts\python -m pip install --no-index --find-links wheels -r requirements.txt`.

`fontes/`, `preparar.py`, `artefatos/dados.csv` e `divisao.json` servem para reproduzir o treinamento, mas não são necessários para apresentar a interface. O notebook original permanece preservado em Downloads; leve uma cópia se quiser consultá-lo na banca.

## Validação

```powershell
.\.venv\Scripts\python -m unittest -v
```

Os testes verificam 10 horários → 4 estudos → 2 horários → aviso sem estudos antigos → retorno a 10 horários → mesma agenda. Incluem navegação, cadastro e cards, chats persistentes, comando de ajuste, arquivos por matéria, bloqueios de trabalho/aula e duração das sessões. Duas sessões novas são abertas com cache limpo e bloqueio de rede externa, download, leitura da base e treinamento.

As interações são verificadas com Streamlit AppTest e bancos isolados em `.test-tmp/`, sem mexer nos dados pessoais. Incluem calendário compacto sem linhas vazias, meia-noite exibida como 00:00, edição por dia/em lote, cartões de 30/60 min, múltiplos períodos, compromissos, salvamento com redirecionamento e preservação de ajustes compatíveis, além da edição manual, urgência, migração e fluxo original. O modelo e o CSP continuam os mesmos, sem novo treinamento.

Detalhes do notebook, configurações e resultados numéricos: [documentação técnica](docs/DETALHES_TECNICOS.md).

## Publicar no Streamlit Community Cloud

A entrada pública é **`app_cloud.py`**. Ela usa o mesmo modelo e as mesmas funções,
mas cria um banco temporário exclusivo por sessão. Alterações, arquivos e chats
não são compartilhados com outros visitantes. Não há login nem persistência online:
recarregar em uma nova sessão ou reiniciar o servidor pode apagar os dados.
O aplicativo local (`app.py`) continua usando `dados/sei.db` normalmente.

1. Envie ao GitHub `app_cloud.py`, `app.py`, `sei/`, `assets/`,
   `.streamlit/config.toml`, `requirements.txt` e os arquivos
   `artefatos/pipeline.joblib` e `artefatos/perfis.json`.
   Inclua também `artefatos/metadados.json` para registrar a versão do modelo.
   Não envie `.venv/`, `dados/`, `.env` ou `.streamlit/secrets.toml`.
2. Em https://share.streamlit.io, escolha **Create app**, o repositório e a branch
   em que você enviou os arquivos. Em **Main file path**, informe **`app_cloud.py`**.
3. Em **Advanced settings → Python version**, selecione **3.14**, a versão usada
   para validar o pipeline. Clique em **Deploy**. Não configure comando de treino.
4. Abra o link publicado, confira as quatro sessões iniciais e abra uma janela
   anônima: ela deve começar com seu próprio exemplo, sem suas alterações.

O deploy instala `requirements.txt` e carrega os artefatos prontos. Não baixa a
base nem treina. As versões científicas permanecem fixas para compatibilidade com
`pipeline.joblib`; não as reduza sem preparar e validar novamente o modelo.
Se a plataforma não oferecer Python 3.14 ou alguma dessas versões, será necessário
recriar e validar os artefatos no ambiente disponível antes de publicar.

Para simular a entrada pública no Windows:

```powershell
.\.venv\Scripts\python -m streamlit run app_cloud.py --server.address 127.0.0.1
```

Para refazer o modelo, instale as dependências adicionais de preparação:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-preparacao.txt
.\.venv\Scripts\python preparar.py --dados fontes\uci_697.csv
```

Guia oficial: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
