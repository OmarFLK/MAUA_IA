# CMob: passengers_daily

Fonte: CSV publico passengers_daily.csv, normalizado dos HTMLs enviados.
Registros: 62. Cobertura geral: 2026-07-15 a 2026-09-14.

Cobertura por mes (ausencia de registro nao significa zero; excecoes sao eventos esparsos):
- 2026-07: 17 dias presentes de 31, de 2026-07-15 a 2026-07-31. Mes completo: False.
- 2026-08: 31 dias presentes de 31, de 2026-08-01 a 2026-08-31. Mes completo: True.
- 2026-09: 14 dias presentes de 30, de 2026-09-01 a 2026-09-14. Mes completo: False.

Colunas: service_date (DATE), turnstile_passengers (BIGINT), advance_passengers (BIGINT), non_paying_passengers (BIGINT), total_passengers (BIGINT), source_file (VARCHAR), source_period (VARCHAR), source_granularity (VARCHAR), source_generated_at (VARCHAR)

Numeros de passageiros nao podem ser divididos por linha ou horario: passengers_daily so tem data.
Calcule respostas numericas no DuckDB; nao estime valores ausentes ou causas para nao pagantes.
