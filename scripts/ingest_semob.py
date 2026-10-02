from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from semob_ai.ingestion import run_ingestion


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize SEMOB HTML reports into Parquet and DuckDB.")
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data"))
    args = parser.parse_args()
    result = run_ingestion(args.raw, args.output)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

