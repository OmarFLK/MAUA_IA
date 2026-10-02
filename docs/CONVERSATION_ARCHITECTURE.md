# Continuidade conversacional

## Causa raiz corrigida

O frontend já enviava `conversation_id` e o backend armazenava turnos em SQLite, mas o roteamento analítico chamava `plan_question()` somente com a mensagem atual. Nem o Scope Guard nem o QueryPlan recebiam o contexto estruturado da sessão. Assim, expressões elípticas como `E julho?` eram avaliadas isoladamente.

## Fluxo atual

```text
mensagem atual
  -> SessionStore(user_id, session_id)
  -> FollowUpResolver
  -> Scope Guard contextual
  -> QueryPlan novo ou delta do plano anterior
  -> DuckDB somente leitura
  -> enriquecimento determinístico
  -> atualização do ConversationState
```

Assuntos explicitamente fora do domínio e tentativas de prompt injection são bloqueados antes da execução, mesmo quando existe contexto SEMOB ativo.

## Três níveis de memória

### Session state

`data/database/session.sqlite` mantém o estado estruturado por usuário e sessão: assunto, dataset, métricas, períodos, filtros, agrupamentos, entidades, último plano, plano de comparação, resumo do resultado e interações relevantes.

É a fonte prioritária para resolver o próximo turno. Uma nova `session_id` começa vazia, mesmo para o mesmo usuário.

### Working memory

É uma projeção compacta dentro de `ConversationState`, contendo somente o contexto analítico ativo. Não depende de busca vetorial nem do histórico textual completo.

### Memória persistente

`data/database/memory.sqlite` continua separado. Turnos possuem retenção limitada e preferências possuem armazenamento próprio. Resultados operacionais não são promovidos automaticamente a fatos permanentes e não são usados para continuar outra sessão.

## Tipos de follow-up

- `NEW_TOPIC`
- `FOLLOW_UP`
- `REFINEMENT`
- `COMPARISON`
- `DRILL_DOWN`
- `FILTER_CHANGE`
- `METRIC_CHANGE`
- `TIME_CHANGE`
- `EXPLANATION`
- `CORRECTION`

Resoluções de alta confiança são executadas automaticamente. Quando a granularidade não existe, como passageiros por linha, o sistema explica a limitação em vez de inventar uma consulta.

## Enriquecimento determinístico

- Decomposição de passageiros: quantidades e percentuais.
- Comparações: dois valores, diferença absoluta e variação percentual.
- Rankings: direção e limite herdados ou modificados pelo follow-up.
- Causalidade: diferenças são apresentadas como associação; causa não é afirmada sem evidência.

## Interpretação pelo Gemma

O roteamento é híbrido. Pedidos quantitativos continuam no Analytics Engine. Pedidos como `o que você acha desses dados?`, `interprete` e `me dê insights` são enviados ao Gemma com as últimas evidências estruturadas da sessão, além do RAG autorizado.

Isso permite uma resposta conversacional sem transformar o modelo em fonte dos números. O contexto também informa explicitamente que `não pagantes` não significa evasão ou fraude, que uma única observação não comprova tendência e que cobertura da tabela só implica resultado parcial quando não contém todo o período solicitado.

`passageiros_pagantes` é calculado como `Catraca + Antecipados`. A identidade com `Total - Não Pagantes` foi verificada em todas as 62 linhas recebidas, mas a definição continua explicitamente pendente de homologação de negócio.

## Depuração local

Em `APP_ENVIRONMENT=development`, um usuário autenticado pode consultar:

```text
GET /api/debug/session?conversation_id=<id>
```

O endpoint retorna somente o estado pertencente ao usuário autenticado e os turnos recentes daquela sessão. Em produção ele responde `404`.

Os logs de desenvolvimento registram pergunta original, tipo de follow-up, intenção resolvida, contexto herdado, mudanças, plano final e sessão. Credenciais e conteúdo bruto dos dados não são registrados.
