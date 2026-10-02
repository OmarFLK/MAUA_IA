from __future__ import annotations

from pathlib import Path

import pandas as pd

from semob_ai.ingestion.parser import parse_report
from semob_ai.ingestion.pipeline import run_ingestion
from semob_ai.ingestion.schema import br_float, br_int


OPERATION_HTML = """<html><head><meta charset='Cp1252'></head><body>
<table class='data'>
<th>Data</th><th>diaSem</th><th>nrVeiculos</th><th>nrMaxVeicFx</th>
<th>nrViagensProgr</th><th>nrViagensRealiz</th><th>Dif Viagens</th>
<th>kmProd</th><th>kmImprod</th><th>kmTotal</th>
<tr><td>01/08/2026</td><td>Sab</td><td>37</td><td>35</td><td>924</td>
<td>920</td><td>4</td><td>6.889,4</td><td>344,3</td><td>7.233,7</td>
<tr><td>Total Geral</td><td></td><td></td><td></td><td>924</td>
<td>920</td><td>4</td><td>6.889,4</td><td>344,3</td><td>7.233,7</td>
</table></body></html>"""


def write_cp1252(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("cp1252"))


def test_brazilian_number_parsing() -> None:
    assert br_int("10.700") == 10_700
    assert br_float("20.434.667,35") == 20_434_667.35
    assert br_float("-3.380,00") == -3_380.0


def test_parser_handles_malformed_smart_report_and_totals(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    report = raw / "Agosto_2026" / "Mensal" / "Mensal_202608.html"
    write_cp1252(report, OPERATION_HTML)

    parsed = parse_report(report, raw)

    assert len(parsed) == 1
    assert parsed[0].table_name == "operation_daily"
    assert len(parsed[0].records) == 1
    assert parsed[0].records[0]["total_km"] == 7_233.7
    assert parsed[0].records[0]["source_granularity"] == "monthly"


def test_monthly_report_wins_over_fortnightly_duplicate(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_cp1252(raw / "Agosto_2026" / "Mensal" / "Mensal_202608.html", OPERATION_HTML)
    write_cp1252(raw / "Agosto_2026" / "Quinzenal" / "Quinzenal_202608.html", OPERATION_HTML)

    result = run_ingestion(raw, tmp_path / "data")
    operation = next(table for table in result.tables if table.name == "operation_daily")
    frame = pd.read_parquet(tmp_path / "data" / "processed" / "parquet" / "operation_daily.parquet")

    assert operation.input_rows == 2
    assert operation.output_rows == 1
    assert operation.duplicates_removed == 1
    assert frame.iloc[0]["source_granularity"] == "monthly"

