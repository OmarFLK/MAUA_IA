# Arquitetura atual

## Resumo executivo

O repositório é hoje um cliente web local para a API OpenAI-compatible Barô da Mauá. Ele **não contém nem carrega os pesos do Gemma localmente**. O modelo é executado em `https://ia.maua.br/api/v1`; o backend FastAPI lê `BARO_API_KEY`, protege a credencial e transmite a resposta ao frontend React.

O trabalho SEMOB foi acrescentado como um subsistema independente e local. Os HTMLs brutos permanecem em `data/raw`, os dados normalizados são gravados em Parquet e o mecanismo analítico é DuckDB. Nenhum dado operacional é enviado ao modelo durante a ingestão.

## Componentes existentes

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| `frontend/` | React, TypeScript, Vite | Login, conversas e streaming |
| `backend/` | FastAPI, OpenAI SDK e HTTPX | Autenticação e streaming para a API Barô |
| `backend/database.py` | SQLAlchemy async + Alembic | Pool, sessões e schema PostgreSQL |
| `backend/conversations.py` | FastAPI + SQLAlchemy | Conversas, mensagens, preferências e estado persistente |
| `semob_ai/ingestion/` | BeautifulSoup, Pandas, PyArrow | Leitura CP1252, normalização e proveniência |
| `data/processed/parquet/` | Parquet | Camada canônica analítica |
| `data/database/semob.duckdb` | DuckDB | Consultas locais somente leitura |

## Modelo observado

- Identificador exposto pela API: `google/gemma-3-27b`.
- Protocolo: OpenAI-compatible, endpoint `/v1/chat/completions`.
- Execução observada: remota no endereço configurado; não há pesos no repositório.
- Tokenizer: não exposto pela API.
- Chat template: não exposto pela API.
- Quantização: não exposta pela API.
- Janela de contexto: não exposta pela API.
- GPU/VRAM do servidor: não expostas pela API.
- Modelos auxiliares disponíveis: consultar o responsável pelo ambiente.

Esses itens não devem ser inferidos pelo nome do modelo. Para fine-tuning será necessário obter do responsável pelo servidor a revisão exata do modelo, tokenizer, formato dos pesos, licença e limites de contexto, ou baixar uma cópia compatível em uma máquina autorizada.

## Requisitos de treinamento

O treinamento QLoRA de um modelo de 27B não deve ser iniciado até confirmar uma GPU CUDA compatível e VRAM suficiente. Inventários de máquinas e detalhes de infraestrutura permanecem locais, fora da documentação pública.

## Fluxo atual

1. O usuário autentica no FastAPI.
2. O frontend envia o histórico para `/api/chat`.
3. O FastAPI chama o servidor Mauá usando a chave apenas no backend.
4. A resposta é retransmitida em NDJSON.

No estado anterior à camada SEMOB, o modelo recebia um prompt acadêmico genérico e podia responder sem evidência calculada. A arquitetura alvo remove essa liberdade para perguntas numéricas: o backend calcula primeiro no DuckDB e fornece ao Gemma somente um resultado estruturado para explicação.

## Limites e riscos encontrados

- O frontend ainda mantém uma cópia de conveniência no `localStorage`, mas o backend persiste as mensagens e o estado por usuário no PostgreSQL.
- O cliente podia enviar mensagens `system`; o backend precisa ignorá-las no modo SEMOB.
- Não existia catálogo, camada analítica, RAG ou proteção de escopo.
- A API remota não oferece, pelo contrato observado, uma operação de fine-tuning.
- O conjunto recebido não contém documentação textual suficiente para um RAG institucional rico; ele contém principalmente relatórios tabulares.
