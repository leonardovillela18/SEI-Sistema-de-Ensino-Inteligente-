# SEI — Sistema de Ensino Inteligente

Calendário de estudos em Streamlit com contas individuais e configuração inicial.
A entrada começa vazia, sem matérias, aulas, horários ou conversas demonstrativas.

## Executar no Windows / VS Code

Com Python 3.14 de 64 bits, abra a pasta no VS Code e execute no terminal PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py --server.address 127.0.0.1
```

Abra http://127.0.0.1:8501. Para usar a mesma entrada da hospedagem, substitua
`app.py` por `app_cloud.py` no último comando.

## Primeiro acesso

1. O robô entra com animação e diz oi. Clique em **Vamos começar**.
2. Entre com email/senha ou escolha **Quero começar a estudar** para cadastrar
   nome, email e senha (8 a 128 caracteres).
3. Informe apenas os nomes das matérias, uma por linha, sem repetições.
4. Escolha dias e cartões de 60 minutos. Segunda a sexta aparecem na seleção;
   sábado e domingo são opcionais. Nenhum horário começa marcado.
5. Confira a prévia: todas as vagas são usadas. Cada matéria recebe a mesma
   quantidade inteira; as horas restantes são sorteadas entre matérias distintas.
   Se houver menos horas do que matérias, o sistema informa quais ficaram sem sessão.
6. Selecione duas sessões e clique em **Trocar matérias** para inverter seus estudos.
   **Aprovar e começar a estudar** grava matérias, disponibilidade e cronograma juntos.
   Todas as matérias começam com urgência Normal.

Após aprovar, você acessa Calendário, Matérias, Disponibilidade e Chatbot.
**Gerar plano** redistribui seus horários; pesos e urgências diferentes dão mais
horas às matérias prioritárias. Esta modalidade não usa o perfil fictício do notebook
nem apresenta a probabilidade de evasão desse perfil como se fosse do usuário.
Chats continuam demonstrativos, sem leitura automática dos arquivos ou IA generativa.

## Sessão e armazenamento

- Login válido por no máximo **24 horas**. Após esse prazo, entre novamente.
  **Sair da conta** revoga a sessão e limpa o estado da interface.
- Novas abas ou sessões do navegador podem pedir login antes desse prazo.
  Não há cookie persistente de autenticação nesta versão.
- Cada conta tem um banco em `dados/usuarios/<id>/sei.db`.
  `dados/accounts.db` guarda contas e hashes dos tokens. Senhas são derivadas com
  PBKDF2 e sal individual; não são guardadas em texto puro.
- Cinco falhas de login consecutivas bloqueiam a conta por cinco minutos.
- Não há verificação do email ou recuperação de senha nesta etapa.
- **No Streamlit Community Cloud, reinicializações/redeploys podem apagar contas
  e arquivos locais.** Para armazenamento durável, é necessário banco e arquivos
  externos persistentes. A limitação aparece no cadastro.
- A variável `SEI_DATA_DIR` permite escolher outra pasta de dados.
  Nunca envie `dados/`, `.env` ou `.streamlit/secrets.toml` ao GitHub.

Os dados antigos foram arquivados em `.test-tmp/legado-20261117-163615/`,
fora da área ativa, preservando a cópia recuperável. Não são carregados nas contas.
Exemplos acadêmicos só são criados explicitamente nos testes (`seed_demo=True`).

## Publicar no Streamlit Community Cloud

Envie ao GitHub `app_cloud.py`, `app.py`, toda a pasta `sei/`, **todos os arquivos
em `assets/`**, `.streamlit/config.toml`, `requirements.txt` e `artefatos/`.
Não envie `.venv/`, `dados/`, `.test-tmp/`, `.env` ou secrets.

Em https://share.streamlit.io, selecione o repositório e a branch:

- **Main file path:** `app_cloud.py`
- **Advanced settings → Python version:** `3.14`

Clique em **Deploy**. O aplicativo não baixa a base nem treina ao iniciar.
As versões científicas estão fixadas para compatibilidade com o modelo salvo.
Se o ambiente não estiver disponível na hospedagem, prepare e valide os artefatos
novamente em uma versão compatível antes de publicar.

Guia oficial: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Modelo acadêmico e demonstração offline

A Regressão Logística e o fluxo CSP originais permanecem disponíveis pelo terminal.
Os artefatos já estão preparados; refazer o treino é opcional:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-preparacao.txt
.\.venv\Scripts\python preparar.py --dados fontes\uci_697.csv
.\.venv\Scripts\python demo.py
```

Para apresentar offline, leve código, assets, artefatos e ambiente previamente
instalado. Para manter contas locais, copie `dados/` com o app encerrado.
Detalhes: [documentação técnica](docs/DETALHES_TECNICOS.md).

## Testes

```powershell
.\.venv\Scripts\python -m unittest -q
```

Bancos de testes são isolados em `.test-tmp/`. A suíte cobre cadastro, horários
vazios, divisão equilibrada, sobras, finais de semana, troca, aprovação, novo login,
isolamento, expiração em 24h e o fluxo acadêmico anterior.
