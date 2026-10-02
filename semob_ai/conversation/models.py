from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from semob_ai.analytics.query_plan import DatePeriod, QueryPlan


class FollowUpType(str, Enum):
    NEW_TOPIC = "NEW_TOPIC"
    FOLLOW_UP = "FOLLOW_UP"
    REFINEMENT = "REFINEMENT"
    COMPARISON = "COMPARISON"
    DRILL_DOWN = "DRILL_DOWN"
    FILTER_CHANGE = "FILTER_CHANGE"
    METRIC_CHANGE = "METRIC_CHANGE"
    TIME_CHANGE = "TIME_CHANGE"
    EXPLANATION = "EXPLANATION"
    PROJECTION = "PROJECTION"
    CORRECTION = "CORRECTION"


class RelevantInteraction(BaseModel):
    question: str
    follow_up_type: FollowUpType
    resolved_intent: str
    plan: dict[str, Any] | None = None


class ConversationState(BaseModel):
    session_id: str
    user_id: str
    current_domain: str = "SEMOB"
    current_subject: str | None = None
    active_dataset: str | None = None
    active_metrics: list[str] = Field(default_factory=list)
    time_range: DatePeriod = Field(default_factory=DatePeriod)
    comparison_time_range: DatePeriod | None = None
    filters: list[dict[str, Any]] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    entities: dict[str, list[str]] = Field(default_factory=dict)
    lines: list[str] = Field(default_factory=list)
    vehicles: list[str] = Field(default_factory=list)
    time_band: str | None = None
    previous_intent: str | None = None
    previous_query_plan: dict[str, Any] | None = None
    previous_comparison_plan: dict[str, Any] | None = None
    previous_query_result_summary: dict[str, Any] | None = None
    previous_answer_summary: str | None = None
    last_user_question: str | None = None
    unresolved_ambiguities: list[str] = Field(default_factory=list)
    working_memory: dict[str, Any] = Field(default_factory=dict)
    relevant_interactions: list[RelevantInteraction] = Field(default_factory=list)
    evidence_history: list[dict[str, Any]] = Field(default_factory=list)
    last_follow_up_type: FollowUpType = FollowUpType.NEW_TOPIC

    @property
    def has_analytics_context(self) -> bool:
        return self.previous_query_plan is not None

    def previous_plan(self) -> QueryPlan | None:
        return QueryPlan.model_validate(self.previous_query_plan) if self.previous_query_plan else None

    def comparison_plan(self) -> QueryPlan | None:
        return QueryPlan.model_validate(self.previous_comparison_plan) if self.previous_comparison_plan else None


class ResolvedRequest(BaseModel):
    original_question: str
    resolved_question: str
    is_follow_up: bool
    follow_up_type: FollowUpType
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    plan: QueryPlan | None = None
    comparison_plan: QueryPlan | None = None
    response_mode: Literal["standard", "breakdown", "comparison", "projection", "explanation", "insight", "clarification"] = "standard"
    inherited_context: dict[str, Any] = Field(default_factory=dict)
    modified_context: dict[str, Any] = Field(default_factory=dict)
    clarification: str | None = None


class ConversationResponse(BaseModel):
    kind: Literal["analytics", "conceptual", "out_of_scope", "clarification"]
    answer: str | None = None
    resolution: ResolvedRequest
    state: ConversationState
    llm_context: str | None = None
