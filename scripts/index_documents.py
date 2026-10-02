from __future__ import annotations

import argparse
from pathlib import Path

from semob_ai.rag import LocalRagIndex


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the entirely local SEMOB textual index.")
    parser.add_argument("--documents", type=Path, default=Path("knowledge"))
    parser.add_argument("--database", type=Path, default=Path("data/database/rag.sqlite"))
    args = parser.parse_args()
    count = LocalRagIndex(args.database).rebuild(args.documents)
    print(f"Indexed {count} authorized text chunks in {args.database}.")


if __name__ == "__main__":
    main()
