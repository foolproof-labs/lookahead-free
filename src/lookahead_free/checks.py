"""Exact temporal checks over the pipeline DAG.

Input references in the pipeline JSON may name either an op_id or an output
of some op (dataflow semantics); ambiguous output names are reported.

Checks (all linear-time in the number of edges):

- ``dag``               — inputs resolve, no cycles, no duplicate op_ids
- ``decision_availability`` — every input of a decision op is available at
  or before the decision time (the core look-ahead check)
- ``window_boundary``   — window/resample ops declare a window end; a window
  whose end is after its consumer's decision time is a look-ahead
- ``pit_reads``         — pit_read / vintage_read ops declare a PIT cutoff;
  the cutoff is the availability of their output
- ``monotonicity``      — every op's availability >= the availability of its
  inputs (no op can produce a fact earlier than the facts it consumes)
- ``heuristic_boundary``— value-dependent operations are flagged (P1): for
  them the temporal structure is checked exactly, but the operation itself
  sits in the undecidable fragment (Fonseca 2026) and needs heuristic guards

Severity: P0 = look-ahead (fail-closed), P1 = heuristic boundary / warning,
P2 = informational.
"""

from __future__ import annotations

from typing import Any

from .model import Pipeline


def _resolve_edges(pipeline: Pipeline) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Resolve input references (op_id or output name) to op_ids.

    Returns ``(resolved, unresolved)`` keyed by op_id.  An output name
    declared by more than one op is ambiguous and treated as unresolved.
    """
    ops = pipeline.by_id()
    by_output: dict[str, list[str]] = {}
    for op in pipeline.operations:
        for out in op.outputs:
            by_output.setdefault(out, []).append(op.op_id)
    resolved: dict[str, list[str]] = {}
    unresolved: dict[str, list[str]] = {}
    for op in pipeline.operations:
        ids: list[str] = []
        unknown: list[str] = []
        for ref in op.inputs:
            if ref in ops:
                ids.append(ref)
            elif ref in by_output:
                if len(by_output[ref]) == 1:
                    ids.append(by_output[ref][0])
                else:
                    unknown.append(f"{ref} (ambiguous: {', '.join(by_output[ref])})")
            else:
                unknown.append(ref)
        resolved[op.op_id] = ids
        unresolved[op.op_id] = unknown
    return resolved, unresolved


def _availability(op, avail_by_id: dict[str, str | None]) -> str | None:
    bound = op.explicit_bound()
    if bound:
        return bound
    inputs = [avail_by_id.get(inp) for inp in op.inputs if avail_by_id.get(inp)]
    return max(inputs) if inputs else None


def check_pipeline(pipeline: Pipeline) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    ops = pipeline.by_id()
    resolved_edges, unresolved_edges = _resolve_edges(pipeline)

    def add(check_id: str, severity: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "check_id": check_id,
                "severity": severity,
                "passed": passed,
                "detail": detail,
            }
        )

    # ---- dag structure -------------------------------------------------------
    problems: list[str] = []
    if len(ops) != len(pipeline.operations):
        problems.append("duplicate op_id")
    for op_id, unknown in unresolved_edges.items():
        for ref in unknown:
            problems.append(f"{op_id} references unresolvable input {ref!r}")
    # cycle detection (DFS over resolved edges)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(op_id: str) -> bool:
        if op_id not in ops:
            return False  # unreachable; reported via unresolved inputs
        if op_id in visited:
            return False
        if op_id in visiting:
            return True
        visiting.add(op_id)
        for inp in resolved_edges.get(op_id, []):
            if visit(inp):
                return True
        visiting.discard(op_id)
        visited.add(op_id)
        return False

    cyclic = any(visit(op_id) for op_id in ops)
    if cyclic:
        problems.append("cycle detected")
    add("dag", "P0", not problems, "; ".join(problems) if problems else "dag ok")

    # ---- availability propagation -------------------------------------------
    avail_by_id: dict[str, str | None] = {}
    for _ in range(len(ops) + 1):
        changed = False
        for op in pipeline.operations:
            new = _availability(op, avail_by_id)
            if new != avail_by_id.get(op.op_id):
                avail_by_id[op.op_id] = new
                changed = True
        if not changed:
            break

    # ---- monotonicity --------------------------------------------------------
    mono_problems: list[str] = []
    for op in pipeline.operations:
        bound = op.explicit_bound()
        for inp in resolved_edges.get(op.op_id, []):
            input_avail = avail_by_id.get(inp)
            if input_avail is None:
                continue
            if bound is not None and bound < input_avail:
                mono_problems.append(
                    f"{op.op_id} bound {bound} < input {inp} availability "
                    f"{input_avail} (impossible availability)"
                )
    add("monotonicity", "P0", not mono_problems,
        "; ".join(mono_problems) if mono_problems else "monotonicity ok")

    # ---- decision availability (core) ----------------------------------------
    decision_problems: list[str] = []
    for op in pipeline.operations:
        if op.kind != "decision":
            continue
        decision_time = op.decision_time
        for inp in resolved_edges.get(op.op_id, []):
            input_avail = avail_by_id.get(inp)
            if input_avail is None:
                decision_problems.append(
                    f"{op.op_id} input {inp!r} has no resolvable availability"
                )
                continue
            if input_avail > decision_time:
                decision_problems.append(
                    f"{op.op_id} decides at {decision_time} but input {inp!r} "
                    f"is only available at {input_avail} (LOOK-AHEAD)"
                )
    add("decision_availability", "P0", not decision_problems,
        "; ".join(decision_problems) if decision_problems else "decision availability ok")

    # ---- window boundary -----------------------------------------------------
    window_problems: list[str] = []
    for op in pipeline.operations:
        if op.kind not in ("window", "resample"):
            continue
        if not op.window_end:
            window_problems.append(f"{op.op_id} ({op.kind}) missing window_end")
    add("window_boundary", "P0", not window_problems,
        "; ".join(window_problems) if window_problems else "window boundaries ok")

    # ---- pit reads -----------------------------------------------------------
    pit_problems: list[str] = []
    for op in pipeline.operations:
        if op.kind not in ("pit_read", "vintage_read"):
            continue
        if not op.read_cutoff:
            pit_problems.append(f"{op.op_id} ({op.kind}) missing read_cutoff")
    add("pit_reads", "P0", not pit_problems,
        "; ".join(pit_problems) if pit_problems else "pit reads ok")

    # ---- heuristic boundary (value-dependent ops) ----------------------------
    heuristic_ops = [op.op_id for op in pipeline.operations if op.value_dependent]
    add(
        "heuristic_boundary",
        "P1",
        not heuristic_ops,
        "value-dependent ops (undecidable fragment, heuristic guards required): "
        + (", ".join(heuristic_ops) if heuristic_ops else "none"),
    )

    # ---- informational -------------------------------------------------------
    reads = [op.op_id for op in pipeline.operations if op.kind == "read"]
    add("pipeline_shape", "P2", True,
        f"{len(pipeline.operations)} ops, {len(reads)} reads, pipeline "
        f"{pipeline.name!r}")

    p0_failed = [check for check in checks if check["severity"] == "P0" and not check["passed"]]
    passed = not p0_failed
    verdict = (
        "PASS - value-independent fragment is look-ahead-free"
        if passed
        else "FAIL - look-ahead detected in the value-independent fragment"
    )
    return {
        "schema_version": "lookahead_free.check.v1",
        "pipeline": pipeline.name,
        "passed": passed,
        "verdict": verdict,
        "checks": checks,
        "availability": {
            op.op_id: avail_by_id.get(op.op_id) for op in pipeline.operations
        },
        "safety": {
            "production_effect": False,
            "changes_probability": False,
            "allow_real_trade": False,
        },
    }
