from __future__ import annotations

import json
from pathlib import Path

from semob_ai.training import build_dataset


def test_training_dataset_is_split_and_contains_no_credentials(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Você é um analista SEMOB.", encoding="utf-8")
    database = tmp_path / 'semob.duckdb'
    from scripts.build_cmob_data import build_snapshot
    build_snapshot(Path('data/public'), database)
    train_count, validation_count = build_dataset(tmp_path / "dataset", prompt, database=database)

    rows = [
        json.loads(line)
        for filename in ("train.jsonl", "validation.jsonl")
        for line in (tmp_path / "dataset" / filename).read_text(encoding="utf-8").splitlines()
    ]

    assert train_count > 100 and validation_count > 50
    assert {row["task"] for row in rows} == {"grounded_answer", "contextual_follow_up", "security_refusal"}
    assert not any("Bearer " in json.dumps(row) for row in rows)
    training = [json.loads(line) for line in (tmp_path / 'dataset/train.jsonl').read_text(encoding='utf-8').splitlines()]
    validation = [json.loads(line) for line in (tmp_path / 'dataset/validation.jsonl').read_text(encoding='utf-8').splitlines()]
    assert not any(row['period'] == '2026-09' for row in training)
    assert all(row['period'] == '2026-09' for row in validation)
    assert not json.loads((tmp_path / 'dataset/manifest.json').read_text())['trained']

