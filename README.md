# Analista SEMOB com Gemma

Chatbot local e independente para análise de transporte público municipal. A aplicação usa FastAPI + React, dados canônicos em Parquet, consultas DuckDB validadas, RAG textual local e o Gemma da Mauá apenas para interpretação dentro do domínio autorizado.

## Estado atual

- Relatórios HTML autorizados preservados localmente em `data/raw`, fora do Git.
- 10 tabelas canônicas em Parquet e DuckDB.
- Sobreposição mensal/quinzenal deduplicada com precedência mensal.
- Perguntas numéricas convertidas em `QueryPlan`; SQL livre não é aceito.
- Proteção de escopo e prompt controlado pelo backend.
- RAG local restrito a `knowledge/`.
- Memória local separada por usuário e conversa.
- Continuidade conversacional por sessão com deltas sobre o QueryPlan anterior.
- Dataset e script QLoRA preparados, mas treinamento bloqueado até haver checkpoint local exato e GPU CUDA adequada.

Veja [arquitetura atual](docs/CURRENT_ARCHITECTURE.md) e [arquitetura da IA](docs/AI_ARCHITECTURE.md). A auditoria com volumes e cobertura reais dos dados permanece local em `docs/DATA_AUDIT.md`, fora do repositório público.

Para alternar entre casa, faculdade e nuvem, veja [uso em redes e IPs diferentes](docs/03%20-%20Uso%20em%20redes%20e%20IPs%20diferentes.md). A autorização é feita no IP público de saída do backend, não em uma lista de IPs dentro do chatbot.

## Preparar o ambiente

No PowerShell, dentro da raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

O `.env` deve permanecer local. Use `.env.example` como referência e configure a URL OpenAI-compatible fornecida pela Mauá. Credenciais e dados gerados estão ignorados pelo Git.

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

Para uma instalação nova, preencha `MAUA_AI_BASE_URL`, `MAUA_AI_API_KEY` e `JWT_SECRET` no `.env` antes de iniciar. Gere o JWT com `python -c "import secrets; print(secrets.token_hex(32))"`. O valor não deve entrar no Git. Veja [configuração local e migração](docs/02%20-%20Migracao%20para%20outro%20PC.md).

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
64 testes Python aprovados em 01/10/2026
10/10 casos analíticos dourados aprovados
ESLint aprovado
Build Vite aprovado
```
