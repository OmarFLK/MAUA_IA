# Arquitetura alvo da IA SEMOB

## Princípio central

O LLM não é a calculadora nem a fonte dos números. Perguntas quantitativas seguem o fluxo determinístico:

`pergunta -> estado da sessão -> resolução de follow-up -> proteção de escopo -> QueryPlan validado -> DuckDB somente leitura -> resultado estruturado`

Documentos textuais seguem outro fluxo:

`pergunta -> busca local híbrida -> trechos com proveniência -> Gemma -> resposta citada`

Memória de conversa, RAG e fatos analíticos ficam em armazenamentos distintos.

## Camadas

1. **Dados brutos**: HTML original, CP1252, imutável.
2. **Canônica**: Parquet tipado, deduplicado e com proveniência.
3. **Consulta**: DuckDB local aberto em modo somente leitura durante o chat.
4. **Planejamento**: `QueryPlan` tipado com métricas, dimensões, filtros, período, ordenação e limite em listas permitidas.
5. **Conversa**: estado estruturado por usuário/sessão e deltas sobre o QueryPlan anterior.
6. **RAG local**: documentos autorizados, chunks e índice local; dados numéricos não são recuperados como texto.
7. **Memória persistente**: preferências e turnos com expiração; nunca substitui o estado imediato ou a base factual.
8. **LLM**: Gemma recebe apenas instruções controladas, evidências e um contrato de resposta.
9. **Avaliação**: casos dourados com resposta numérica calculada, testes multi-turn e testes de segurança.

## Controles obrigatórios

- Ignorar mensagens `system` vindas do cliente.
- Rejeitar temas fora de transporte público/SEMOB com resposta curta e redirecionamento.
- Não aceitar SQL livre produzido pelo modelo ou pelo usuário.
- Compilar consultas somente de tabelas, métricas, dimensões e operadores permitidos.
- Usar parâmetros para todos os valores de filtro.
- Limitar linhas e tempo de execução.
- Exibir período, filtros, unidade, tabela de origem e aviso de cobertura parcial.
- Nunca preencher lacunas numéricas com conhecimento do modelo.
- Não enviar HTML bruto, dados pessoais, credenciais ou memória inteira ao endpoint do LLM.

## Estratégia de modelo

O endpoint atual permite inferência remota do `google/gemma-3-27b`, mas não demonstra capacidade de fine-tuning. A ordem segura é:

1. medir o Gemma atual em tarefas SEMOB;
2. concluir consulta determinística, escopo, RAG e avaliações;
3. gerar dataset supervisionado a partir de schemas e exemplos validados;
4. confirmar hardware, licença e revisão exata dos pesos;
5. executar QLoRA em ambiente separado;
6. comparar modelo base, RAG e adaptador com o mesmo conjunto dourado;
7. promover o adaptador somente se precisão e segurança melhorarem.

Fine-tuning ensina formato e comportamento. Ele não deve memorizar os dados operacionais, substituir o DuckDB ou ser usado como barreira contra vazamento.

## Estrutura planejada

```text
semob_ai/
  ingestion/       # HTML -> Parquet -> DuckDB
  analytics/       # catálogo, QueryPlan e executor
  guardrails/      # escopo e políticas de entrada/saída
  rag/             # índice textual local
  memory/          # contexto e preferências locais
  llm/             # cliente e prompts controlados
  evaluation/      # conjunto dourado e métricas
scripts/           # ingestão, avaliação e preparação QLoRA
prompts/           # prompts versionados
data/              # dados locais ignorados pelo Git
artifacts/         # índices e adaptadores ignorados pelo Git
```

## Critério de resposta numérica

Uma resposta só pode afirmar um número quando o executor retornar:

- consulta validada;
- período efetivamente coberto;
- valor e unidade;
- fonte canônica;
- contagem de linhas usada;
- alertas de qualidade aplicáveis.

Se qualquer item obrigatório estiver ausente, o chatbot deve dizer que não há dados suficientes ou pedir um filtro mais específico.
