"""Tests for the pipeline model and exact temporal checks."""

from __future__ import annotations

import pytest

from lookahead_free.checks import check_pipeline
from lookahead_free.model import load_pipeline

GOOD_PIPELINE = {
    "name": "momentum-daily",
    "operations": [
        {"op_id": "quotes", "kind": "read", "release": "2026-07-31T16:00:00",
         "outputs": ["quotes"]},
        {"op_id": "fundamentals", "kind": "pit_read", "read_cutoff": "2026-07-31T00:00:00",
         "outputs": ["fundamentals"]},
        {"op_id": "momentum", "kind": "window", "window_end": "2026-08-01T15:00:00",
         "inputs": ["quotes"], "outputs": ["momentum"]},
        {"op_id": "features", "kind": "join", "inputs": ["momentum", "fundamentals"],
         "outputs": ["features"]},
        {"op_id": "decide", "kind": "decision", "decision_time": "2026-08-01T15:00:00",
         "inputs": ["features"], "outputs": ["signal"]},
    ],
}


def test_good_pipeline_passes() -> None:
    body = check_pipeline(load_pipeline(GOOD_PIPELINE))
    assert body["passed"] is True
    by_id = {check["check_id"]: check for check in body["checks"]}
    assert by_id["decision_availability"]["passed"] is True
    assert by_id["monotonicity"]["passed"] is True
    # features availability = max(momentum 15:00, fundamentals 07-31) = 15:00
    assert body["availability"]["features"] == "2026-08-01T15:00:00"


def test_decision_before_input_availability_is_lookahead() -> None:
    pipeline = {
        "name": "leaky",
        "operations": [
            {"op_id": "quotes", "kind": "read", "release": "2026-08-01T16:00:00",
             "outputs": ["quotes"]},
            {"op_id": "decide", "kind": "decision", "decision_time": "2026-08-01T15:00:00",
             "inputs": ["quotes"], "outputs": ["signal"]},
        ],
    }
    body = check_pipeline(load_pipeline(pipeline))
    assert body["passed"] is False
    by_id = {check["check_id"]: check for check in body["checks"]}
    assert by_id["decision_availability"]["passed"] is False
    assert "LOOK-AHEAD" in by_id["decision_availability"]["detail"]


def test_monotonicity_violation_impossible_availability() -> None:
    pipeline = {
        "name": "impossible",
        "operations": [
            {"op_id": "quotes", "kind": "read", "release": "2026-08-01T16:00:00",
             "outputs": ["quotes"]},
            {"op_id": "fast", "kind": "transform", "release": "2026-08-01T10:00:00",
             "inputs": ["quotes"], "outputs": ["fast"]},
        ],
    }
    body = check_pipeline(load_pipeline(pipeline))
    by_id = {check["check_id"]: check for check in body["checks"]}
    assert by_id["monotonicity"]["passed"] is False
    assert body["passed"] is False


def test_unknown_input_and_cycle() -> None:
    pipeline = {
        "name": "broken",
        "operations": [
            {"op_id": "a", "kind": "read", "release": "2026-08-01T10:00:00", "outputs": ["a"]},
            {"op_id": "b", "kind": "transform", "inputs": ["missing"], "outputs": ["b"]},
            {"op_id": "c", "kind": "transform", "inputs": ["d"], "outputs": ["c"]},
            {"op_id": "d", "kind": "transform", "inputs": ["c"], "outputs": ["d"]},
        ],
    }
    body = check_pipeline(load_pipeline(pipeline))
    by_id = {check["check_id"]: check for check in body["checks"]}
    assert by_id["dag"]["passed"] is False
    assert "unresolvable input" in by_id["dag"]["detail"]
    assert "cycle" in by_id["dag"]["detail"]


def test_window_and_pit_read_require_bounds() -> None:
    with pytest.raises(ValueError, match="window_end"):
        load_pipeline(
            {
                "name": "bad",
                "operations": [
                    {"op_id": "w", "kind": "window", "inputs": ["q"], "outputs": ["w"]},
                ],
            }
        )
    with pytest.raises(ValueError, match="read_cutoff"):
        load_pipeline(
            {
                "name": "bad2",
                "operations": [
                    {"op_id": "p", "kind": "pit_read", "outputs": ["p"]},
                ],
            }
        )


def test_value_dependent_flagged_at_heuristic_boundary() -> None:
    pipeline = {
        "name": "agentic",
        "operations": [
            {"op_id": "quotes", "kind": "read", "release": "2026-08-01T16:00:00",
             "outputs": ["quotes"]},
            {"op_id": "retrieval", "kind": "transform", "value_dependent": True,
             "inputs": ["quotes"], "outputs": ["retrieval"]},
            {"op_id": "decide", "kind": "decision", "decision_time": "2026-08-01T15:00:00",
             "inputs": ["retrieval"], "outputs": ["signal"]},
        ],
    }
    body = check_pipeline(load_pipeline(pipeline))
    by_id = {check["check_id"]: check for check in body["checks"]}
    # structure is still checked exactly: retrieval availability = quotes 16:00
    # which is AFTER the 15:00 decision -> still a look-ahead (P0)
    assert by_id["decision_availability"]["passed"] is False
    assert by_id["heuristic_boundary"]["passed"] is False
    assert by_id["heuristic_boundary"]["severity"] == "P1"


def test_decision_time_is_availability_of_decision_output() -> None:
    body = check_pipeline(load_pipeline(GOOD_PIPELINE))
    assert body["availability"]["decide"] == "2026-08-01T15:00:00"


def test_output_name_references_resolve() -> None:
    """Dataflow semantics: inputs may name an output instead of an op_id."""
    pipeline = {
        "name": "dataflow",
        "operations": [
            {"op_id": "quotes", "kind": "read", "release": "2026-07-31T16:00:00",
             "outputs": ["quotes"]},
            {"op_id": "momentum", "kind": "window", "window_end": "2026-08-01T15:00:00",
             "inputs": ["quotes"], "outputs": ["mom"]},
            {"op_id": "decide", "kind": "decision", "decision_time": "2026-08-01T15:00:00",
             "inputs": ["mom"], "outputs": ["signal"]},  # "mom" is an output name
        ],
    }
    body = check_pipeline(load_pipeline(pipeline))
    by_id = {check["check_id"]: check for check in body["checks"]}
    assert by_id["dag"]["passed"] is True
    assert body["passed"] is True


def test_ambiguous_output_name_is_reported() -> None:
    pipeline = {
        "name": "ambiguous",
        "operations": [
            {"op_id": "a", "kind": "read", "release": "2026-07-31T16:00:00",
             "outputs": ["x"]},
            {"op_id": "b", "kind": "read", "release": "2026-07-31T16:00:00",
             "outputs": ["x"]},
            {"op_id": "decide", "kind": "decision", "decision_time": "2026-08-01T15:00:00",
             "inputs": ["x"], "outputs": ["signal"]},
        ],
    }
    body = check_pipeline(load_pipeline(pipeline))
    by_id = {check["check_id"]: check for check in body["checks"]}
    assert by_id["dag"]["passed"] is False
    assert "ambiguous" in by_id["dag"]["detail"]
