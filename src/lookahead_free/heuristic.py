"""Heuristic companion scanner for Python research code (``lf scan``).

``lf check`` proves look-ahead freedom on the *value-independent fragment*
(declarative pipelines).  Real research code also contains value-dependent
operations the verifiable layer cannot decide — that is where this heuristic
scanner lives.  It is explicitly **not** a proof: every finding is a
suspicious idiom for a human to review, and the module says so in the
report (same honesty boundary as the rest of the library).

Rules (added 2026-09, distilled from a production A-share research
pipeline's static time-point scanner):

- ``H001`` (hard): future subscript — ``series[index + k]`` with ``k > 0``
  reads a bar that does not exist yet at decision time.
- ``H002`` (hard): future window slice — ``series[i + k : ...]`` with a
  positive offset lower bound.
- ``H003`` (review): a data-fetching call without an explicit time-binding
  parameter (``as_of`` / ``available_at`` / ``cutoff`` / ``end_date`` /
  ``date`` / ``day``).  Convention-based: calibrate the name sets below to
  your codebase.

Severity semantics mirror the production scanner: hard findings fail the
run (exit 1); review findings are listed but do not fail it.  The rule set
is deliberately small and auditable; extend it in code, not by magic.
"""

from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from typing import Any

FETCH_CALL_RE = re.compile(
    r"^(fetch|request|query|download|kline|quote|backfill)[a-z_0-9]*$", re.IGNORECASE
)
TIME_PARAM_RE = re.compile(r"^(as_of|asof|available_at|cutoff|end_date|start_date|date|day|when|at)$", re.IGNORECASE)


def _const_int(node: ast.AST) -> int | None:
    """Return a positive constant int if ``node`` is ``<name> + K`` or K itself."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        right = node.right
        if isinstance(right, ast.Constant) and isinstance(right.value, int):
            return right.value
        left = node.left
        if isinstance(left, ast.Constant) and isinstance(left.value, int):
            return left.value
    return None


def _subslice_offset(slice_: ast.Slice) -> int | None:
    if slice_.lower is None:
        return None
    value = _const_int(slice_.lower)
    if value is None:
        return None
    return value if value > 0 else None


def _findings_for_function(
    tree: ast.AST, function_name: str
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)

        if isinstance(node, ast.Subscript):
            offset = None
            if isinstance(node.slice, ast.Slice):
                offset = _subslice_offset(node.slice)
                if offset is not None:
                    findings.append(
                        {
                            "rule": "H002",
                            "kind": "hard",
                            "line": line,
                            "message": (
                                f"{function_name}: window slice starts {offset} step(s) "
                                "in the future — value-dependent look-ahead window"
                            ),
                        }
                    )
                    continue
            elif isinstance(node.slice, ast.BinOp) and isinstance(node.slice.op, ast.Add):
                right = node.slice.right
                if isinstance(right, ast.Constant) and isinstance(right.value, int) and right.value > 0:
                    findings.append(
                        {
                            "rule": "H001",
                            "kind": "hard",
                            "line": line,
                            "message": (
                                f"{function_name}: subscript reads index + "
                                f"{right.value} — future bar access (heuristic)"
                            ),
                        }
                    )

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if not FETCH_CALL_RE.match(node.func.id):
                continue
            param_names = [arg.arg for arg in node.keywords if arg.arg]
            if not any(TIME_PARAM_RE.match(str(name)) for name in param_names):
                findings.append(
                    {
                        "rule": "H003",
                        "kind": "review",
                        "line": line,
                        "message": (
                            f"{function_name}: call to {node.func.id}() has no explicit "
                            "as_of/available_at/cutoff/date parameter (convention heuristic)"
                        ),
                    }
                )
    return findings


def scan_python_source(source: str, *, path: str = "<string>") -> dict[str, Any]:
    """Scan Python source for heuristic look-ahead idioms.

    Returns a report with ``findings`` (rule/kind/line/message), ``verdict``
    PASS/FAIL and ``passed`` (False only when a hard rule fired).  Review
    findings never fail the run — they are the heuristic boundary, stated
    out loud.
    """
    findings: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return {
            "schema_version": "lookahead_free_heuristic_scan.v1",
            "path": path,
            "verdict": "FAIL",
            "passed": False,
            "blockers": [f"syntax_error: {exc}"],
            "findings": [],
            "note": "could not parse source — fail-closed",
        }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_findings_for_function(node, node.name))
    hard = [f for f in findings if f["kind"] == "hard"]
    return {
        "schema_version": "lookahead_free_heuristic_scan.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "path": path,
        "verdict": "PASS" if not hard else "FAIL",
        "passed": not hard,
        "findings": findings,
        "note": (
            "heuristic scan: hard findings (H001/H002) fail the run; review "
            "findings (H003) are listed but not authoritative — this is NOT "
            "the verifiable layer.  For proofs use `lf check`."
        ),
    }
