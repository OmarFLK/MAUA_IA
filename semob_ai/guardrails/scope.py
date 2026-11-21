from __future__ import annotations

import unicodedata
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    reason: str


TRANSPORT_TERMS = {
    "semob", "transporte", "onibus", "linha", "viag", "veiculo", "passageiro", "pagante", "catraca",
    "quilometr", "km", "itinerario", "mobilidade", "saldo", "credito", "tarifa", "motorista",
    "horario", "operacao", "frota", "partida", "terminal", "venda", "faturamento", "utilizacao", "cumprimento", "excecao", "excecoes", "bilhetagem",
}
DATA_WORK_TERMS = {
    "dados", "indicador", "metrica", "estatistic", "relatorio", "dashboard", "serie historica",
}
DATA_REQUEST_TERMS = {"analise", "resumo", "panorama", "visao geral"}
PERIOD_TERMS = {
    "periodo", "mes", "ano", "semana", "dia", "janeiro", "fevereiro", "marco", "abril", "maio",
    "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
}
OUT_OF_SCOPE_TERMS = {
    "receita culinaria", "receita de bolo", "futebol", "filme", "medicina", "advogado", "bitcoin",
    "youtube", "politica", "eleicao", "presidente", "baixar videos", "faca um site", "site em react",
}
INJECTION_TERMS = {"ignore as instrucoes", "ignore as regras", "ignore as regras anteriores", "prompt do sistema", "system prompt", "jailbreak", "finja que nao", "esquece tudo"}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def is_conversational_message(question: str) -> bool:
    plain = _plain(question).strip()
    if re.fullmatch(
        r"(?:oi|ola|opa|eai|e ai|bom dia|boa tarde|boa noite|obrigad[oa]|valeu|beleza|"
        r"(?:vamos|bora)(?: para)? (?:mais um|outro|um novo) teste|"
        r"(?:vamos|bora) testar(?: de novo)?|podemos (?:testar|continuar))\W*",
        plain,
    ):
        return True
    # A greeting must not swallow a real request appended to it, especially
    # when the session already has an analytical plan to continue.
    if re.search(
        r"\b(?:quant[oa]s?|total|soma|media|ranking|compare|compara|comparar|"
        r"resuma|resumo|detalhe|projecao|percentual)\b",
        plain,
    ):
        return False
    return bool(re.search(
        r"\b(?:(?:voce|vc|tu)\s+(?:esta|ta|esta mesmo|ta mesmo)\s+"
        r"(?:funcionando|online|ai|disponivel)|"
        r"(?:esta|ta|tudo)\s+funcionando|"
        r"(?:em que|com o que|como)\s+(?:(?:voce|vc)\s+)?"
        r"(?:pode|consegue|poderia)\s+(?:me\s+)?ajudar|"
        r"o que\s+(?:(?:voce|vc)\s+)?(?:pode|consegue|sabe)\s+"
        r"(?:fazer|analisar|responder)|"
        r"quais\s+(?:sao\s+)?(?:suas|as suas)\s+(?:funcoes|capacidades)|"
        r"quem\s+(?:e\s+voce|e\s+vc)|"
        r"como\s+(?:voce|vc|isso|o assistente)\s+funciona|"
        r"(?:primeiro|meu primeiro|mais um)\s+teste\s+(?:com voce|contigo))\b",
        plain,
    ))


def is_work_support_message(question: str) -> bool:
    plain = _plain(question)
    return bool(re.search(
        r"\b(?:escrev\w*|redig\w*|redij\w*|revis\w*|reescrev\w*|prepar\w*|"
        r"mont\w*|organiz\w*|planej\w*|cri\w*)\b.*"
        r"\b(?:texto|e-?mail|comunicado|apresentacao|reuniao|roteiro|plano|"
        r"planilha|formula|codigo|script|documentacao)\b",
        plain,
    ))


def check_scope(
    question: str,
    *,
    context_active: bool = False,
    follow_up_candidate: bool = False,
) -> ScopeDecision:
    plain = _plain(question)
    if any(term in plain for term in INJECTION_TERMS):
        return ScopeDecision(False, "tentativa de alterar as instruções do assistente")
    # Domain context takes precedence over ambiguous topic words: public
    # transport policy and Python analysis of passengers are legitimate work.
    if any(term in plain for term in TRANSPORT_TERMS):
        return ScopeDecision(True, "tema de transporte público")
    if any(term in plain for term in DATA_WORK_TERMS):
        return ScopeDecision(True, "trabalho de analise de dados")
    if any(term in plain for term in DATA_REQUEST_TERMS) and any(term in plain for term in PERIOD_TERMS):
        return ScopeDecision(True, "pedido analitico com periodo")
    if any(term in plain for term in OUT_OF_SCOPE_TERMS):
        return ScopeDecision(False, "tema explicitamente fora do domínio SEMOB")
    if is_conversational_message(question):
        return ScopeDecision(True, "interação conversacional")
    if context_active and follow_up_candidate:
        return ScopeDecision(True, "continuação contextual de uma análise SEMOB")
    # Let the model understand open-ended work requests, introductions and
    # unclear questions. Missing keywords alone are not grounds for refusal.
    return ScopeDecision(True, "conversa aberta e apoio ao trabalho no dashboard")
