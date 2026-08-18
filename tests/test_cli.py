"""End-to-end CLI tests and schema validation of example pipelines."""

from __future__ import annotations

import json

import pytest

from lookahead_free.cli import main
from lookahead_free.model import load_pipeline


@pytest.fixture()
def good_pipeline(tmp_path):
    pipeline = {
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
    path = tmp_path / "good.json"
    path.write_text(json.dumps(pipeline), encoding="utf-8")
    return str(path)


@pytest.fixture()
def leaky_pipeline(tmp_path):
    pipeline = {
        "name": "leaky",
        "operations": [
            {"op_id": "quotes", "kind": "read", "release": "2026-08-01T16:00:00",
             "outputs": ["quotes"]},
            {"op_id": "decide", "kind": "decision", "decision_time": "2026-08-01T15:00:00",
             "inputs": ["quotes"], "outputs": ["signal"]},
        ],
    }
    path = tmp_path / "leaky.json"
    path.write_text(json.dumps(pipeline), encoding="utf-8")
    return str(path)


def test_cli_version() -> None:
    assert main(["version"]) == 0


def test_cli_check_good(good_pipeline, capsys) -> None:
    assert main(["check", "--pipeline", good_pipeline]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out
    assert "decision_availability" in out


def test_cli_check_leaky_fails(leaky_pipeline, capsys) -> None:
    assert main(["check", "--pipeline", leaky_pipeline]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "LOOK-AHEAD" in out


def test_cli_check_json(good_pipeline, capsys) -> None:
    assert main(["check", "--pipeline", good_pipeline, "--json"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["schema_version"] == "lookahead_free.check.v1"
    assert body["passed"] is True
    assert len(body["checks"]) == 7


def test_example_pipeline_is_well_formed() -> None:
    example = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "examples" / "factor-pipeline.json"
    )
    pipeline = load_pipeline(example)
    assert pipeline.name == "factor-pipeline"
    assert len(pipeline.operations) >= 5
