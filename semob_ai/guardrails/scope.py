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
    "horario", "operacao", "frota", "partida", "terminal",
}
OUT_OF_SCOPE_TERMS = {
    "codigo python", "programar", "receita", "futebol", "filme", "medicina", "advogado", "bitcoin",
    "youtube", "politica", "eleicao", "presidente", "baixar videos", "faca um site", "site em react",
}
INJECTION_TERMS = {"ignore as instrucoes", "ignore as regras", "ignore as regras anteriores", "prompt do sistema", "system prompt", "jailbreak", "finja que nao", "esquece tudo"}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def is_conversational_message(question: str) -> bool:
    plain = _plain(question).strip()
    return bool(re.fullmatch(
        r"(?:oi|ola|bom dia|boa tarde|boa noite|obrigad[oa]|valeu|beleza|"
        r"(?:vamos|bora)(?: para)? (?:mais um|outro|um novo) teste|"
        r"(?:vamos|bora) testar(?: de novo)?|podemos (?:testar|continuar))\W*",
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
    if any(term in plain for term in OUT_OF_SCOPE_TERMS):
        return ScopeDecision(False, "tema explicitamente fora do domínio SEMOB")
    if is_conversational_message(question):
        return ScopeDecision(True, "interação conversacional")
    if len(plain.split()) <= 4 and any(term in plain for term in ("oi", "ola", "bom dia", "boa tarde", "ajuda")):
        return ScopeDecision(True, "saudação")
    if any(term in plain for term in TRANSPORT_TERMS):
        return ScopeDecision(True, "tema de transporte público")
    if context_active and follow_up_candidate:
        return ScopeDecision(True, "continuação contextual de uma análise SEMOB")
    return ScopeDecision(False, "não foi identificado vínculo com transporte público ou SEMOB")
