from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


def br(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic exploratory SEMOB indicators.")
    parser.add_argument("--database", type=Path, default=Path("data/database/semob.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("data/exports/insights.md"))
    args = parser.parse_args()
    connection = duckdb.connect(str(args.database), read_only=True)
    try:
        period = connection.execute("SELECT MIN(service_date), MAX(service_date) FROM operation_daily").fetchone()
        scheduled, completed, productive, deadhead = connection.execute(
            "SELECT SUM(scheduled_trips), SUM(completed_trips), SUM(productive_km), SUM(deadhead_km) FROM operation_daily"
        ).fetchone()
        top_lines = connection.execute(
            "SELECT line_code, SUM(trips) AS trips FROM line_daily GROUP BY line_code ORDER BY trips DESC LIMIT 10"
        ).fetchall()
        top_hours = connection.execute(
            "SELECT time_band, SUM(trips) AS trips FROM hour_daily GROUP BY time_band ORDER BY trips DESC LIMIT 10"
        ).fetchall()
        passengers = connection.execute(
            "SELECT strftime(service_date, '%Y-%m') AS month, SUM(total_passengers) FROM passengers_daily GROUP BY month ORDER BY month"
        ).fetchall()
    finally:
        connection.close()

    completion_rate = completed / scheduled * 100 if scheduled else 0
    deadhead_share = deadhead / (productive + deadhead) * 100 if productive + deadhead else 0
    lines = [
        "# Indicadores exploratórios SEMOB",
        "",
        f"Período coberto pela operação diária: {period[0]} a {period[1]}.",
        "",
        "## Visão geral",
        "",
        f"- Viagens programadas: {scheduled:,}.",
        f"- Viagens realizadas: {completed:,}.",
        f"- Taxa de realização: {br(completion_rate, 2)}%.",
        f"- Participação da quilometragem improdutiva: {br(deadhead_share, 2)}%.",
        "",
        "## Linhas com mais viagens",
        "",
        "| Linha | Viagens |",
        "|---|---:|",
        *(f"| {line} | {trips:,} |" for line, trips in top_lines),
        "",
        "## Faixas horárias com mais viagens",
        "",
        "| Faixa | Viagens |",
        "|---|---:|",
        *(f"| {hour} | {trips:,} |" for hour, trips in top_hours),
        "",
        "## Passageiros por mês de serviço",
        "",
        "| Mês | Passageiros |",
        "|---|---:|",
        *(f"| {month} | {total:,} |" for month, total in passengers),
        "",
        "Os indicadores são descritivos e não demonstram causalidade. Julho e setembro possuem cobertura parcial em algumas tabelas.",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote deterministic insights to {args.output}.")


if __name__ == "__main__":
    main()

