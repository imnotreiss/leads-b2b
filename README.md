# Captação e Gestão de Leads B2B

Sistema Streamlit + SQLite para buscar empresas locais sem site (e com pelo menos
10 avaliações no Google), armazená-las deduplicadas e gerenciar a prospecção via WhatsApp.

## Arquitetura

- `database.py` — schema SQLite (tabela `leads`) e operações de deduplicação/atualização.
- `api_client.py` — integração com a **Serper.dev Places API** e filtros de qualificação
  (sem site + ≥10 avaliações).
- `app.py` — interface Streamlit (busca + abas "Novas Pesquisas" e "Mensagens Enviadas").

O banco `leads.db` é criado automaticamente na primeira execução (`db.init_db()`).

### Por que Serper.dev

A Serper.dev tem um endpoint de Places (`https://google.serper.dev/places`) que já
retorna nome, endereço, telefone, site, rating e número de avaliações em uma única
chamada, com plano gratuito (2.500 buscas). A Google Places API oficial exige duas
chamadas (Text Search + Place Details) e cobrança por chamada desde o primeiro uso —
por isso não foi a escolha padrão, mas pode substituir `api_client.py` se preferir.

### Limitação conhecida: e-mail e redes sociais

Como o filtro exige empresas **sem site**, normalmente não há fonte pública de onde
extrair e-mail ou redes sociais automaticamente (o Google Places não expõe esses
campos). Os campos `email` e `redes_sociais` ficam vazios após a busca — adicione-os
manualmente nas Observações (aba 2) depois de falar com o lead, se aplicável.

## Passo a passo — rodar localmente

1. **Pré-requisitos**: Python 3.10+.
2. Crie e ative um ambiente virtual:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```
4. Obtenha uma chave gratuita em [serper.dev](https://serper.dev) (cadastro simples,
   sem cartão de crédito).
5. (Opcional) Salve a chave para não precisar digitá-la toda vez: copie
   `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e substitua o valor.
6. Rode a aplicação:
   ```powershell
   streamlit run app.py
   ```
7. Acesse `http://localhost:8501`, informe a chave de API (se não usou o passo 5),
   preencha Nicho e Cidade/Estado e clique em **"Buscar Leads (Até 50)"**.

## Deploy gratuito no Streamlit Community Cloud

1. Suba o projeto para um repositório no GitHub (inclua `app.py`, `database.py`,
   `api_client.py`, `requirements.txt`; **não** suba `leads.db` nem `secrets.toml` —
   já estão no `.gitignore`).
2. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com GitHub.
3. Clique em **"New app"**, selecione o repositório, branch e arquivo principal
   (`app.py`).
4. Em **"Advanced settings" → "Secrets"**, cole:
   ```toml
   SERPER_API_KEY = "sua_chave_aqui"
   ```
5. Clique em **Deploy**. O app ficará disponível em uma URL pública `*.streamlit.app`.

> **Atenção — persistência no Cloud**: o SQLite do Streamlit Community Cloud é
> efêmero (o arquivo `leads.db` é perdido a cada reinício/redeploy do container).
> Para uso contínuo em produção, use o app localmente ou migre `database.py` para
> um banco externo (ex.: Turso/LibSQL, Postgres via Supabase) mantendo a mesma
> interface de funções.

## Regras de negócio implementadas

- Busca até 50 estabelecimentos por pesquisa (paginação automática na Serper.dev).
- Filtra apenas empresas **sem site cadastrado** e com **≥10 avaliações**.
- Deduplicação por `place_id_google` (campo `cid` do Google) ou telefone antes de
  gravar — leads já existentes no banco nunca são reinseridos.
- Leads marcados como "Mensagem Enviada" saem imediatamente da aba de novos leads
  (mudança de `status`) e nunca mais reaparecem em buscas futuras, mesmo que a
  empresa apareça de novo em uma nova pesquisa.
- Aba "Mensagens Enviadas" permite filtrar por status (Enviado, Em Negociação,
  Fechado, Sem Resposta) e editar status/observações de cada lead.
