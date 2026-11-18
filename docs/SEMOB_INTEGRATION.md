# API exclusiva para o Projeto Integrador SEMOB

O dashboard Flutter continua publicado na Vercel e chama seu backend Dart. Somente esse backend acessa o MAUA_IA, com uma credencial própria. A chave Barô e os bancos do MAUA_IA não são compartilhados com o SEMOB.

```text
Flutter/Vercel → SEMOB/Dart/Render → MAUA_IA/FastAPI/Render
                                      ├─ CMob: escopo + memória isolada
                                      ├─ DuckDB: resultados numéricos exatos
                                      └─ RAG autorizado → Gemma/Barô
```

## Gerar e configurar a credencial

Na raiz do MAUA_IA, com o ambiente Python ativado:

```powershell
python -m scripts.create_integration_key --output ..\semob-credentials.private.json
```

O script gera 48 bytes aleatórios, grava o arquivo exclusivamente fora do repositório, não sobrescreve arquivos e não mostra a credencial no terminal. O JSON contém duas seções:

| Seção | Serviço Render | Variáveis |
|---|---|---|
| `maua_ia` | `cmob-ai-backend` | `SEMOB_INTEGRATION_KEY_SHA256` |
| `semob` | `projeto-integrador-semob` | `SEMOB_AI_URL`, `SEMOB_AI_API_KEY`, `SEMOB_AI_REQUEST_FIELD`, `SEMOB_AI_RESPONSE_FIELD` |

No MAUA_IA fica apenas o SHA-256. A chave real vai somente para `SEMOB_AI_API_KEY` do backend SEMOB. A URL é `https://cmob-ai-backend.onrender.com/api/integrations/semob/chat`, com campos `message` e `answer`.

As variáveis `BARO_API_KEY`, `DATABASE_URL` e `JWT_SECRET` existentes permanecem no MAUA_IA. Não configure esses segredos na Vercel nem em variáveis `VITE_`/`--dart-define`. Não coloque o JSON privado no Git, nos logs ou em capturas de tela.

Depois de salvar as variáveis, publique uma nova versão de cada serviço. Alterar variáveis pela API do Render exige um novo deploy; reiniciar uma versão antiga não aplica a alteração. [Documentação do Render](https://render.com/docs/deploys).

## Contrato

`POST /api/integrations/semob/chat`, com `Authorization: Bearer <credencial exclusiva>`:

```json
{
  "message": "Qual foi o total de passageiros?",
  "user_id": "identificador-autenticado-pelo-backend-semob",
  "conversation_id": "workspace",
  "context": {
    "period": "2026-08",
    "filters": {"from": "2026-08-01", "to": "2026-08-31"}
  },
  "preferences": {}
}
```

Retorna `answer`, `assistant: "cmob"`, `kind`, `sources`, `conversation_id` e `period`. `GET /api/integrations/semob/status`, com a mesma credencial, verifica a disponibilidade da configuração, banco, RAG e base analítica. Nenhuma resposta expõe as credenciais.

- O identificador do usuário é inserido pelo backend SEMOB a partir da sessão; o navegador não escolhe outra identidade.
- O provedor usa identidades internas inativas, sem login, separadas das contas normais do MAUA_IA. Conversas são separadas por usuário, identificador de conversa e período/intervalo selecionados.
- O período do dashboard é o padrão para perguntas sem datas. Uma data explícita na pergunta prevalece. Intervalos inválidos são recusados.
- A API sempre seleciona CMob. Um campo superior `assistant: "general"` é recusado. Preferências não trocam o assistente nem o prompt controlado pelo servidor.
- Contexto enviado pelo dashboard não substitui documentos nem resultados analíticos autorizados. O RAG e as consultas são executados no MAUA_IA.
- Resultados analíticos são devolvidos diretamente, com números e cobertura exatos. Respostas conceituais usam o modelo com o contexto RAG.
- Bases ausentes, modelo indisponível, respostas vazias e timeouts produzem erros explícitos; não há resposta simulada como fallback.
- Limites por processo: 20 solicitações/minuto por identidade, 120/minuto pelo serviço e até 4 solicitações simultâneas. O SEMOB mantém também seu limite autenticado de 20 solicitações a cada 15 minutos.
- O modelo tem prazo de 45 segundos; a chamada do SEMOB tem prazo de 55 segundos. A política de retenção existente de até 14 dias também atende ao histórico da integração.

Para revogar, esvazie `SEMOB_INTEGRATION_KEY_SHA256` e faça deploy do MAUA_IA. Para rotacionar, gere outro arquivo e atualize os dois serviços. O script nunca fornece acesso administrativo ao Render ou ao MAUA_IA.

## Verificação

```powershell
python -m scripts.build_cmob_data
python -m scripts.index_documents
python -m pytest backend tests
```

Os testes verificam autenticação exclusiva, bloqueio das APIs de conta/chat comum, RAG real com modelo controlado em teste, datas, fontes, isolamento de memória, erros e limites. O outro repositório contém teste HTTP real opcional, habilitado por `SEMOB_TEST_MAUA_URL` e `SEMOB_TEST_MAUA_KEY`, contra uma API de teste. Nunca use banco de produção para as suítes.
