"""Export audited public CSV snapshots and grounded RAG documentation."""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import duckdb

from semob_ai.analytics.catalog import TABLES


def publish(database: Path, output: Path, knowledge: Path, metadata: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    knowledge.mkdir(parents=True, exist_ok=True)
    manifest = {"format_version": 1, "dataset": "cmob-semob-2026", "source_files": 44,
                "normalization": "ISO dates, UTF-8 CSV, comma delimiter, dot decimal, text identifiers",
                "precedence": "report for the service month, then monthly before fortnightly; exact duplicates removed",
                "excluded_public_columns": ["trip_exceptions.driver", "ingested_at"], "tables": {}}
    catalog_file = metadata / "catalog.json"
    if catalog_file.is_file():
        manifest["sources"] = json.loads(catalog_file.read_text(encoding="utf-8"))["sources"]
        manifest["source_files"] = len({item["source_file"] for item in manifest["sources"]})
    quality_file = metadata / "quality_report.json"
    if quality_file.is_file():
        manifest["quality"] = json.loads(quality_file.read_text(encoding="utf-8"))["tables"]
        for table in manifest["quality"].values():
            table["summary"].pop("parquet_file", None)
    summaries = []
    con = duckdb.connect(str(database), read_only=True)
    try:
        names = [row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_type='BASE TABLE' ORDER BY table_name").fetchall()
                 if row[0] in TABLES or row[0] == 'departures_by_line_hour']
        for name in names:
            columns = [(row[0], row[1]) for row in con.execute(f'DESCRIBE "{name}"').fetchall() if row[0] not in {"driver", "ingested_at"}]
            selected = ', '.join(f'"{column}"' for column, _ in columns)
            path = output / f"{name}.csv"
            con.execute(f'COPY (SELECT {selected} FROM "{name}" ORDER BY service_date, {selected}) TO ? (HEADER, DELIMITER \',\')', [str(path)])
            count, start, end = con.execute(f'SELECT count(*), min(service_date), max(service_date) FROM "{name}"').fetchone()
            periods = []
            for month, days in con.execute(f"SELECT strftime(service_date, '%Y-%m'), list(distinct service_date ORDER BY service_date) FROM \"{name}\" GROUP BY 1 ORDER BY 1").fetchall():
                year, month_number = map(int, month.split('-'))
                calendar_days = calendar.monthrange(year, month_number)[1]
                present = set(days)
                missing = [date(year, month_number, day).isoformat() for day in range(1, calendar_days + 1) if date(year, month_number, day) not in present]
                coverage = {"month": month, "observed_days": len(days), "start": str(days[0]), "end": str(days[-1]),
                            "calendar_days": calendar_days, "all_calendar_days_present": not missing, "missing_dates": missing}
                periods.append(coverage)
                for metric_name, metric in TABLES.get(name, {}).get("metrics", {}).items():
                    value = con.execute(f'SELECT {metric.expression} FROM "{name}" WHERE strftime(service_date, \'%Y-%m\') = ?', [month]).fetchone()[0]
                    summaries.append({"dataset": name, "month": month, "metric": metric_name, "value": value, "unit": metric.unit,
                                      **{key: val for key, val in coverage.items() if key not in {"month", "missing_dates"}},
                                      "missing_dates": "|".join(missing)})
            manifest["tables"][name] = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                        "columns": [{"name": column, "type": kind} for column, kind in columns],
                                        "row_count": count, "start": str(start), "end": str(end), "periods": periods}
            lines = [f"# CMob: {name}", "", f"Fonte: CSV publico {path.name}, normalizado dos HTMLs enviados.",
                     f"Registros: {count}. Cobertura geral: {start} a {end}.", "",
                     "Cobertura por mes (ausencia de registro nao significa zero; excecoes sao eventos esparsos):"]
            for period in periods:
                lines.append(f"- {period['month']}: {period['observed_days']} dias presentes de {period['calendar_days']}, de {period['start']} a {period['end']}. Mes completo: {period['all_calendar_days_present']}.")
            lines.extend(["", "Colunas: " + ', '.join(f"{column} ({kind})" for column, kind in columns),
                          "", "Numeros de passageiros nao podem ser divididos por linha ou horario: passengers_daily so tem data.",
                          "Calcule respostas numericas no DuckDB; nao estime valores ausentes ou causas para nao pagantes."])
            (knowledge / f"{name}.md").write_text('\n'.join(lines) + '\n', encoding='utf-8')
    finally:
        con.close()
    with (output / 'monthly_summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    manifest["summary"] = {"file": "monthly_summary.csv", "row_count": len(summaries),
                           "sha256": hashlib.sha256((output / 'monthly_summary.csv').read_bytes()).hexdigest()}
    month_names = {"2026-07": "julho de 2026", "2026-08": "agosto de 2026", "2026-09": "setembro de 2026"}
    for month in sorted({row['month'] for row in summaries}):
        lines = [f"# SEMOB: dados de {month_names.get(month, month)}", "",
                 "Agregados verificados; fonte: data/public/monthly_summary.csv. Consulte o DuckDB para novos filtros.",
                 "Nao compare totais de meses incompletos como se representassem o mesmo numero de dias.", ""]
        for row in summaries:
            if row['month'] != month or row['dataset'] not in {'passengers_daily', 'operation_daily', 'card_movements_daily'}:
                continue
            metric = TABLES[row['dataset']]['metrics'][row['metric']]
            lines.append(f"- {metric.label}: {row['value']} {row['unit']}; fonte {row['dataset']}, {row['observed_days']} dias registrados, {row['start']} a {row['end']}; todos os dias do mes presentes: {row['all_calendar_days_present']}.")
        (knowledge / f'period_{month}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    fingerprint = ''.join(table['sha256'] for table in manifest['tables'].values())
    manifest['data_version'] = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, default=Path('data/database/semob.duckdb'))
    parser.add_argument('--output', type=Path, default=Path('data/public'))
    args = parser.parse_args()
    manifest = publish(args.database, args.output, Path('knowledge/generated'), Path('data/metadata'))
    print(json.dumps({'version': manifest['data_version'], 'tables': len(manifest['tables']),
                      'rows': sum(table['row_count'] for table in manifest['tables'].values())}))


if __name__ == '__main__':
    main()
