# Analista SEMOB com Gemma via Barô

Chatbot local para análise de transporte público municipal. A aplicação usa FastAPI + React, dados canônicos em Parquet, consultas DuckDB validadas, RAG textual local e o modelo `google/gemma-3-27b` pela API OpenAI-compatible Barô da Mauá.

## Estado atual

- Relatórios HTML autorizados preservados localmente em `data/raw`, fora do Git.
- 10 tabelas canônicas em Parquet e DuckDB.
- Sobreposição mensal/quinzenal deduplicada com precedência mensal.
- Perguntas numéricas convertidas em `QueryPlan`; SQL livre não é aceito.
- Proteção de escopo e prompt controlado pelo backend.
- RAG local restrito a `knowledge/`.
- Memória local separada por usuário e conversa.
- Dois assistentes sobre o mesmo Gemma via Barô: CMob AI especializado e Gemma Livre de propósito geral.
- Histórico, contexto e memória isolados por assistente.
- Continuidade conversacional por sessão com deltas sobre o QueryPlan anterior.
- Dataset e script QLoRA preparados, mas treinamento bloqueado até haver checkpoint local exato e GPU CUDA adequada.

Veja [arquitetura atual](docs/CURRENT_ARCHITECTURE.md) e [arquitetura da IA](docs/AI_ARCHITECTURE.md). A auditoria com volumes e cobertura reais dos dados permanece local em `docs/DATA_AUDIT.md`, fora do repositório público.

O backend é o único componente que acessa a Barô. A chave pessoal permanece no ambiente local e nunca é enviada ao navegador.

## Preparar o ambiente

No PowerShell, dentro da raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

Crie o `.env` local a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Preencha sua chave sem aspas e mantenha os demais valores padrão:

```dotenv
BARO_API_KEY=cole_sua_chave_aqui
BARO_BASE_URL=https://ia.maua.br/api/v1
BARO_MODEL=google/gemma-3-27b
```

O `.env` está ignorado pelo Git e deve permanecer local. Nunca coloque a chave real no README, no código-fonte ou em commits.

## Reconstruir a base

Os HTMLs devem ficar abaixo de `data/raw`, mantendo as pastas de período e granularidade.

```powershell
.\.venv\Scripts\python.exe -m scripts.ingest_semob
.\.venv\Scripts\python.exe -m scripts.index_documents
```

Saídas locais:

- `data/processed/parquet/*.parquet`
- `data/database/semob.duckdb`
- `data/database/rag.sqlite`
- `data/metadata/catalog.json`
- `data/metadata/quality_report.json`

## Executar

```powershell
.\start-local.cmd
```

Esse atalho usa o Node portátil em `../.tools/node`, a `.venv` e as dependências do frontend já instaladas. Para uma instalação nova com Python e Node no PATH, siga [migração e execução manual](docs/02%20-%20Migracao%20para%20outro%20PC.md). O Git não inclui `.tools`, `.env`, relatórios de entrada nem bancos locais.

Abra [http://127.0.0.1:5173](http://127.0.0.1:5173). Para encerrar:

```powershell
.\stop-local.cmd
```

Para uma instalação nova, preencha `BARO_API_KEY` e `JWT_SECRET` no `.env` antes de iniciar. Gere o JWT com `python -c "import secrets; print(secrets.token_hex(32))"`. Esses valores não devem entrar no Git. Veja [configuração local e migração](docs/02%20-%20Migracao%20para%20outro%20PC.md).

O backend usa migrações Alembic. `start-local.cmd` aplica `alembic upgrade head` antes de iniciar. Em produção, use PostgreSQL e mantenha `DATABASE_AUTO_CREATE=false`.

Para validar a credencial isoladamente, com o ambiente virtual ativo:

```powershell
$env:BARO_API_KEY="cole_sua_chave_aqui"
python -c "import os; from openai import OpenAI; c=OpenAI(base_url='https://ia.maua.br/api/v1', api_key=os.environ['BARO_API_KEY']); print(c.chat.completions.create(model='google/gemma-3-27b', messages=[{'role':'user','content':'Olá, Barô!'}]).choices[0].message.content)"
```

Por padrão, crie sua conta na interface. Se habilitar `SEED_TEST_USERS=true`, configure também `SEED_TEST_PASSWORD` no `.env` local. As contas novas abaixo usarão essa senha; a interface não a preenche nem a revela:

| Usuário | E-mail |
|---|---|
| Ana Silva | `ana@teste.maua.ai` |
| Bruno Santos | `bruno@teste.maua.ai` |
| Carla Oliveira | `carla@teste.maua.ai` |

Desative as contas demonstrativas antes de qualquer publicação.

Alterar `SEED_TEST_PASSWORD` não troca a senha de contas já existentes. As versões antigas continham senhas de demonstração no código: considere-as públicas e substitua/remova essas contas antes de qualquer deploy. Este commit não apaga o histórico antigo do repositório.

## Perguntas suportadas localmente

Exemplos:

- `Quantas viagens foram realizadas em agosto de 2026?`
- `Quais as 10 linhas com mais viagens em agosto de 2026?`
- `Qual foi o total de passageiros em agosto de 2026?`
- `Mostre a quilometragem improdutiva por dia em agosto de 2026.`
- `Quais linhas tiveram mais exceções em julho de 2026?`

Essas consultas funcionam sem enviar os dados brutos ao Gemma. Respostas conceituais usam somente o corpus textual local autorizado como contexto do modelo.

Follow-ups podem omitir o contexto já estabelecido, por exemplo: `E julho?`, `Compara com agosto`, `E os não pagantes?`, `E as 5 com menos?` e `E a improdutiva?`.

Pedidos de interpretação, como `O que você acha desses dados?` e `Me dê insights`, usam o Gemma com as evidências calculadas da sessão. Assim, o modelo conversa e interpreta, enquanto os números continuam vindo do DuckDB.

Em desenvolvimento, o estado autenticado pode ser inspecionado em `GET /api/debug/session?conversation_id=<id>`. O endpoint não existe quando `APP_ENVIRONMENT=production`.

## Backend PostgreSQL e deploy

Os dados operacionais ficam nas tabelas PostgreSQL `users`, `conversations`, `conversation_messages`, `conversation_states` e `user_preferences`. O backend também fornece `GET /api/ready` para readiness do banco, endpoints de perfil/senha/conta, histórico de conversas e preferências autenticadas.

Para subir PostgreSQL + backend com Docker:

```powershell
docker compose up --build
```

Para o deploy de teste com frontend na Vercel, backend no Render e PostgreSQL no Neon, siga [Deploy de teste: Neon + Render + Vercel](docs/DEPLOY_RENDER.md). O `render.yaml` cria somente o backend e solicita `DATABASE_URL`, `BARO_API_KEY` e `ALLOWED_ORIGINS` como valores privados no painel do Render.

## Avaliação e relatórios

```powershell
.\.venv\Scripts\python.exe -m scripts.build_golden_eval
.\.venv\Scripts\python.exe -m scripts.evaluate_analytics
.\.venv\Scripts\python.exe -m scripts.generate_insights
.\.venv\Scripts\python.exe -m pytest -q
```

O conjunto dourado e o relatório exploratório são gerados em diretórios ignorados pelo Git para não publicar resultados derivados dos dados.

## Fine-tuning opcional

Prepare primeiro o dataset local:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_finetuning
```

O treino QLoRA exige outra instalação com CUDA, ao menos 24 GB de VRAM para esta receita e uma cópia local autorizada do checkpoint/tokenizer exatos. Downloads de modelo são desativados pelo script:

```powershell
python -m pip install -r requirements-training.txt
python -m scripts.train_qlora --model D:\modelos\gemma-3-27b
```

Não use fine-tuning para memorizar dados operacionais. Métricas continuam sendo calculadas no DuckDB.

## Validação executada

```text
Conexão real com google/gemma-3-27b aprovada em 08/10/2026
Streaming assíncrono da API Barô aprovado em 08/10/2026
18 testes de backend aprovados; 2 bloqueados porque `data/database/semob.duckdb` não está presente nesta instalação
Migração Alembic aprovada sobre banco existente e banco vazio
ESLint e build de produção do frontend aprovados
```
