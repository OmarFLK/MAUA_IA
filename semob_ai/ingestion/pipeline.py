from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from semob_ai.ingestion.parser import ParsedReport, parse_report


PROVENANCE_COLUMNS = {
    "source_file",
    "source_period",
    "source_granularity",
    "source_priority",
    "source_generated_at",
    "ingested_at",
}


@dataclass
class TableResult:
    name: str
    input_rows: int
    output_rows: int
    duplicates_removed: int
    rejected_rows: int
    min_date: str | None
    max_date: str | None
    parquet_file: str


@dataclass
class IngestionResult:
    source_files: int
    tables: list[TableResult]
    database_file: str
    catalog_file: str
    quality_file: str


def _quality_checks(name: str, frame: pd.DataFrame) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    if "service_date" in frame:
        checks.append({"check": "service_date_not_null", "failures": int(frame["service_date"].isna().sum())})
    numeric = frame.select_dtypes(include="number")
    for column in numeric.columns:
        if column == "source_priority" or column == "circulating_credit":
            continue
        checks.append({"check": f"{column}_non_negative", "failures": int((numeric[column].dropna() < 0).sum())})
    if {"productive_km", "deadhead_km", "total_km"}.issubset(frame.columns):
        delta = (frame["productive_km"] + frame["deadhead_km"] - frame["total_km"]).abs()
        checks.append({"check": "km_components_match_total", "failures": int((delta > 0.11).sum())})
    if {"scheduled_trips", "completed_trips"}.issubset(frame.columns):
        checks.append({"check": "completed_not_above_scheduled", "failures": int((frame["completed_trips"] > frame["scheduled_trips"]).sum())})
    return checks


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def run_ingestion(raw_root: Path, output_root: Path) -> IngestionResult:
    raw_root = raw_root.resolve()
    output_root = output_root.resolve()
    parquet_dir = output_root / "processed" / "parquet"
    database_dir = output_root / "database"
    metadata_dir = output_root / "metadata"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    database_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    html_files = sorted(raw_root.rglob("*.html"))
    ingested_at = datetime.now(timezone.utc).isoformat()
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    reports: list[ParsedReport] = []
    sources: list[dict[str, object]] = []
    for path in html_files:
        parsed = parse_report(path, raw_root, ingested_at)
        reports.extend(parsed)
        for report in parsed:
            grouped[report.table_name].extend(report.records)
            sources.append({"source_file": report.source_file, "sha256": report.sha256, "table": report.table_name})

    table_results: list[TableResult] = []
    quality_tables: dict[str, object] = {}
    catalog_tables: dict[str, object] = {}
    database_file = database_dir / "semob.duckdb"
    connection = duckdb.connect(str(database_file))
    try:
        for name in sorted(grouped):
            records = grouped[name]
            frame = pd.DataFrame.from_records(records)
            input_rows = len(frame)
            business_columns = [column for column in frame.columns if column not in PROVENANCE_COLUMNS]
            frame = frame.sort_values(["source_priority", "source_file"], ascending=[False, True])
            frame = frame.drop_duplicates(subset=business_columns, keep="first").reset_index(drop=True)
            duplicates_removed = input_rows - len(frame)
            rejected_rows = sum(report.rejected_rows for report in reports if report.table_name == name)
            if "service_date" in frame:
                frame["service_date"] = pd.to_datetime(frame["service_date"]).dt.date
                frame = frame.sort_values(["service_date"] + [column for column in business_columns if column != "service_date"]).reset_index(drop=True)

            parquet_file = parquet_dir / f"{name}.parquet"
            frame.drop(columns=["source_priority"]).to_parquet(parquet_file, index=False)
            connection.execute(f'DROP TABLE IF EXISTS "{name}"')
            connection.execute(f'CREATE TABLE "{name}" AS SELECT * FROM read_parquet(?)', [str(parquet_file)])

            min_date = str(frame["service_date"].min()) if "service_date" in frame and not frame.empty else None
            max_date = str(frame["service_date"].max()) if "service_date" in frame and not frame.empty else None
            result = TableResult(name, input_rows, len(frame), duplicates_removed, rejected_rows, min_date, max_date, str(parquet_file))
            table_results.append(result)
            quality_tables[name] = {"summary": asdict(result), "checks": _quality_checks(name, frame)}
            catalog_tables[name] = {
                "columns": [{"name": column, "dtype": str(dtype), "nulls": int(frame[column].isna().sum())} for column, dtype in frame.drop(columns=["source_priority"]).dtypes.items()],
                "row_count": len(frame),
                "date_range": {"min": min_date, "max": max_date},
                "source_files": sorted(frame["source_file"].unique().tolist()),
            }

        connection.execute("CREATE OR REPLACE VIEW available_tables AS SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'")
    finally:
        connection.close()

    catalog_file = metadata_dir / "catalog.json"
    quality_file = metadata_dir / "quality_report.json"
    _write_json(catalog_file, {"generated_at": ingested_at, "raw_root": str(raw_root), "sources": sources, "tables": catalog_tables})
    _write_json(quality_file, {"generated_at": ingested_at, "source_files": len(html_files), "tables": quality_tables})
    return IngestionResult(len(html_files), table_results, str(database_file), str(catalog_file), str(quality_file))

