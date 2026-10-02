from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from semob_ai.ingestion.schema import SCHEMAS, TableSchema


@dataclass
class ParsedReport:
    table_name: str
    records: list[dict[str, object]]
    rejected_rows: int
    source_file: str
    sha256: str


def normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_value.casefold().strip().split())


def _schema_for(headers: list[str]) -> TableSchema | None:
    normalized = tuple(normalize_header(header) for header in headers)
    for schema in SCHEMAS:
        if normalized == schema.headers:
            return schema
    return None


def _source_context(path: Path, raw_root: Path) -> dict[str, object]:
    relative = path.relative_to(raw_root).as_posix()
    parts = relative.split("/")
    period_match = next((re.fullmatch(r"([A-Za-z]+)_(\d{4})", part) for part in parts), None)
    period_match = period_match if period_match and period_match.group(0) else None
    period = period_match.group(0) if period_match else "unknown"
    granularity = "monthly" if any("mensal" in part.casefold() for part in parts) else "fortnightly"
    return {
        "source_file": relative,
        "source_period": period,
        "source_granularity": granularity,
        "source_priority": 2 if granularity == "monthly" else 1,
    }


def _generated_at(soup: BeautifulSoup, source_period: str) -> str | None:
    text_content = soup.get_text(" ", strip=True)
    numeric = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})", text_content)
    if numeric:
        return datetime.strptime(" ".join(numeric.groups()), "%d/%m/%Y %H:%M").isoformat()

    named = re.search(r"(\d{2})-(Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)\s+(\d{2}:\d{2})", text_content, re.IGNORECASE)
    if named:
        month_names = {name.casefold(): index for index, name in enumerate(("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"), 1)}
        year_match = re.search(r"(\d{4})", source_period)
        if year_match:
            return datetime(int(year_match.group(1)), month_names[named.group(2).casefold()], int(named.group(1)), *map(int, named.group(3).split(":"))).isoformat()
    return None


def _date_from_month_day(year_month: object, day: object) -> str | None:
    if not isinstance(year_month, str) or not isinstance(day, int):
        return None
    try:
        return datetime.strptime(f"{year_month}-{day:02d}", "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def parse_report(path: Path, raw_root: Path, ingested_at: str | None = None) -> list[ParsedReport]:
    raw = path.read_bytes()
    soup = BeautifulSoup(raw.decode("cp1252"), "html.parser")
    context = _source_context(path, raw_root)
    generated_at = _generated_at(soup, str(context["source_period"]))
    ingested_at = ingested_at or datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(raw).hexdigest()
    parsed: list[ParsedReport] = []

    for table in soup.find_all("table"):
        headers = [cell.get_text(" ", strip=True) for cell in table.find_all("th", recursive=False)]
        if not headers:
            headers = [cell.get_text(" ", strip=True) for cell in table.find_all("th")]
        schema = _schema_for(headers)
        if schema is None:
            continue

        records: list[dict[str, object]] = []
        rejected = 0
        for row in table.find_all("tr"):
            values = [cell.get_text(" ", strip=True) for cell in row.find_all("td", recursive=False)]
            if not values:
                continue
            if len(values) != len(schema.columns):
                rejected += 1
                continue
            try:
                record = {
                    column: parser(value)
                    for column, parser, value in zip(schema.columns, schema.parsers, values, strict=True)
                }
            except (TypeError, ValueError):
                rejected += 1
                continue

            if schema.name in {"passengers_daily", "card_balances_daily", "card_movements_daily"}:
                service_date = _date_from_month_day(record.pop("year_month"), record.pop("day"))
                if service_date is None:
                    continue
                record = {"service_date": service_date, **record}
            elif record.get("service_date") is None:
                continue

            record.update(
                source_file=context["source_file"],
                source_period=context["source_period"],
                source_granularity=context["source_granularity"],
                source_priority=context["source_priority"],
                source_generated_at=generated_at,
                ingested_at=ingested_at,
            )
            records.append(record)

        parsed.append(ParsedReport(schema.name, records, rejected, str(context["source_file"]), digest))

    return parsed

