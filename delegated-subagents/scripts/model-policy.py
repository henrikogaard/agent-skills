#!/usr/bin/env python3
"""Classify the live OpenCode model inventory for delegated routing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from runtime import assess_free_models


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    models = [line.strip() for line in sys.stdin if line.strip()]
    assessed = assess_free_models(models, args.task, args.history)
    if args.json:
        print(json.dumps(assessed, indent=2, sort_keys=True))
    else:
        for item in assessed:
            print(f"{item['status']}\t{item['model']}\t{item['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
