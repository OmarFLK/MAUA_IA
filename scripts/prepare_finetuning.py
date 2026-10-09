from __future__ import annotations

import argparse
from pathlib import Path

from semob_ai.training import build_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a leakage-checked SEMOB supervised dataset.")
    parser.add_argument("--output", type=Path, default=Path("data/finetuning"))
    parser.add_argument("--prompt", type=Path, default=Path("prompts/cmob_system.md"))
    parser.add_argument("--database", type=Path, default=Path("data/database/semob.duckdb"))
    args = parser.parse_args()
    train, validation = build_dataset(args.output, args.prompt, database=args.database)
    print(f"Prepared {train} training and {validation} validation examples in {args.output}.")


if __name__ == "__main__":
    main()

