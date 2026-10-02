from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime

from semob_ai.analytics.query_plan import DatePeriod, OrderBy, QueryFilter, QueryPlan


MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _period(question: str) -> DatePeriod:
    dates = [datetime.strptime(value, "%d/%m/%Y").date() for value in re.findall(r"\b\d{2}/\d{2}/\d{4}\b", question)]
    if len(dates) >= 2:
        return DatePeriod(start=min(dates), end=max(dates))
    if len(dates) == 1:
        return DatePeriod(start=dates[0], end=dates[0])
    for name, month in MONTHS.items():
        if name in question:
            year_match = re.search(r"\b(20\d{2})\b", question)
            year = int(year_match.group(1)) if year_match else 2026
            return DatePeriod(start=date(year, month, 1), end=date(year, month, calendar.monthrange(year, month)[1]))
    return DatePeriod()


def plan_question(raw_question: str) -> QueryPlan | None:
    question = _plain(raw_question)
    if any(term in question for term in ("o que e", "defina", "qual o significado", "o que significa", "conceito de")):
        return None
    period = _period(question)
    dimensions: list[str] = []
    filters: list[QueryFilter] = []
    limit_match = re.search(r"\b(?:top|maiores|menores)\s+(\d{1,3})\b", question) or re.search(r"\b(\d{1,3})\s+(?:linhas|dias|faixas)\b", question)
    limit = min(int(limit_match.group(1)), 50) if limit_match else 20

    if "por dia" in question or "diari" in question:
        dimensions.append("service_date")

    if any(term in question for term in ("passageir", "catraca", "pagante", "pagaram", "pagou")):
        has_non_paying = bool(re.search(r"\bnao\s+(?:sao\s+|eram\s+|foram\s+)?pag", question))
        has_paying = any(term in question for term in ("pagante", "pagaram", "pagou")) and not (has_non_paying and " e " not in question)
        if has_non_paying and has_paying:
            return QueryPlan(
                intent="breakdown",
                dataset="passengers_daily",
                metrics=["paying_passengers", "non_paying_passengers", "total_passengers"],
                dimensions=dimensions,
                period=period,
                limit=limit,
            )
        metric = "non_paying_passengers" if has_non_paying else "turnstile_passengers" if "catraca" in question else "paying_passengers" if has_paying else "total_passengers"
        return QueryPlan(dataset="passengers_daily", metrics=[metric], dimensions=dimensions, period=period, limit=limit)

    if any(term in question for term in ("saldo", "credito transferido")):
        metric = "credits_transferred" if "transfer" in question else "closing_balance"
        return QueryPlan(dataset="card_balances_daily", metrics=[metric], dimensions=dimensions, period=period, limit=limit)

    if any(term in question for term in ("venda", "utilizacao", "credito circulante")):
        metric = "total_sales" if "venda" in question else "total_usage" if "utilizacao" in question else "circulating_credit"
        return QueryPlan(dataset="card_movements_daily", metrics=[metric], dimensions=dimensions, period=period, limit=limit)

    if any(term in question for term in ("exce", "nao realizada", "nao iniciada", "nao terminada")):
        if "linha" in question:
            dimensions.append("line_code")
        return QueryPlan(
            dataset="trip_exceptions",
            metrics=["exception_count"],
            dimensions=list(dict.fromkeys(dimensions)),
            period=period,
            order_by=[OrderBy(field="exception_count", direction="desc")] if dimensions else [],
            limit=limit,
        )

    line_group = "por linha" in question or "linhas" in question
    hour_group = any(term in question for term in ("por horario", "por faixa", "faixa horaria"))
    if line_group:
        dimensions.append("line_code")
    if hour_group:
        dimensions.append("time_band")

    line_match = re.search(r"\blinha\s+([a-z0-9.-]+)\b", question)
    if line_match and line_match.group(1) not in {"com", "por", "que"}:
        filters.append(QueryFilter(field="line_code", value=line_match.group(1).upper()))

    if filters and any(term in question for term in ("analise", "dados", "desempenho")):
        return QueryPlan(dataset="line_daily", metrics=["trips", "total_km"], filters=filters, period=period, limit=limit)

    if "km" in question or "quilometr" in question:
        metric = "deadhead_km" if "improdut" in question else "productive_km" if "produt" in question else "total_km"
        dataset = "line_daily" if line_group or filters else "operation_daily"
    elif "viagem" in question or "viagens" in question:
        if line_group or filters:
            dataset, metric = "line_daily", "trips"
        elif hour_group:
            dataset, metric = "hour_daily", "trips"
        else:
            dataset = "operation_daily"
            metric = "scheduled_trips" if "programad" in question else "trip_difference" if "diferenca" in question else "completed_trips"
    elif "veiculo" in question:
        dataset = "hour_daily" if hour_group else "operation_daily"
        metric = "max_vehicles" if any(term in question for term in ("max", "maior", "pico")) else "average_vehicles"
        if dataset == "hour_daily" and metric == "average_vehicles":
            metric = "max_vehicles"
    else:
        return None

    dimensions = list(dict.fromkeys(dimensions))
    order = [OrderBy(field=metric, direction="asc" if "menor" in question else "desc")] if dimensions and any(term in question for term in ("maior", "menor", "mais", "top", "ranking")) else []
    return QueryPlan(intent="ranking" if order else "aggregate", dataset=dataset, metrics=[metric], dimensions=dimensions, filters=filters, period=period, order_by=order, limit=limit)
