from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from semob_ai.analytics.catalog import TABLES, Metric
from semob_ai.analytics.query_plan import QueryPlan


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    units: dict[str, str]
    labels: dict[str, str]
    coverage_start: str | None
    coverage_end: str | None
    source_table: str
    filters_applied: list[str]


class AnalyticsExecutor:
    def __init__(self, database_file: Path):
        self.database_file = database_file

    def _compile(self, plan: QueryPlan) -> tuple[str, list[object]]:
        table = TABLES[plan.dataset]
        metrics: dict[str, Metric] = table["metrics"]  # type: ignore[assignment]
        selections = [f'"{dimension}"' for dimension in plan.dimensions]
        selections.extend(f'{metrics[name].expression} AS "{name}"' for name in plan.metrics)
        where = []
        parameters: list[object] = []
        if plan.period.start:
            where.append('"service_date" >= ?')
            parameters.append(plan.period.start)
        if plan.period.end:
            where.append('"service_date" <= ?')
            parameters.append(plan.period.end)
        for item in plan.filters:
            if item.operator == "eq":
                where.append(f'"{item.field}" = ?')
                parameters.append(item.value)  # type: ignore[arg-type]
            else:
                values = item.value if isinstance(item.value, list) else []
                placeholders = ", ".join("?" for _ in values)
                where.append(f'"{item.field}" IN ({placeholders})')
                parameters.extend(values)

        sql = f'SELECT {", ".join(selections)} FROM "{plan.dataset}"'
        if where:
            sql += " WHERE " + " AND ".join(where)
        if plan.dimensions:
            sql += " GROUP BY " + ", ".join(f'"{field}"' for field in plan.dimensions)
        if plan.order_by:
            sql += " ORDER BY " + ", ".join(f'"{item.field}" {item.direction.upper()}' for item in plan.order_by)
        elif plan.dimensions:
            sql += " ORDER BY " + ", ".join(f'"{field}" ASC' for field in plan.dimensions)
        sql += " LIMIT ?"
        parameters.append(plan.limit)
        return sql, parameters

    def execute(self, plan: QueryPlan) -> QueryResult:
        if not self.database_file.is_file():
            raise FileNotFoundError("Banco SEMOB ainda não foi gerado. Execute a ingestão.")
        sql, parameters = self._compile(plan)
        connection = duckdb.connect(str(self.database_file), read_only=True)
        try:
            coverage = connection.execute(
                f'SELECT MIN(service_date), MAX(service_date) FROM "{plan.dataset}"'
            ).fetchone()
            cursor = connection.execute(sql, parameters)
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            connection.close()

        metrics: dict[str, Metric] = TABLES[plan.dataset]["metrics"]  # type: ignore[assignment]
        filters = []
        if plan.period.start or plan.period.end:
            filters.append(f"período {plan.period.start or 'início'} a {plan.period.end or 'fim'}")
        filters.extend(f"{item.field} {item.operator} {item.value}" for item in plan.filters)
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            units={name: metrics[name].unit for name in plan.metrics},
            labels={name: metrics[name].label for name in plan.metrics},
            coverage_start=str(coverage[0]) if coverage and coverage[0] else None,
            coverage_end=str(coverage[1]) if coverage and coverage[1] else None,
            source_table=plan.dataset,
            filters_applied=filters,
        )

