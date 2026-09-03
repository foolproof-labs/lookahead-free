"""Tests for the heuristic companion scanner (``lf scan``).

The heuristic layer is explicitly NOT a proof: hard findings (H001/H002)
fail the run, review findings (H003) are listed but do not fail it.  The
verifiable layer stays ``lf check``.
"""

from __future__ import annotations

from lookahead_free.heuristic import scan_python_source

FUTURE_INDEX_SRC = """
def calculator(arrays, index):
    return float(arrays['close'][index + 5] / arrays['close'][index] - 1.0)
"""

FUTURE_SLICE_SRC = """
def calculator(arrays, index):
    window = arrays['close'][index + 1:index + 6]
    return float(sum(window) / len(window))
"""

FETCH_WITHOUT_TIME_SRC = """
def pull_quotes(code):
    return fetch_quotes(code)
"""

CLEAN_SRC = """
def calculator(arrays, index):
    if index < 20:
        return 0.0
    return float(arrays['close'][index] / arrays['close'][index - 20] - 1.0)
"""


def test_h001_future_subscript_fails() -> None:
    report = scan_python_source(FUTURE_INDEX_SRC, path="leak.py")
    assert report["verdict"] == "FAIL"
    assert report["passed"] is False
    rules = [f["rule"] for f in report["findings"]]
    assert "H001" in rules


def test_h002_future_slice_fails() -> None:
    report = scan_python_source(FUTURE_SLICE_SRC, path="leak.py")
    assert report["passed"] is False
    assert "H002" in [f["rule"] for f in report["findings"]]


def test_h003_fetch_without_time_param_is_review_only() -> None:
    report = scan_python_source(FETCH_WITHOUT_TIME_SRC, path="data.py")
    findings = report["findings"]
    assert any(f["rule"] == "H003" and f["kind"] == "review" for f in findings)
    assert report["passed"] is True  # review findings never fail the run


def test_clean_source_passes() -> None:
    report = scan_python_source(CLEAN_SRC, path="clean.py")
    assert report["verdict"] == "PASS"
    assert report["passed"] is True
    assert report["findings"] == []


def test_syntax_error_fails_closed() -> None:
    report = scan_python_source("def broken(:\n", path="bad.py")
    assert report["passed"] is False
    assert any("syntax_error" in str(b) for b in report["blockers"])
