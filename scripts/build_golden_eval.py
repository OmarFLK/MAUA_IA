from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from semob_ai.analytics import AnalyticsExecutor
from semob_ai.analytics.planner import plan_question


def serialize(value: object) -> object:
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    raise TypeError


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local golden set from validated SEMOB queries.")
    parser.add_argument("--cases", type=Path, default=Path("evaluation/cases.json"))
    parser.add_argument("--database", type=Path, default=Path("data/database/semob.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("data/metadata/golden_eval.json"))
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    executor = AnalyticsExecutor(args.database)
    golden = []
    for case in cases:
        plan = plan_question(case["question"])
        if plan is None:
            raise SystemExit(f"No plan for case {case['id']}")
        golden.append({**case, "plan": plan.model_dump(mode="json"), "expected": asdict(executor.execute(plan))})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(golden, ensure_ascii=False, indent=2, default=serialize) + "\n", encoding="utf-8")
    print(f"Built {len(golden)} golden cases in {args.output}.")


if __name__ == "__main__":
    main()

