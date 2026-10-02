from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from semob_ai.analytics import AnalyticsExecutor, QueryPlan


def normalized(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Regression-test deterministic analytics against the local golden set.")
    parser.add_argument("--golden", type=Path, default=Path("data/metadata/golden_eval.json"))
    parser.add_argument("--database", type=Path, default=Path("data/database/semob.duckdb"))
    args = parser.parse_args()
    cases = json.loads(args.golden.read_text(encoding="utf-8"))
    executor = AnalyticsExecutor(args.database)
    failures = []
    for case in cases:
        actual = asdict(executor.execute(QueryPlan.model_validate(case["plan"])))
        if normalized(actual) != normalized(case["expected"]):
            failures.append(case["id"])
    print(f"Analytics evaluation: {len(cases) - len(failures)}/{len(cases)} passed.")
    if failures:
        raise SystemExit("Failed cases: " + ", ".join(failures))


if __name__ == "__main__":
    main()

