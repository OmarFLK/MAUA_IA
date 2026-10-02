from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


Parser = Callable[[str], object]


@dataclass(frozen=True)
class TableSchema:
    name: str
    headers: tuple[str, ...]
    columns: tuple[str, ...]
    parsers: tuple[Parser, ...]


def text(value: str) -> str | None:
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def br_int(value: str) -> int | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    return int(cleaned.replace(".", "").replace(" ", ""))


def br_float(value: str) -> float | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    return float(cleaned.replace(".", "").replace(",", ".").replace(" ", ""))


def date_br(value: str) -> str | None:
    from datetime import datetime

    cleaned = value.strip()
    if not cleaned or cleaned.casefold().startswith("total"):
        return None
    return datetime.strptime(cleaned, "%d/%m/%Y").date().isoformat()


SCHEMAS = (
    TableSchema(
        "operation_daily",
        ("data", "diasem", "nrveiculos", "nrmaxveicfx", "nrviagensprogr", "nrviagensrealiz", "dif viagens", "kmprod", "kmimprod", "kmtotal"),
        ("service_date", "weekday", "vehicles", "max_vehicles_interval", "scheduled_trips", "completed_trips", "trip_difference", "productive_km", "deadhead_km", "total_km"),
        (date_br, text, br_int, br_int, br_int, br_int, br_int, br_float, br_float, br_float),
    ),
    TableSchema(
        "fulfillment_daily",
        ("data", "manha_p", "manha_r", "tarde_p", "tarde_r", "noite_p", "noite_r", "programadas", "realizadas"),
        ("service_date", "morning_scheduled", "morning_completed", "afternoon_scheduled", "afternoon_completed", "evening_scheduled", "evening_completed", "scheduled_trips", "completed_trips"),
        (date_br, br_int, br_int, br_int, br_int, br_int, br_int, br_int, br_int),
    ),
    TableSchema(
        "departures_by_line_hour",
        ("data", "linha", "fx_hor", "nr_veiculos", "nr_viagens", "partidas"),
        ("service_date", "line_code", "time_band", "vehicles", "trips", "departures"),
        (date_br, text, text, br_int, br_int, text),
    ),
    TableSchema(
        "line_daily",
        ("data", "linha", "kmtotal", "nrviagens"),
        ("service_date", "line_code", "total_km", "trips"),
        (date_br, text, br_float, br_int),
    ),
    TableSchema(
        "hour_daily",
        ("data", "fx_hor", "nr_veiculos", "nr_viagens"),
        ("service_date", "time_band", "vehicles", "trips"),
        (date_br, text, br_int, br_int),
    ),
    TableSchema(
        "trips",
        ("data", "linha", "prefixo", "atividade", "sentido", "fx_hor", "iniciorealizado", "fimrealizado", "kmprod", "kmimprod", "kmtotal"),
        ("service_date", "line_code", "vehicle_prefix", "activity", "direction", "time_band", "actual_start", "actual_end", "productive_km", "deadhead_km", "total_km"),
        (date_br, text, text, text, text, text, text, text, br_float, br_float, br_float),
    ),
    TableSchema(
        "trip_exceptions",
        ("data", "linha", "atendimento", "prefixo", "atividade", "motorista", "sentido", "tabela", "statussaida", "statuschegada", "inicioprogramado", "iniciorealizado", "fimprogramado", "fimrealizado", "kmprod"),
        ("service_date", "line_code", "service", "vehicle_prefix", "activity", "driver", "direction", "schedule", "departure_status", "arrival_status", "scheduled_start", "actual_start", "scheduled_end", "actual_end", "productive_km"),
        (date_br, text, text, text, text, text, text, text, text, text, text, text, text, text, br_float),
    ),
    TableSchema(
        "passengers_daily",
        ("mes", "dia", "catraca", "antecipados", "nao pagantes", "total passageiros"),
        ("year_month", "day", "turnstile_passengers", "advance_passengers", "non_paying_passengers", "total_passengers"),
        (text, br_int, br_int, br_int, br_int, br_int),
    ),
    TableSchema(
        "card_balances_daily",
        ("mes", "dia", "serie", "creditos transferidos para cartoes", "saldo final"),
        ("year_month", "day", "series", "credits_transferred", "closing_balance"),
        (text, br_int, br_int, br_float, br_float),
    ),
    TableSchema(
        "card_movements_daily",
        ("mes", "dia", "total vendas", "total utilizacao", "credito circulante"),
        ("year_month", "day", "total_sales", "total_usage", "circulating_credit"),
        (text, br_int, br_float, br_float, br_float),
    ),
)

