"""Command-line interface for lookahead-free.

Subcommands:

- ``check``   check a declarative pipeline JSON for look-ahead (verifiable)
- ``scan``    heuristic scan of Python source (review-level, not a proof)
- ``version`` print version
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .checks import check_pipeline
from .heuristic import scan_python_source
from .model import load_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lf",
        description="Verifiable look-ahead-freedom for the value-independent fragment.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check a pipeline JSON for look-ahead")
    check.add_argument("--pipeline", required=True, help="pipeline JSON path")
    check.add_argument("--json", action="store_true", help="machine-readable output")

    scan = sub.add_parser("scan", help="heuristic scan of Python source (review-level)")
    scan.add_argument("--source", required=True, help="Python source file to scan")
    scan.add_argument("--json", action="store_true", help="machine-readable output")

    sub.add_parser("version", help="print version")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(__version__)
        return 0

    if args.command == "check":
        pipeline = load_pipeline(args.pipeline)
        body: dict[str, Any] = check_pipeline(pipeline)
        if args.json:
            print(json.dumps(body, ensure_ascii=False, indent=2))
        else:
            print(f"pipeline: {body['pipeline']}")
            print(body["verdict"])
            for check in body["checks"]:
                marker = "PASS" if check["passed"] else "FAIL"
                print(f" [{marker}] {check['severity']} {check['check_id']}: {check['detail']}")
        return 0 if body["passed"] else 1

    if args.command == "scan":
        source = Path(args.source).read_text(encoding="utf-8-sig")
        body = scan_python_source(source, path=args.source)
        if args.json:
            print(json.dumps(body, ensure_ascii=False, indent=2))
        else:
            print(body["verdict"])
            for finding in body["findings"]:
                print(
                    f" [{finding['kind'].upper()}] {finding['rule']} line "
                    f"{finding['line']}: {finding['message']}"
                )
            if body.get("blockers"):
                print(f"blockers: {', '.join(body['blockers'])}")
        return 0 if body["passed"] else 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
