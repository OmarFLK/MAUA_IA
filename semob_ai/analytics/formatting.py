from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal

from semob_ai.analytics.executor import QueryResult
from semob_ai.analytics.query_plan import QueryPlan


def _value(value: object, unit: str | None = None) -> str:
    if value is None:
        return "sem dado"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, (int, float, Decimal)):
        decimals = 2 if unit in {"km", "R$", "veículos/dia"} else 0
        rendered = f"{float(value):,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"R$ {rendered}" if unit == "R$" else rendered
    return str(value)


def _coverage_warning(plan: QueryPlan, result: QueryResult) -> str | None:
    starts_before = bool(plan.period.start and result.coverage_start and str(plan.period.start) < result.coverage_start)
    ends_after = bool(plan.period.end and result.coverage_end and str(plan.period.end) > result.coverage_end)
    missing_days = bool(plan.period.start and plan.period.end and result.observed_days
                        and result.source_table != 'trip_exceptions'
                        and result.observed_days < (plan.period.end - plan.period.start).days + 1)
    if starts_before or ends_after or missing_days:
        return "Aviso: o periodo solicitado nao possui registros para todos os dias na fonte; o resultado é parcial."
    return None


def format_result(plan: QueryPlan, result: QueryResult) -> str:
    if not result.rows:
        return (
            "Não encontrei registros para esses filtros. "
            f"A tabela `{result.source_table}` cobre {result.coverage_start} a {result.coverage_end}."
        )
    lines: list[str] = []
    if plan.dimensions == ['service_date'] and len(result.rows) > 1:
        for metric in plan.metrics:
            numeric_rows = [row for row in result.rows if isinstance(row.get(metric), (int, float, Decimal))]
            if numeric_rows:
                highest = max(numeric_rows, key=lambda row: row[metric])
                lowest = min(numeric_rows, key=lambda row: row[metric])
                lines.append(f"**{result.labels[metric]}**, entre as {len(numeric_rows)} datas retornadas: "
                             f"maximo {_value(highest[metric], result.units[metric])} em {_value(highest['service_date'])}; "
                             f"minimo {_value(lowest[metric], result.units[metric])} em {_value(lowest['service_date'])}.")
        lines.append('')
    if not plan.dimensions and len(result.rows) == 1:
        row = result.rows[0]
        for metric in plan.metrics:
            lines.append(f"**{result.labels[metric]}:** {_value(row[metric], result.units[metric])} {'' if result.units[metric] == 'R$' else result.units[metric]}".rstrip())
    else:
        headers = plan.dimensions + plan.metrics
        lines.append("| " + " | ".join(result.labels.get(header, header) for header in headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in result.rows:
            lines.append("| " + " | ".join(_value(row[header], result.units.get(header)) for header in headers) + " |")

    requested = []
    if plan.period.start or plan.period.end:
        requested.append(f"período solicitado: {plan.period.start or 'início'} a {plan.period.end or 'fim'}")
    requested.extend(result.filters_applied[1:] if requested else result.filters_applied)
    lines.extend([
        "",
        f"Fonte: `{result.source_table}`. Cobertura disponível: {result.coverage_start} a {result.coverage_end}.",
        f"Filtros: {', '.join(requested) if requested else 'nenhum; todo o período disponível'}.",
    ])
    if warning := _coverage_warning(plan, result):
        lines.append(warning)
    lines.append(f"Dias com registros no recorte: {result.observed_days}; intervalo observado: {result.observed_start} a {result.observed_end}. Ausencia de registro nao significa zero.")
    return "\n".join(lines)


def _period_label(plan: QueryPlan) -> str:
    start, end = plan.period.start, plan.period.end
    months = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
    if start and end and start.day == 1 and start.year == end.year and start.month == end.month:
        return f"{months[start.month - 1]} de {start.year}"
    return f"{start or 'início'} a {end or 'fim'}"


def format_breakdown(plan: QueryPlan, result: QueryResult) -> str:
    if not result.rows or plan.dimensions:
        return format_result(plan, result)
    row = result.rows[0]
    paying = float(row.get("paying_passengers") or 0)
    non_paying = float(row.get("non_paying_passengers") or 0)
    total = float(row.get("total_passengers") or paying + non_paying)
    paying_share = paying / total * 100 if total else 0
    non_paying_share = non_paying / total * 100 if total else 0
    lines = [
            f"Em **{_period_label(plan)}**:",
            "",
            f"- **Pagantes:** {_value(paying, 'passageiros')} passageiros ({_value(paying_share, 'km')}%).",
            f"- **Não pagantes:** {_value(non_paying, 'passageiros')} passageiros ({_value(non_paying_share, 'km')}%).",
            f"- **Total:** {_value(total, 'passageiros')} passageiros.",
            "",
            f"**Leitura:** no período, {'não pagantes' if non_paying_share >= paying_share else 'pagantes'} representaram a maior parcela do total "
            f"({_value(max(paying_share, non_paying_share), 'km')}%). Essa proporção descreve o recorte, mas não explica suas causas.",
            "",
            "Pagantes é uma derivação operacional: `Catraca + Antecipados`. A definição ainda depende de homologação formal da SEMOB.",
            f"Fonte: `{result.source_table}`. Cobertura disponível: {result.coverage_start} a {result.coverage_end}.",
    ]
    if warning := _coverage_warning(plan, result):
        lines.append(warning)
    lines.append(f"Dias com registros no recorte: {result.observed_days}; intervalo observado: {result.observed_start} a {result.observed_end}.")
    return "\n".join(lines)


def format_comparison(
    primary_plan: QueryPlan,
    primary: QueryResult,
    comparison_plan: QueryPlan,
    comparison: QueryResult,
    *,
    explanation: bool = False,
) -> str:
    if not primary.rows or not comparison.rows:
        missing = primary if not primary.rows else comparison
        return format_result(primary_plan if not primary.rows else comparison_plan, missing)
    first_plan, first, second_plan, second = (
        (comparison_plan, comparison, primary_plan, primary)
        if (comparison_plan.period.start or date.min) <= (primary_plan.period.start or date.min)
        else (primary_plan, primary, comparison_plan, comparison)
    )
    lines = [f"Comparação entre **{_period_label(first_plan)}** e **{_period_label(second_plan)}**:", ""]
    dimensions = primary_plan.dimensions
    if not dimensions:
        first_row, second_row = first.rows[0], second.rows[0]
        for metric in primary_plan.metrics:
            first_value = float(first_row.get(metric) or 0)
            second_value = float(second_row.get(metric) or 0)
            difference = second_value - first_value
            variation = difference / first_value * 100 if first_value else None
            unit = primary.units[metric]
            lines.extend(
                (
                    f"**{primary.labels[metric]}**",
                    f"- {_period_label(first_plan)}: {_value(first_value, unit)} {'' if unit == 'R$' else unit}".rstrip(),
                    f"- {_period_label(second_plan)}: {_value(second_value, unit)} {'' if unit == 'R$' else unit}".rstrip(),
                    f"- Diferença: {_value(difference, unit)} {'' if unit == 'R$' else unit}".rstrip(),
                    f"- Variação: {_value(variation, 'km')}%" if variation is not None else "- Variação: não calculável porque o valor inicial é zero.",
                    "",
                )
            )
    else:
        metric = primary_plan.metrics[0]
        def keyed(result: QueryResult) -> dict[tuple[object, ...], float]:
            return {tuple(row[field] for field in dimensions): float(row.get(metric) or 0) for row in result.rows}
        first_values, second_values = keyed(first), keyed(second)
        rows = []
        for key in set(first_values) | set(second_values):
            before, after = first_values.get(key, 0), second_values.get(key, 0)
            difference = after - before
            variation = difference / before * 100 if before else None
            rows.append((key, before, after, difference, variation))
        rows.sort(key=lambda item: item[3])
        lines.extend((
            "| " + " | ".join(dimensions + [_period_label(first_plan), _period_label(second_plan), "Diferença", "Variação"]) + " |",
            "| " + " | ".join("---" for _ in range(len(dimensions) + 4)) + " |",
        ))
        unit = primary.units[metric]
        for key, before, after, difference, variation in rows[:20]:
            rendered = [str(value) for value in key] + [_value(before, unit), _value(after, unit), _value(difference, unit), f"{_value(variation, 'km')}%" if variation is not None else "n/a"]
            lines.append("| " + " | ".join(rendered) + " |")
    if explanation:
        lines.extend(("", "Os dados mostram diferenças e possíveis associações, mas não demonstram a causa. Para atribuir causalidade seriam necessárias evidências operacionais adicionais."))
    warnings = [warning for warning in (_coverage_warning(first_plan, first), _coverage_warning(second_plan, second)) if warning]
    if warnings:
        lines.extend((
            "",
            "**Leitura:** ao menos um período tem cobertura parcial. As diferenças observadas podem refletir quantidades distintas de dias disponíveis, portanto não devem ser interpretadas como tendência operacional.",
        ))
    elif not dimensions:
        variations: list[tuple[str, float]] = []
        first_row, second_row = first.rows[0], second.rows[0]
        for metric in primary_plan.metrics:
            before = float(first_row.get(metric) or 0)
            after = float(second_row.get(metric) or 0)
            if before:
                variations.append((primary.labels[metric], (after - before) / before * 100))
        if variations:
            label, variation = max(variations, key=lambda item: abs(item[1]))
            direction = "aumento" if variation >= 0 else "redução"
            lines.extend((
                "",
                f"**Leitura:** a maior mudança proporcional foi em {label}, com {direction} de {_value(abs(variation), 'km')}%. O dado mostra variação, mas não determina sua causa.",
            ))
    lines.extend(("", f"Fonte: `{primary.source_table}`. Cálculos executados localmente sobre os dois períodos."))
    for period_plan, period_result in ((first_plan, first), (second_plan, second)):
        status = "cobertura parcial" if _coverage_warning(period_plan, period_result) else "dentro da cobertura disponível"
        start = max(str(period_plan.period.start or ""), period_result.coverage_start or "")
        end = min(str(period_plan.period.end or "9999-12-31"), period_result.coverage_end or "9999-12-31")
        lines.append(f"- {_period_label(period_plan)}: {status}; intervalo disponível: {start} a {end}.")
    if warnings:
        lines.append("Aviso: ao menos um dos períodos tem cobertura parcial; compare os valores com cautela.")
    return "\n".join(lines).rstrip()


def format_projection(plan: QueryPlan, result: QueryResult) -> str:
    if plan.dimensions or not result.rows or not plan.period.start or not plan.period.end:
        return "Não há base suficiente para calcular uma projeção mensal simples com esse recorte."

    coverage_start = date.fromisoformat(result.coverage_start) if result.coverage_start else plan.period.start
    coverage_end = date.fromisoformat(result.coverage_end) if result.coverage_end else plan.period.end
    observed_start = max(plan.period.start, coverage_start)
    observed_end = min(plan.period.end, coverage_end)
    observed_days = result.observed_days
    if observed_days <= 0:
        return "Não há dias observados no período para calcular a projeção."

    if plan.period.start.month == 12:
        next_year, next_month = plan.period.start.year + 1, 1
    else:
        next_year, next_month = plan.period.start.year, plan.period.start.month + 1
    next_days = calendar.monthrange(next_year, next_month)[1]
    month_names = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")

    row = result.rows[0]
    lines = [f"**Projeção simples para {month_names[next_month - 1]} de {next_year}:**", ""]
    for metric in plan.metrics:
        current_value = float(row.get(metric) or 0)
        projected_value = current_value / observed_days * next_days
        unit = result.units[metric]
        lines.append(
            f"- **{result.labels[metric]}:** {_value(projected_value, unit)} {'' if unit == 'R$' else unit}".rstrip()
        )
    lines.extend(
        (
            "",
            f"Método: média diária dos {observed_days} dias cobertos no período-base, multiplicada pelos {next_days} dias do mês projetado.",
            "A projeção é uma extrapolação linear; não incorpora sazonalidade, mudanças operacionais ou fatores externos.",
        )
    )
    return "\n".join(lines)
