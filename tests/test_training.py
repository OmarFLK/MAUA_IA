from __future__ import annotations

import json
from pathlib import Path

from semob_ai.training import build_dataset


def test_training_dataset_is_split_and_contains_no_credentials(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Você é um analista SEMOB.", encoding="utf-8")
    train_count, validation_count = build_dataset(tmp_path / "dataset", prompt)

    rows = [
        json.loads(line)
        for filename in ("train.jsonl", "validation.jsonl")
        for line in (tmp_path / "dataset" / filename).read_text(encoding="utf-8").splitlines()
    ]

    assert train_count + validation_count == 15
    assert {row["task"] for row in rows} == {"scope_refusal", "query_plan"}
    assert not any("Bearer " in json.dumps(row) for row in rows)

