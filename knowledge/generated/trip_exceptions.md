# CMob: trip_exceptions

Fonte: CSV publico trip_exceptions.csv, normalizado dos HTMLs enviados.
Registros: 122. Cobertura geral: 2026-07-01 a 2026-09-11.

Cobertura por mes (ausencia de registro nao significa zero; excecoes sao eventos esparsos):
- 2026-07: 20 dias presentes de 31, de 2026-07-01 a 2026-07-31. Mes completo: False.
- 2026-08: 18 dias presentes de 31, de 2026-08-02 a 2026-08-30. Mes completo: False.
- 2026-09: 4 dias presentes de 30, de 2026-09-02 a 2026-09-11. Mes completo: False.

Colunas: service_date (DATE), line_code (VARCHAR), service (VARCHAR), vehicle_prefix (VARCHAR), activity (VARCHAR), direction (VARCHAR), schedule (VARCHAR), departure_status (VARCHAR), arrival_status (VARCHAR), scheduled_start (VARCHAR), actual_start (VARCHAR), scheduled_end (VARCHAR), actual_end (VARCHAR), productive_km (DOUBLE), source_file (VARCHAR), source_period (VARCHAR), source_granularity (VARCHAR), source_generated_at (VARCHAR)

Numeros de passageiros nao podem ser divididos por linha ou horario: passengers_daily so tem data.
Calcule respostas numericas no DuckDB; nao estime valores ausentes ou causas para nao pagantes.
