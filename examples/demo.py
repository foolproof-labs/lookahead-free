"""End-to-end demo: check a pipeline, then break it and watch the gate fire.

Run with:  python examples/demo.py
Uses examples/factor-pipeline.json (clean) and an inline leaky variant
(decision before the data is available).  No network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lookahead_free.cli import main as cli_main  # noqa: E402

GOOD = Path(__file__).resolve().parent / "factor-pipeline.json"
TMP = Path(__file__).resolve().parent


def _run(label: str, pipeline_path: Path) -> None:
    print(f"\n== {label} ==")
    code = cli_main(["check", "--pipeline", str(pipeline_path)])
    print(f"=> exit code: {code} (0 = look-ahead-free, 1 = look-ahead detected)")


def main() -> int:
    _run("1. clean factor pipeline (value-independent fragment)", GOOD)

    leaky = json.loads(GOOD.read_text(encoding="utf-8"))
    for op in leaky["operations"]:
        if op["op_id"] == "decide":
            op["decision_time"] = "2026-08-01T14:00:00"  # before features are available
    leaky_path = TMP / "factor-pipeline.leaky.json"
    leaky_path.write_text(json.dumps(leaky, ensure_ascii=False, indent=2), encoding="utf-8")
    _run("2. same pipeline, decision pulled to 14:00 (features ready at 15:00)", leaky_path)

    leaky_path.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
