from pathlib import Path
import pytest

from semob_ai.conversation.service import ConversationEngine
from semob_ai.rag import LocalRagIndex
from scripts.build_cmob_data import build_snapshot


@pytest.fixture
def real_engine(tmp_path):
    database = tmp_path / 'cmob.duckdb'
    build_snapshot(Path('data/public'), database)
    return ConversationEngine(database, tmp_path / 'session.sqlite')


def test_exact_screenshot_dialogue(real_engine):
    messages = [
        'opa, eai, modelo par analises do semob, certo?',
        'me de um resumo dos dados de agosto',
        'preciso de um resumo dos dados de agosto do semob',
        'preciso de mais detalhes em todos os sentidos por favor',
    ]
    answers = [real_engine.handle('test', 'screenshot', message) for message in messages]
    assert answers[0].kind == 'conceptual'
    for answer in answers[1:3]:
        assert answer.kind == 'analytics'
        assert '1.050.248' in answer.answer
        assert '288.378' in answer.answer
        assert '761.870' in answer.answer
        assert answer.state.time_range.start.year == 2026
    assert answers[3].kind == 'conceptual'
    assert '1.050.248' in answers[3].llm_context
    assert 'EVID' in answers[3].llm_context


def test_partial_month_and_unavailable_period(real_engine):
    partial = real_engine.handle('test', 'july', 'Qual foi o total de passageiros em julho?')
    assert '489.653' in partial.answer
    assert 'parcial' in partial.answer
    assert '17' in partial.answer
    absent = real_engine.handle('test', 'old', 'Qual foi o total de passageiros em agosto de 2023?')
    assert 'Nao encontrei' in absent.answer or 'Não encontrei' in absent.answer
    assert not absent.state.previous_query_result_summary['primary']['rows']


def test_granularity_and_real_comparison(real_engine):
    real_engine.handle('test', 'details', 'me de um resumo dos dados de agosto')
    unsupported = real_engine.handle('test', 'details', 'E por linha?')
    assert unsupported.kind == 'clarification'
    assert 'granularidade' in unsupported.answer
    daily = real_engine.handle('test', 'details', 'E por dia?')
    assert daily.kind == 'analytics'
    assert daily.resolution.plan.dimensions == ['service_date']
    assert len(daily.state.previous_query_result_summary['primary']['rows']) > 1
    comparison = real_engine.handle('test', 'compare', 'Compare passageiros de julho e agosto.')
    assert '1.050.248' in comparison.answer and '489.653' in comparison.answer
    assert 'parcial' in comparison.answer


def test_rag_contains_new_dataset_coverage(tmp_path):
    index = LocalRagIndex(tmp_path / 'rag.sqlite')
    assert index.rebuild(Path('knowledge')) > 3
    hits = index.search('cobertura passageiros setembro 2026', limit=10)
    assert any('generated/' in hit.source and '2026-09' in hit.text for hit in hits)
