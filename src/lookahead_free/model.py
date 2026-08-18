"""Pipeline model: declarative DAG of temporally annotated operations.

Each operation declares what it consumes, what it produces, and its
temporal bound:

- ``release``          — read ops: when the data becomes knowable
- ``window_end``       — window/resample ops: the end of the lookback window
- ``read_cutoff``      — pit_read / vintage_read ops: the PIT cutoff
- ``decision_time``    — decision ops: when the decision is made

Output availability is computed by the checker: an explicit bound, or the
maximum availability of the inputs (monotonicity).  ``value_dependent``
marks operations whose semantics depend on data values — for these the
temporal checks are exact on *structure* but the operation itself sits at
the heuristic boundary (Fonseca's undecidability result).

Times are ISO-8601 strings; ISO order equals chronological order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OP_KINDS = frozenset(
    {
        "read",
        "window",
        "resample",
        "join",
        "pit_read",
        "vintage_read",
        "transform",
        "decision",
        "write",
    }
)
EXPLICIT_BOUND_FIELDS = {
    "read": "release",
    "window": "window_end",
    "resample": "window_end",
    "pit_read": "read_cutoff",
    "vintage_read": "read_cutoff",
}
BOUND_REQUIRED = {"window", "resample", "pit_read", "vintage_read"}


@dataclass
class Operation:
    """One node in the pipeline DAG."""

    op_id: str
    kind: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    release: str | None = None
    window_end: str | None = None
    read_cutoff: str | None = None
    decision_time: str | None = None
    value_dependent: bool = False
    note: str = ""

    def explicit_bound(self) -> str | None:
        """The op's declared availability bound, if any."""
        for key in ("release", "window_end", "read_cutoff", "decision_time"):
            value = getattr(self, key)
            if value:
                return value
        return None


@dataclass
class Pipeline:
    """A pipeline: operations plus edge structure (implicit via inputs)."""

    name: str
    operations: list[Operation] = field(default_factory=list)

    def by_id(self) -> dict[str, Operation]:
        return {op.op_id: op for op in self.operations}


def _validate_kind(kind: str) -> None:
    if kind not in OP_KINDS:
        raise ValueError(f"unknown op kind: {kind!r}")


def _validate_bound(op: Operation) -> None:
    if op.kind in BOUND_REQUIRED:
        bound = getattr(op, EXPLICIT_BOUND_FIELDS[op.kind])
        if not bound:
            raise ValueError(f"op {op.op_id!r} ({op.kind}) requires "
                             f"{EXPLICIT_BOUND_FIELDS[op.kind]}")
    if op.kind == "decision" and not op.decision_time:
        raise ValueError(f"decision op {op.op_id!r} requires decision_time")
    if op.kind == "read" and not op.release:
        raise ValueError(f"read op {op.op_id!r} requires release")


def operation_from_dict(value: dict[str, Any]) -> Operation:
    kind = str(value.get("kind") or "")
    _validate_kind(kind)
    op = Operation(
        op_id=str(value.get("op_id") or ""),
        kind=kind,
        inputs=[str(x) for x in (value.get("inputs") or [])],
        outputs=[str(x) for x in (value.get("outputs") or [])],
        release=str(value["release"]) if value.get("release") else None,
        window_end=str(value["window_end"]) if value.get("window_end") else None,
        read_cutoff=str(value["read_cutoff"]) if value.get("read_cutoff") else None,
        decision_time=str(value["decision_time"]) if value.get("decision_time") else None,
        value_dependent=bool(value.get("value_dependent", False)),
        note=str(value.get("note") or ""),
    )
    if not op.op_id:
        raise ValueError("op_id is required")
    _validate_bound(op)
    return op


def load_pipeline(path: Path | str | dict[str, Any]) -> Pipeline:
    """Load a pipeline from a JSON file or dict."""
    if isinstance(path, dict):
        payload = path
    else:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("operations"), list):
        raise ValueError("pipeline must be an object with an 'operations' list")
    return Pipeline(
        name=str(payload.get("name") or "unnamed"),
        operations=[operation_from_dict(op) for op in payload["operations"]],
    )
