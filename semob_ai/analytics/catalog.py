from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    expression: str
    unit: str
    label: str


TABLES: dict[str, dict[str, object]] = {
    "operation_daily": {
        "dimensions": {"service_date", "weekday"},
        "metrics": {
            "scheduled_trips": Metric("SUM(scheduled_trips)", "viagens", "Viagens programadas"),
            "completed_trips": Metric("SUM(completed_trips)", "viagens", "Viagens realizadas"),
            "trip_difference": Metric("SUM(trip_difference)", "viagens", "Diferença de viagens"),
            "productive_km": Metric("SUM(productive_km)", "km", "Quilometragem produtiva"),
            "deadhead_km": Metric("SUM(deadhead_km)", "km", "Quilometragem improdutiva"),
            "total_km": Metric("SUM(total_km)", "km", "Quilometragem total"),
            "average_vehicles": Metric("AVG(vehicles)", "veículos/dia", "Média de veículos"),
            "max_vehicles": Metric("MAX(vehicles)", "veículos", "Máximo de veículos"),
        },
    },
    "fulfillment_daily": {
        "dimensions": {"service_date"},
        "metrics": {
            "morning_scheduled": Metric("SUM(morning_scheduled)", "viagens", "Viagens programadas pela manhã"),
            "morning_completed": Metric("SUM(morning_completed)", "viagens", "Viagens realizadas pela manhã"),
            "afternoon_scheduled": Metric("SUM(afternoon_scheduled)", "viagens", "Viagens programadas à tarde"),
            "afternoon_completed": Metric("SUM(afternoon_completed)", "viagens", "Viagens realizadas à tarde"),
            "evening_scheduled": Metric("SUM(evening_scheduled)", "viagens", "Viagens programadas à noite"),
            "evening_completed": Metric("SUM(evening_completed)", "viagens", "Viagens realizadas à noite"),
            "scheduled_trips": Metric("SUM(scheduled_trips)", "viagens", "Viagens programadas"),
            "completed_trips": Metric("SUM(completed_trips)", "viagens", "Viagens realizadas"),
        },
    },
    "line_daily": {
        "dimensions": {"service_date", "line_code"},
        "metrics": {
            "trips": Metric("SUM(trips)", "viagens", "Viagens"),
            "total_km": Metric("SUM(total_km)", "km", "Quilometragem total"),
        },
    },
    "hour_daily": {
        "dimensions": {"service_date", "time_band"},
        "metrics": {
            "trips": Metric("SUM(trips)", "viagens", "Viagens"),
            "max_vehicles": Metric("MAX(vehicles)", "veículos", "Máximo de veículos"),
        },
    },
    "trips": {
        "dimensions": {"service_date", "line_code", "vehicle_prefix", "activity", "direction", "time_band"},
        "metrics": {
            "trip_count": Metric("COUNT(*)", "viagens", "Registros de viagens"),
            "productive_km": Metric("SUM(productive_km)", "km", "Quilometragem produtiva"),
            "deadhead_km": Metric("SUM(deadhead_km)", "km", "Quilometragem improdutiva"),
            "total_km": Metric("SUM(total_km)", "km", "Quilometragem total"),
        },
    },
    "trip_exceptions": {
        "dimensions": {"service_date", "line_code", "vehicle_prefix", "activity", "direction", "departure_status", "arrival_status"},
        "metrics": {"exception_count": Metric("COUNT(*)", "ocorrências", "Exceções de viagem")},
    },
    "passengers_daily": {
        "dimensions": {"service_date"},
        "metrics": {
            "total_passengers": Metric("SUM(total_passengers)", "passageiros", "Total de passageiros"),
            "paying_passengers": Metric("SUM(turnstile_passengers + advance_passengers)", "passageiros", "Passageiros pagantes (derivação operacional)"),
            "turnstile_passengers": Metric("SUM(turnstile_passengers)", "passageiros", "Passageiros de catraca"),
            "advance_passengers": Metric("SUM(advance_passengers)", "passageiros", "Passageiros antecipados"),
            "non_paying_passengers": Metric("SUM(non_paying_passengers)", "passageiros", "Passageiros não pagantes"),
        },
    },
    "card_balances_daily": {
        "dimensions": {"service_date", "series"},
        "metrics": {
            "credits_transferred": Metric("SUM(credits_transferred)", "R$", "Créditos transferidos"),
            "closing_balance": Metric("MAX(closing_balance)", "R$", "Saldo final"),
        },
    },
    "card_movements_daily": {
        "dimensions": {"service_date"},
        "metrics": {
            "total_sales": Metric("SUM(total_sales)", "R$", "Total de vendas"),
            "total_usage": Metric("SUM(total_usage)", "R$", "Total de utilização"),
            "circulating_credit": Metric("SUM(circulating_credit)", "R$", "Crédito circulante"),
        },
    },
}
