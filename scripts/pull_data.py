#!/usr/bin/env python
"""CLI for week-1 data acquisition.

Usage:
    python scripts/pull_data.py --all
    python scripts/pull_data.py --source fda_shortages nadac
    python scripts/pull_data.py --all --force
"""

import argparse
import sys

from shortage.data.pull import SOURCES, pull


def main() -> int:
    p = argparse.ArgumentParser(description="Pull and cache core public data sources.")
    p.add_argument("--all", action="store_true", help="pull every core source")
    p.add_argument("--source", nargs="+", choices=sorted(SOURCES), help="specific sources")
    p.add_argument("--force", action="store_true", help="re-pull even if cache is fresh")
    p.add_argument("--list", action="store_true", help="list available sources and exit")
    args = p.parse_args()

    if args.list:
        for name, fn in SOURCES.items():
            print(f"{name:18s} {(fn.__doc__ or '').strip().splitlines()[0]}")
        return 0
    if not (args.all or args.source):
        p.error("nothing to do: pass --all or --source")

    status = pull(None if args.all else args.source, force=args.force)
    print("\n=== summary ===")
    failed = 0
    for name, s in status.items():
        print(f"{name:18s} {s}")
        failed += s.startswith("FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
