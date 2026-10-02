from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from semob_ai.analytics.catalog import TABLES


class DatePeriod(BaseModel):
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def ordered(self) -> "DatePeriod":
        if self.start and self.end and self.start > self.end:
            raise ValueError("A data inicial não pode ser posterior à final.")
        return self


class QueryFilter(BaseModel):
    field: str
    operator: Literal["eq", "in"] = "eq"
    value: str | int | float | list[str] | list[int] | list[float]


class OrderBy(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "desc"


class QueryPlan(BaseModel):
    intent: Literal["aggregate", "ranking", "comparison", "breakdown"] = "aggregate"
    dataset: str
    metrics: list[str] = Field(min_length=1, max_length=5)
    dimensions: list[str] = Field(default_factory=list, max_length=3)
    filters: list[QueryFilter] = Field(default_factory=list, max_length=8)
    period: DatePeriod = Field(default_factory=DatePeriod)
    order_by: list[OrderBy] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def allowed_catalog_entries(self) -> "QueryPlan":
        table = TABLES.get(self.dataset)
        if table is None:
            raise ValueError("Dataset não permitido.")
        allowed_metrics = set(table["metrics"])
        allowed_dimensions = set(table["dimensions"])
        if unknown := set(self.metrics) - allowed_metrics:
            raise ValueError(f"Métricas não permitidas: {sorted(unknown)}")
        if unknown := set(self.dimensions) - allowed_dimensions:
            raise ValueError(f"Dimensões não permitidas: {sorted(unknown)}")
        filterable = allowed_dimensions | {"service_date"}
        if unknown := {item.field for item in self.filters} - filterable:
            raise ValueError(f"Filtros não permitidos: {sorted(unknown)}")
        selectable = set(self.metrics) | set(self.dimensions)
        if unknown := {item.field for item in self.order_by} - selectable:
            raise ValueError(f"Ordenações não permitidas: {sorted(unknown)}")
        for item in self.filters:
            if item.operator == "in" and not isinstance(item.value, list):
                raise ValueError("O operador 'in' exige uma lista.")
            if item.operator == "in" and isinstance(item.value, list) and not item.value:
                raise ValueError("O operador 'in' não aceita uma lista vazia.")
        return self
