from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from semob_ai.analytics import AnalyticsExecutor
from semob_ai.analytics.formatting import format_breakdown, format_comparison, format_projection, format_result
from semob_ai.conversation.models import ConversationResponse, ConversationState, RelevantInteraction
from semob_ai.conversation.resolver import FollowUpResolver, _subject
from semob_ai.conversation.store import SessionStore
from semob_ai.guardrails import check_scope


SCOPE_REFUSAL = (
    "Posso ajudar somente com transporte público municipal e análise dos dados autorizados da SEMOB. "
    "Reformule a pergunta dentro desse tema."
)


class ConversationEngine:
    def __init__(
        self,
        analytics_database: Path,
        session_database: Path | None,
        logger: logging.Logger | None = None,
    ):
        self.executor = AnalyticsExecutor(analytics_database)
        self.sessions = SessionStore(session_database) if session_database else None
        self.resolver = FollowUpResolver()
        self.logger = logger or logging.getLogger(__name__)

    def handle(
        self, user_id: str, session_id: str, message: str,
        history: list[dict[str, str]] | None = None,
        state: ConversationState | None = None,
    ) -> ConversationResponse:
        state_is_external = state is not None
        if state is None:
            if not self.sessions:
                raise RuntimeError("O armazenamento de estado não foi configurado.")
            state = self.sessions.load(user_id, session_id, assistant_mode="cmob")
        resolution = self.resolver.resolve(message, state, history)
        scope = check_scope(
            message,
            context_active=state.has_analytics_context,
            follow_up_candidate=resolution.is_follow_up,
        )
        if not scope.allowed:
            return ConversationResponse(kind="out_of_scope", answer=SCOPE_REFUSAL, resolution=resolution, state=state)
        if resolution.response_mode == "clarification":
            return ConversationResponse(kind="clarification", answer=resolution.clarification, resolution=resolution, state=state)
        if resolution.response_mode == "insight":
            return ConversationResponse(
                kind="conceptual",
                resolution=resolution,
                state=state,
                llm_context=self._insight_context(state),
            )
        if resolution.plan is None:
            return ConversationResponse(kind="conceptual", resolution=resolution, state=state)

        primary = self.executor.execute(resolution.plan)
        comparison = None
        if resolution.comparison_plan is not None and resolution.response_mode in {"comparison", "projection", "explanation"}:
            comparison = self.executor.execute(resolution.comparison_plan)
        if comparison is not None:
            answer = format_comparison(
                resolution.plan,
                primary,
                resolution.comparison_plan,
                comparison,
                explanation=resolution.response_mode == "explanation",
            )
        elif resolution.response_mode == "breakdown":
            answer = format_breakdown(resolution.plan, primary)
        else:
            answer = format_result(resolution.plan, primary)
            if resolution.response_mode == "explanation":
                answer += "\n\nOs dados disponíveis descrevem o resultado, mas não permitem afirmar causalidade sem evidências operacionais adicionais."
        if resolution.response_mode == "projection":
            answer += "\n\n" + format_projection(resolution.plan, primary)

        self._update_state(state, resolution, asdict(primary), asdict(comparison) if comparison else None, answer)
        if self.sessions and not state_is_external:
            self.sessions.save(state, assistant_mode="cmob")
        return ConversationResponse(
            kind="analytics",
            answer=answer,
            resolution=resolution,
            state=state,
            llm_context=self._analytics_context(state, answer),
        )

    def _update_state(
        self,
        state: ConversationState,
        resolution,
        primary_result: dict[str, object],
        comparison_result: dict[str, object] | None,
        answer: str,
    ) -> None:
        plan = resolution.plan
        if plan is None:
            return
        state.current_subject = _subject(plan.dataset)
        state.active_dataset = plan.dataset
        state.active_metrics = list(plan.metrics)
        state.time_range = plan.period.model_copy(deep=True)
        state.comparison_time_range = resolution.comparison_plan.period.model_copy(deep=True) if resolution.comparison_plan else None
        state.filters = [item.model_dump(mode="json") for item in plan.filters]
        state.group_by = list(plan.dimensions)
        state.lines = [str(item.value) for item in plan.filters if item.field == "line_code"]
        state.entities = {"lines": state.lines} if state.lines else {}
        state.previous_intent = plan.intent
        state.previous_query_plan = plan.model_dump(mode="json")
        state.previous_comparison_plan = resolution.comparison_plan.model_dump(mode="json") if resolution.comparison_plan else None
        summary = {"primary": json.loads(json.dumps(primary_result, default=str))}
        if comparison_result:
            summary["comparison"] = json.loads(json.dumps(comparison_result, default=str))
        state.previous_query_result_summary = summary
        state.previous_answer_summary = answer[:2000]
        state.last_user_question = resolution.original_question
        state.unresolved_ambiguities = []
        state.last_follow_up_type = resolution.follow_up_type
        state.working_memory = {
            "topic": state.current_subject,
            "dataset": state.active_dataset,
            "metrics": state.active_metrics,
            "period": state.time_range.model_dump(mode="json"),
            "comparison_period": state.comparison_time_range.model_dump(mode="json") if state.comparison_time_range else None,
            "filters": state.filters,
            "group_by": state.group_by,
        }
        state.relevant_interactions.append(
            RelevantInteraction(
                question=resolution.original_question,
                follow_up_type=resolution.follow_up_type,
                resolved_intent=resolution.resolved_question,
                plan=state.previous_query_plan,
            )
        )
        state.relevant_interactions = state.relevant_interactions[-12:]
        state.evidence_history.append(
            {
                "question": resolution.original_question,
                "plan": state.previous_query_plan,
                "result": summary,
                "answer": answer[:2000],
            }
        )
        state.evidence_history = state.evidence_history[-6:]

    @staticmethod
    def _evidence_context(state: ConversationState) -> str:
        return "\n\n".join(
            f"Pergunta: {item['question']}\n"
            f"Métricas: {', '.join(item['plan']['metrics'])}\n"
            f"Resultado calculado: {item['answer']}"
            for item in state.evidence_history[-4:]
        )

    @staticmethod
    def _analytics_context(state: ConversationState, canonical_answer: str) -> str:
        return (
            "MODO DE RESPOSTA: ANÁLISE CONVERSACIONAL BASEADA EM EVIDÊNCIAS.\n"
            "O backend já executou a consulta de forma determinística. Os números abaixo são a fonte factual "
            "da resposta e não podem ser alterados, recalculados por estimativa ou substituídos por números da conversa.\n\n"
            "LIMITES DE GRANULARIDADE:\n"
            "- passengers_daily é agregado por data e não permite segmentar passageiros por linha, veículo ou faixa horária.\n"
            "- Só recomende comparações dentro da cobertura explicitamente informada nas evidências.\n"
            "- Não prometa executar um recorte que o dataset e as evidências atuais não suportam.\n\n"
            "RESPOSTA CANÔNICA CALCULADA:\n"
            + canonical_answer
            + "\n\nEstes resultados atuais prevalecem sobre números e comparações incorretos no histórico."
            + "\n\nResponda à mensagem mais recente considerando também o diálogo anterior. "
              "Comece pela resposta direta, preserve todos os valores relevantes e acrescente uma interpretação útil e específica. "
              "Não volte automaticamente para agosto, pagantes ou qualquer assunto anterior se a pergunta atual mudou de foco. "
              "Não repita mecanicamente o texto canônico, não invente causas e não transforme toda resposta em uma lista genérica. "
              "Quando houver apenas um período, trate proporções e concentrações como fotografia do período, não como tendência."
        )

    @staticmethod
    def _insight_context(state: ConversationState) -> str:
        return (
            "REGRAS FACTUAIS DO SCHEMA:\n"
            "- paying_passengers/Pagantes é a derivação operacional Catraca + Antecipados.\n"
            "- non_paying_passengers/Não pagantes é uma coluna separada da fonte; não é a derivação Catraca + Antecipados.\n"
            "- Os dados não explicam a composição ou a causa de Não pagantes. Não sugira gratuidades, isenções, evasão, fraude ou outros motivos, nem como hipótese.\n\n"
            "LIMITES DE GRANULARIDADE:\n"
            "- passengers_daily é agregado por data e não permite segmentar passageiros por linha, veículo ou faixa horária.\n"
            "- Só recomende comparações dentro da cobertura explicitamente informada nas evidências.\n"
            "- Não prometa executar um recorte que o dataset e as evidências atuais não suportam.\n\n"
            "EVIDÊNCIAS ANALÍTICAS DA SESSÃO (calculadas no DuckDB):\n"
            + ConversationEngine._evidence_context(state)
            + "\nAs evidências estão em ordem cronológica: a mais recente corrige e substitui resultados anteriores do mesmo recorte."
            + "\n\nInterprete essas evidências de forma natural. Destaque padrões, proporções e limitações úteis. "
              "Não invente números, não repita mecanicamente a última resposta e não atribua causalidade sem evidência. "
              "A categoria 'não pagantes' tem causa e composição desconhecidas nos dados; não proponha explicações para ela. "
              "A cobertura geral da tabela não torna uma consulta parcial quando todo o período solicitado está contido nela. "
              "Se houver apenas um período, não afirme tendência, aumento ou queda: recomende uma comparação temporal."
        )
