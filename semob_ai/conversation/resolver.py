from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date

from semob_ai.analytics.planner import MONTHS, plan_question
from semob_ai.analytics.query_plan import DatePeriod, OrderBy, QueryFilter, QueryPlan
from semob_ai.conversation.models import ConversationState, FollowUpType, ResolvedRequest
from semob_ai.guardrails.scope import is_conversational_message


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _month_period(year: int, month: int) -> DatePeriod:
    return DatePeriod(start=date(year, month, 1), end=date(year, month, calendar.monthrange(year, month)[1]))


def _shift_month(period: DatePeriod, offset: int) -> DatePeriod | None:
    anchor = period.start or period.end
    if anchor is None:
        return None
    month_index = anchor.year * 12 + anchor.month - 1 + offset
    return _month_period(month_index // 12, month_index % 12 + 1)


def _named_periods(question: str, reference_year: int = 2026) -> list[DatePeriod]:
    year_match = re.search(r"\b(20\d{2})\b", question)
    year = int(year_match.group(1)) if year_match else reference_year
    found = [(question.index(name), _month_period(year, month)) for name, month in MONTHS.items() if name in question]
    return [period for _, period in sorted(found, key=lambda item: item[0])]


def _subject(dataset: str) -> str:
    return {
        "passengers_daily": "passageiros",
        "operation_daily": "operação",
        "fulfillment_daily": "cumprimento de viagens",
        "line_daily": "linhas",
        "hour_daily": "faixas horárias",
        "trips": "viagens",
        "trip_exceptions": "exceções de viagem",
        "card_balances_daily": "saldos de bilhetagem",
        "card_movements_daily": "movimentação de bilhetagem",
    }.get(dataset, dataset)


def _copy_plan(plan: QueryPlan, **changes: object) -> QueryPlan:
    payload = plan.model_dump()
    payload.update(changes)
    return QueryPlan.model_validate(payload)


INSIGHT_CUES = (
    "insight",
    "o que voce acha",
    "qual sua conclusao",
    "qual a sua conclusao",
    "conclusao",
    "interprete",
    "interpretacao",
    "explique melhor",
    "me explique",
    "fale mais",
    "me fale mais",
    "analise esses dados",
    "analise desses dados",
    "analisa esses dados",
    "analisa esses resultados",
    "analise os resultados",
    "faca uma analise",
    "aprofund",
    "pontos de atencao",
    "recomend",
)

CONFIRMATION_CUES = (
    "pode fazer",
    "pode sim",
    "sim pode",
    "faca isso",
    "faz isso",
    "manda ver",
    "prossiga",
    "continue",
    "continua",
    "quero sim",
    "use os dados",
    "pode usar os dados",
)

SHORT_CONFIRMATIONS = {"sim", "claro", "ok", "okay", "isso", "isso mesmo", "confirmo", "pode", "vamos"}

CONTEXT_REFERENCES = (
    "esses dados",
    "desses dados",
    "esses resultados",
    "desse resultado",
    "sobre isso",
    "nisso",
    "essa informacao",
    "a resposta anterior",
    "dados que voce citou",
    "dados citados",
    "como voce falou",
)

PROJECTION_CUES = ("projecao", "projetar", "projete", "previsao", "prever", "estimativa", "estimar", "proximo mes")

COMPARISON_CUES = (
    "compara",
    "compare",
    "comparou",
    "comparacao",
    "em relacao",
    "mes passado",
    "mes anterior",
    "mes antes de",
    "variacao",
    "aumentou",
    "diminuiu",
    "qual foi maior",
    "qual teve mais",
    "diferenca",
    "maior queda",
)


def _contains_any(question: str, cues: tuple[str, ...]) -> bool:
    return any(cue in question for cue in cues)


def _is_confirmation(question: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s]", "", question).strip()
    return cleaned in SHORT_CONFIRMATIONS or _contains_any(cleaned, CONFIRMATION_CUES)


def _asks_projection(question: str) -> bool:
    return _contains_any(question, PROJECTION_CUES)


def _asks_comparison(question: str) -> bool:
    return _contains_any(question, COMPARISON_CUES)


def _is_insight_request(question: str) -> bool:
    return _contains_any(question, INSIGHT_CUES)


def _resolve_periods(
    question: str, plan: QueryPlan, previous_comparison: QueryPlan | None,
    periods: list[DatePeriod],
) -> tuple[QueryPlan, QueryPlan | None]:
    """Resolve explicit anchors before relative dates, for new and existing sessions alike."""
    comparison = previous_comparison
    relative_before = bool(re.search(r"mes (?:passado|anterior|antes de)|periodo anterior", question))
    comparing = _asks_comparison(question) or "os dois" in question or "valor anterior" in question
    if comparing and relative_before:
        if periods:
            plan = _copy_plan(plan, period=periods[-1])
        shifted = _shift_month(plan.period, -1)
        comparison = _copy_plan(plan, period=shifted) if shifted else None
    elif comparing and len(periods) >= 2:
        plan = _copy_plan(plan, period=periods[-1])
        comparison = _copy_plan(plan, period=periods[0])
    elif comparing and periods:
        comparison = _copy_plan(plan, period=periods[-1])
    elif periods:
        if plan.period != periods[-1]:
            comparison = plan.model_copy(deep=True)
        plan = _copy_plan(plan, period=periods[-1])
    elif relative_before or question in {"antes", "e antes?"}:
        shifted = _shift_month(plan.period, -1)
        if shifted:
            comparison = plan.model_copy(deep=True)
            plan = _copy_plan(plan, period=shifted)
    elif any(term in question for term in ("mes seguinte", "periodo seguinte")) or question in {"depois", "e depois?"}:
        shifted = _shift_month(plan.period, 1)
        if shifted:
            comparison = plan.model_copy(deep=True)
            plan = _copy_plan(plan, period=shifted)
    if comparison and comparison.period == plan.period:
        comparison = None
    return plan, comparison


class FollowUpResolver:
    FOLLOW_UP_PREFIXES = ("e ", "mas ", "nesse ", "naquele ", "isso ", "ela ", "ele ", "por que", "porque")

    def looks_like_follow_up(self, message: str, state: ConversationState) -> bool:
        if not state.has_analytics_context:
            return False
        question = _plain(message).strip()
        return (
            question.startswith(self.FOLLOW_UP_PREFIXES)
            or any(term in question for term in ("compara", "mes anterior", "mes seguinte", "mesmo periodo", "quis dizer"))
            or _is_confirmation(question)
            or _is_insight_request(question)
            or _contains_any(question, CONTEXT_REFERENCES)
            or bool(re.search(r"\b(?:ela|ele|isso|anterior|seguinte)\b", question))
        )

    def classify(self, message: str, state: ConversationState) -> FollowUpType:
        question = _plain(message)
        if not state.has_analytics_context:
            return FollowUpType.NEW_TOPIC
        explicit_dataset = None
        if any(term in question for term in ("passageir", "catraca")):
            explicit_dataset = "passengers_daily"
        elif any(term in question for term in ("saldo", "credito transferido")):
            explicit_dataset = "card_balances_daily"
        elif any(term in question for term in ("venda", "credito circulante")):
            explicit_dataset = "card_movements_daily"
        elif any(term in question for term in ("excecao", "excecoes", "nao iniciada", "nao terminada")):
            explicit_dataset = "trip_exceptions"
        elif any(term in question for term in ("quilometr", "veiculo")):
            explicit_dataset = "operation_daily"
        elif "viag" in question and not any(term in question for term in ("ela", "ele", "linha")):
            explicit_dataset = "operation_daily"
        compatible = {
            ("operation_daily", "line_daily"),
            ("line_daily", "operation_daily"),
            ("operation_daily", "fulfillment_daily"),
            ("fulfillment_daily", "operation_daily"),
        }
        if explicit_dataset and explicit_dataset != state.active_dataset and (state.active_dataset, explicit_dataset) not in compatible:
            return FollowUpType.NEW_TOPIC
        if any(term in question for term in ("nao,", "quis dizer", "corrigindo")):
            return FollowUpType.CORRECTION
        if _asks_projection(question):
            return FollowUpType.PROJECTION
        if _is_confirmation(question):
            return FollowUpType.FOLLOW_UP
        if any(term in question for term in ("por que", "porque")) or _is_insight_request(question) or _contains_any(question, CONTEXT_REFERENCES):
            return FollowUpType.EXPLANATION
        if _asks_comparison(question) or "valor anterior" in question:
            return FollowUpType.COMPARISON
        if any(term in question for term in ("por linha", "por dia", "por faixa", "por horario")):
            return FollowUpType.DRILL_DOWN
        if re.search(r"\b(?:so|somente|apenas)\s+(?:a\s+)?linha\b", question):
            return FollowUpType.FILTER_CHANGE
        reference_year = state.time_range.start.year if state.time_range.start else 2026
        if _named_periods(question, reference_year) or any(term in question for term in ("mes anterior", "periodo anterior", "mes seguinte", "periodo seguinte", "mesmo periodo")) or question in {"antes", "e antes?", "depois", "e depois?"}:
            return FollowUpType.TIME_CHANGE
        if any(term in question for term in ("pagante", "pagaram", "improdut", "produtiva", "programad", "realizad", "catraca")):
            return FollowUpType.METRIC_CHANGE
        if re.search(r"\b(?:top\s*\d+|\d+\s+(?:com\s+)?(?:mais|menos)|maiores|menores)\b", question):
            return FollowUpType.REFINEMENT
        return FollowUpType.FOLLOW_UP if self.looks_like_follow_up(message, state) else FollowUpType.NEW_TOPIC

    def resolve(
        self, message: str, state: ConversationState,
        history: list[dict[str, str]] | None = None,
    ) -> ResolvedRequest:
        question = _plain(message).strip()
        if is_conversational_message(message):
            return ResolvedRequest(
                original_question=message, resolved_question=message,
                is_follow_up=state.has_analytics_context,
                follow_up_type=FollowUpType.FOLLOW_UP, confidence="HIGH",
            )
        # Only the requested correction is an anchor, not the erroneous dates it quotes.
        correction = re.search(r"(?:precisa ser|quis dizer|corrigindo)[,:\s]+(.+)$", question)
        if correction:
            question = correction.group(1)
        follow_up_type = self.classify(message, state)
        is_follow_up = follow_up_type != FollowUpType.NEW_TOPIC
        base = state.previous_plan()
        reference_year = state.time_range.start.year if state.time_range.start else 2026
        periods = _named_periods(question, reference_year)

        if any(term in question for term in ("o que e", "defina", "qual o significado", "o que significa", "conceito de")):
            return ResolvedRequest(
                original_question=message, resolved_question=message,
                is_follow_up=state.has_analytics_context, follow_up_type=FollowUpType.EXPLANATION,
                confidence="HIGH", response_mode="insight" if base else "standard",
            )

        if not is_follow_up or base is None:
            plan = plan_question(message)
            comparison = None
            mode = "breakdown" if plan and plan.intent == "breakdown" else "standard"
            if plan:
                plan, comparison = _resolve_periods(question, plan, None, periods)
                if comparison and _asks_comparison(question):
                    plan = _copy_plan(plan, intent="comparison")
                    comparison = _copy_plan(comparison, intent="comparison")
                    mode = "comparison"
                    follow_up_type = FollowUpType.COMPARISON
            if plan and _asks_projection(question):
                mode = "projection"
                follow_up_type = FollowUpType.PROJECTION
            return ResolvedRequest(
                original_question=message,
                resolved_question=message,
                is_follow_up=False,
                follow_up_type=follow_up_type,
                confidence="HIGH" if plan else "MEDIUM",
                plan=plan,
                comparison_plan=comparison,
                response_mode=mode,
                modified_context={"new_topic": True},
            )

        inherited = {
            "dataset": base.dataset,
            "metrics": base.metrics,
            "period": base.period.model_dump(mode="json"),
            "filters": [item.model_dump(mode="json") for item in base.filters],
            "dimensions": base.dimensions,
        }
        plan = base.model_copy(deep=True)
        comparison = state.comparison_plan()
        modified: dict[str, object] = {}
        mode = "standard"
        confirmation_cue = _is_confirmation(question)
        projection_cue = _asks_projection(question)
        comparison_cue = _asks_comparison(question) or any(term in question for term in ("os dois", "valor anterior"))

        if confirmation_cue and not (periods or comparison_cue or projection_cue):
            # A confirmation refers to the last offered action, never an invented default query.
            last_reply = history[-1]["content"] if history and history[-1].get("role") == "assistant" else ""
            offers = re.findall(
                r"(?:posso|quer que eu|gostaria que eu|deseja que eu)\s+([^?\n.!]+)",
                _plain(last_reply),
            )
            if len(offers) == 1 and not re.search(r"\bou\b", offers[0]):
                from semob_ai.guardrails import check_scope

                offer = offers[0]
                if check_scope(offer, context_active=True, follow_up_candidate=True).allowed:
                    proposed = self.resolve(offer, state)
                    if proposed.plan is not None or proposed.response_mode == "insight":
                        proposed.original_question = message
                        proposed.modified_context["confirmed_action"] = offer
                        return proposed
            return ResolvedRequest(
                original_question=message, resolved_question=message,
                is_follow_up=True, follow_up_type=FollowUpType.FOLLOW_UP,
                confidence="MEDIUM", response_mode="insight", inherited_context=inherited,
                modified_context={"acknowledged_previous_answer": True},
            )

        plan, comparison = _resolve_periods(question, plan, comparison, periods)
        if plan.period != base.period:
            modified["period"] = plan.period.model_dump(mode="json")

        has_non_paying = bool(re.search(r"\bnao\s+(?:sao\s+|eram\s+|foram\s+)?pag", question)) or "nao pagante" in question
        has_paying = any(term in question for term in ("pagante", "pagaram", "pagou")) and not (has_non_paying and " e " not in question)
        asks_breakdown = has_non_paying and has_paying or any(term in question for term in ("divide", "separa", "decompoe"))
        if plan.dataset == "passengers_daily" and asks_breakdown:
            plan.metrics = ["paying_passengers", "non_paying_passengers", "total_passengers"]
            mode = "breakdown"
            modified["metrics"] = plan.metrics
        elif plan.dataset == "passengers_daily" and has_non_paying:
            plan.metrics = ["non_paying_passengers"]
            modified["metrics"] = plan.metrics
        elif plan.dataset == "passengers_daily" and has_paying:
            plan.metrics = ["paying_passengers"]
            modified["metrics"] = plan.metrics
        elif "improdut" in question and plan.dataset in {"operation_daily", "trips"}:
            plan.metrics = ["deadhead_km"]
            modified["metrics"] = plan.metrics
        elif "produtiva" in question and "improdut" not in question and plan.dataset in {"operation_daily", "trips"}:
            plan.metrics = ["productive_km"]
            modified["metrics"] = plan.metrics
        elif plan.dataset == "line_daily" and "viag" in question:
            plan.metrics = ["trips"]
            modified["metrics"] = plan.metrics

        if any(term in question for term in ("somente a manha", "so a manha", "apenas a manha")) and base.dataset in {"operation_daily", "fulfillment_daily"}:
            metric = "morning_scheduled" if any("scheduled" in item or "program" in item for item in base.metrics) else "morning_completed"
            plan = QueryPlan(dataset="fulfillment_daily", metrics=[metric], period=plan.period, dimensions=[d for d in plan.dimensions if d == "service_date"], limit=plan.limit)
            modified.update(dataset=plan.dataset, metrics=plan.metrics)

        if "por linha" in question:
            if base.dataset in {"operation_daily", "line_daily", "trips"}:
                metric = "trips" if any(item in {"completed_trips", "scheduled_trips", "trip_count", "trips"} for item in base.metrics) else "total_km"
                plan = QueryPlan(intent="ranking", dataset="line_daily", metrics=[metric], dimensions=["line_code"], period=plan.period, filters=[item for item in plan.filters if item.field == "line_code"], limit=plan.limit)
                modified.update(dataset=plan.dataset, dimensions=plan.dimensions, metrics=plan.metrics)
            else:
                return ResolvedRequest(
                    original_question=message,
                    resolved_question=f"Detalhar {_subject(base.dataset)} por linha",
                    is_follow_up=True,
                    follow_up_type=FollowUpType.DRILL_DOWN,
                    confidence="LOW",
                    response_mode="clarification",
                    inherited_context=inherited,
                    clarification="Os dados atuais de passageiros não possuem granularidade por linha. Posso detalhar por dia ou comparar períodos.",
                )

        line_match = re.search(r"\blinha\s+([a-z0-9.-]+)\b", question)
        if line_match and line_match.group(1) not in {"com", "por", "que"}:
            line = line_match.group(1).upper()
            filters = [item for item in plan.filters if item.field != "line_code"]
            filters.append(QueryFilter(field="line_code", value=line))
            if plan.dataset not in {"line_daily", "trips", "trip_exceptions"}:
                plan = QueryPlan(dataset="line_daily", metrics=["trips", "total_km"], period=plan.period, filters=filters, limit=plan.limit)
            else:
                plan.filters = filters
            modified["line"] = line

        rank_match = re.search(r"\b(\d{1,3})\s+(?:com\s+)?(?:mais|menos|maiores|menores)\b", question)
        if rank_match or any(term in question for term in ("maiores", "menores", "com mais", "com menos")):
            plan.limit = min(int(rank_match.group(1)), 50) if rank_match else plan.limit
            direction = "asc" if any(term in question for term in ("menos", "menores")) else "desc"
            if not plan.dimensions and plan.dataset == "line_daily":
                plan.dimensions = ["line_code"]
            if plan.dimensions:
                plan.intent = "ranking"
                plan.order_by = [OrderBy(field=plan.metrics[0], direction=direction)]
                modified.update(limit=plan.limit, ranking_direction=direction)

        if comparison_cue:
            if comparison is not None:
                plan.intent = "comparison"
                comparison = _copy_plan(comparison, metrics=plan.metrics, dimensions=plan.dimensions, filters=plan.filters, intent="comparison", limit=max(plan.limit, 50) if plan.dimensions else plan.limit)
                plan.limit = max(plan.limit, 50) if plan.dimensions else plan.limit
                mode = "comparison"
                modified["comparison_period"] = comparison.period.model_dump(mode="json")
            else:
                return ResolvedRequest(
                    original_question=message,
                    resolved_question="Comparar o resultado atual com outro período",
                    is_follow_up=True,
                    follow_up_type=FollowUpType.COMPARISON,
                    confidence="LOW",
                    plan=plan,
                    response_mode="clarification",
                    inherited_context=inherited,
                    clarification="Com qual período você quer comparar o resultado atual?",
                )

        if follow_up_type == FollowUpType.EXPLANATION:
            mode = "insight" if _is_insight_request(question) or _contains_any(question, CONTEXT_REFERENCES) else "explanation"

        if projection_cue:
            mode = "projection"
            follow_up_type = FollowUpType.PROJECTION
            modified["projection_period"] = "next_month"

        if follow_up_type == FollowUpType.FOLLOW_UP and not modified:
            return ResolvedRequest(
                original_question=message, resolved_question=message,
                is_follow_up=True, follow_up_type=follow_up_type, confidence="MEDIUM",
                response_mode="insight", inherited_context=inherited,
            )

        if mode == "standard" and plan.dataset == "passengers_daily" and {"paying_passengers", "non_paying_passengers", "total_passengers"}.issubset(plan.metrics):
            mode = "breakdown"

        plan = QueryPlan.model_validate(plan.model_dump())
        resolved = f"{_subject(plan.dataset)}; métricas {', '.join(plan.metrics)}; período {plan.period.start} a {plan.period.end}"
        return ResolvedRequest(
            original_question=message,
            resolved_question=resolved,
            is_follow_up=True,
            follow_up_type=follow_up_type,
            confidence="HIGH",
            plan=plan,
            comparison_plan=comparison,
            response_mode=mode,
            inherited_context=inherited,
            modified_context=modified,
        )
