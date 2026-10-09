# Dados publicos CMob / SEMOB

Snapshot normalizado dos 44 HTMLs fornecidos pelo responsavel pelo projeto,
que autorizou sua publicacao como dados publicos. Nao foi atribuido um municipio
ou uma licenca especifica que nao constam dessa autorizacao.

- CSV: UTF-8, separador virgula, decimal ponto, data ISO `YYYY-MM-DD`.
- Codigos de linha/veiculo sao texto: importar como texto para preservar zeros.
- Dez arquivos detalhados, mais `monthly_summary.csv` com agregados por mes.
- `manifest.json`: tipos, SHA-256, contagens, fontes e cobertura por tabela/mes.
- `source_file`, `source_period`, `source_granularity`, `source_generated_at`
  preservam a origem de cada linha. Os SHA-256 dos HTMLs ficam no manifesto.
- Identificacao do motorista foi removida dos CSVs publicos. Os HTMLs originais
  permanecem apenas na pasta local ignorada pelo Git.
- Totais/rodapes nao sao somados como registros. Na sobreposicao, vence o
  relatorio do mes do servico, depois o mensal sobre o quinzenal. Repeticoes
  exatas sao removidas. Divergencias e verificacoes ficam no manifesto.

## Cobertura e limites

Operacao: julho/agosto completos; setembro de 1 a 14. Passageiros: julho de
15 a 31, agosto de 1 a 31, setembro de 1 a 14. Movimentacao e saldos tem datas
ausentes: consulte `periods.missing_dates`. Excecoes sao eventos esparsos, nao
uma serie diaria completa. Ausencia de registro nunca significa zero.

Agosto: 288.378 pagantes operacionais (`Catraca + Antecipados`), 761.870 nao
pagantes, 1.050.248 no total. A causa/composicao de nao pagantes nao esta
identificada. Passageiros nao tem detalhe por linha, horario ou veiculo.

`monthly_summary.csv` conserva as definicoes do catalogo analitico. Agregados
de saldo/credito circulante exigem cautela: nao representam automaticamente
receita ou saldo contavel homologado. Dados inconsistentes da fonte nao foram
alterados para parecer corretos.

## Reconstruir

```sh
python -m scripts.build_cmob_data
python -m scripts.index_documents
```

O Docker executa estes comandos no build. O DuckDB nao precisa de um servidor
separado: e um arquivo analitico dentro do backend. O Neon continua responsavel
por usuarios e conversas. Um redeploy recria o snapshot a partir destes CSVs;
novos dados exigem nova normalizacao/publicacao, nao sao atualizados ao vivo.
