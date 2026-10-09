# CMob: departures_by_line_hour

Fonte: CSV publico departures_by_line_hour.csv, normalizado dos HTMLs enviados.
Registros: 14006. Cobertura geral: 2026-07-01 a 2026-09-14.

Cobertura por mes (ausencia de registro nao significa zero; excecoes sao eventos esparsos):
- 2026-07: 31 dias presentes de 31, de 2026-07-01 a 2026-07-31. Mes completo: True.
- 2026-08: 31 dias presentes de 31, de 2026-08-01 a 2026-08-31. Mes completo: True.
- 2026-09: 14 dias presentes de 30, de 2026-09-01 a 2026-09-14. Mes completo: False.

Colunas: service_date (DATE), line_code (VARCHAR), time_band (VARCHAR), vehicles (BIGINT), trips (BIGINT), departures (VARCHAR), source_file (VARCHAR), source_period (VARCHAR), source_granularity (VARCHAR), source_generated_at (VARCHAR)

Numeros de passageiros nao podem ser divididos por linha ou horario: passengers_daily so tem data.
Calcule respostas numericas no DuckDB; nao estime valores ausentes ou causas para nao pagantes.
