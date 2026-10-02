# Estado de implementação

| Fase | Estado | Evidência |
|---|---|---|
| 0. Auditoria | disponível localmente | volumes e cobertura real permanecem fora do Git |
| 1. HTML para Parquet/DuckDB | implementada | catálogo e proveniência gerados localmente |
| 2. Qualidade e dicionário | concluída | relatório sem falhas nas regras implementadas |
| 3. Analytics e QueryPlan | concluída | allowlists, parâmetros, conexão somente leitura |
| 4. Gemma | integrado para respostas textuais | API remota; detalhes do runtime ainda não expostos |
| 5. RAG | concluída para corpus inicial | índice híbrido local, corpus autorizado em `knowledge/` |
| 6. Memória | concluída | session state estruturado separado da memória persistente; resolução multi-turn |
| 7. Dataset supervisionado | concluída | 12 treino, 3 validação, verificação de vazamento |
| 8. QLoRA | preparado, não executado | sem checkpoint local e sem GPU CUDA detectada |
| 9. Avaliação | baseline concluída | 10/10 consultas douradas determinísticas |
| 10. Insights | baseline concluída | relatório descritivo local com alertas de cobertura |

## Pendências externas

- Confirmar com o responsável pelo Gemma a revisão exata, licença, tokenizer, chat template, quantização e janela de contexto.
- Obter ou provisionar hardware CUDA para treinar e avaliar QLoRA.
- Ampliar o corpus textual somente com documentos institucionais autorizados.
- Revisar as definições de negócio e indicadores com especialistas da SEMOB antes de uso decisório.
