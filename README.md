# lookahead-free

![PyPI version](https://img.shields.io/pypi/v/lookahead-free.svg)
![PyPI downloads](https://img.shields.io/pypi/dm/lookahead-free.svg)
![CI](https://github.com/foolproof-labs/lookahead-free/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

## 中文说明

`lookahead-free` 用于检查量化数据流程是否使用了当时尚未公开的数据，
适合 A 股回测中的行情、财务和公司行为数据流程。你用带时间标记的流程描述
输入数据何时可用，`lf check` 再检查决策是否只读取了当时已知的信息。对于
依赖数据值才决定发布时间的复杂操作，它只报告边界，不声称可以完全证明没有
未来数据，因此不能替代数据供应商和研究流程的人工核验。

**Verifiable look-ahead-freedom for the value-independent fragment of data
pipelines.** Declare your pipeline as a temporally annotated DAG —reads
with release times, windows with ends, PIT reads with cutoffs, decisions
with decision times —and `lf check` proves, in linear time, that no
decision consumes data that was not knowable yet. Python 3.11+, **zero
dependencies**, Windows / Linux / macOS.

**Status:** v0.1 —alpha. The model follows Fonseca (2026); expect the op
kinds and CLI to grow.

## Why this exists

Look-ahead bias is the quiet killer of backtests: a pipeline that computes
today's signal from data that only becomes available at 16:00, then
"decides" at 15:00, looks great and lies. The usual defenses are
heuristics —reviewers eyeballing code, linters matching patterns. This
tool is different: it checks a **declarative** description of the pipeline
and gives an *exact* verdict on the fragment where exactness is possible.

**Grounding.** Fonseca (2026),
["Look-Ahead-Freedom as Temporal Non-Interference"](https://econpapers.repec.org/paper/arxpapers/2607.04958.htm)
(arXiv:2607.04958, submitted to ACM TOSEM) proves that look-ahead-freedom
is **undecidable in general** (Pi-0-1-hard when availability depends on data
values), but admits a **linear-time decidable type-effect system** on the
value-independent fragment —windowing, resampling, joins, point-in-time
and vintage reads. This tool implements exactly that system:

- every op carries a temporal bound (release / window end / PIT cutoff /
  decision time),
- output availability is derived exactly (monotone: no op can produce a
  fact earlier than the facts it consumes),
- decision availability is checked exactly: every input of a decision must
  be available at or before the decision time.

**Honest boundary (stated, not hidden).** Operations declared
`value_dependent: true` are flagged at the **heuristic boundary** (P1):
their temporal structure is still checked exactly, but for the operation
itself no verifiable claim exists —Fonseca's undecidability result is
precisely about value-dependent availability. The tool says so, in the
report, every time.

## Quick start

```bash
# install from PyPI (once published)
pip install lookahead-free

# or run without installing anything:
#   PYTHONPATH=src python -m lookahead_free --help

python examples/demo.py                    # clean pipeline passes, leaky one fails

lf check --pipeline examples/factor-pipeline.json
lf check --pipeline pipeline.json --json   # machine-readable verdict
```

Exit codes: `0` = no look-ahead in the value-independent fragment,
`1` = at least one P0 temporal violation (or unresolvable DAG),
`2` = usage error. Wire it into CI as a hard gate on every pipeline
definition.

## Pipeline format

A JSON object with a `name` and an `operations` list. Each op:

| Field | Meaning |
| --- | --- |
| `op_id` | unique node id |
| `kind` | `read` / `window` / `resample` / `join` / `pit_read` / `vintage_read` / `transform` / `decision` / `write` |
| `inputs` | references to other ops —by `op_id` **or by output name** (dataflow semantics; ambiguous output names are rejected) |
| `outputs` | data names this op produces |
| `release` | (read) when the data becomes knowable |
| `window_end` | (window/resample, required) end of the lookback window |
| `read_cutoff` | (pit_read/vintage_read, required) the PIT cutoff |
| `decision_time` | (decision, required) when the decision is made |
| `value_dependent` | optional; marks ops in the undecidable fragment (agentic retrieval, value-conditional availability) |
| `note` | free-form |

Availability of an op's output = its explicit bound, or the maximum
availability of its inputs. See
[examples/factor-pipeline.json](https://github.com/foolproof-labs/lookahead-free/blob/main/examples/factor-pipeline.json) for a
complete factor pipeline (quotes -> windows -> PIT fundamentals -> join -> agentic retrieval -> decision).

## The checks

| Check | Severity | What it proves |
| --- | --- | --- |
| `dag` | P0 | inputs resolve (op_id or output name), no duplicate ids, no cycles |
| `monotonicity` | P0 | no op's bound is earlier than an input's availability (impossible availability) |
| `decision_availability` | P0 | every input of a decision is available at or before the decision time —**the core look-ahead check** |
| `window_boundary` | P0 | window/resample ops declare their window end |
| `pit_reads` | P0 | PIT/vintage reads declare their cutoff |
| `heuristic_boundary` | P1 | value-dependent ops present -> structural checks exact, op semantics heuristic (per Fonseca's undecidability) |
| `pipeline_shape` | P2 | informational |

## Philosophy

**Prices must be knowable; decisions must be honest; undecidability must be
stated.**

The reproducibility crisis in computational research is structural, and in
quantitative finance it shows up first as leakage: point-in-time data
discipline ([Kelly et al., NBER w35247](https://www.nber.org/papers/w35247);
[Look-Ahead-Bench, arXiv:2601.13770](https://ar5iv.labs.arxiv.org/html/2601.13770))
is now an industry-wide principle because look-ahead silently inflates
alpha ([Daniel, Sornette & Wohrmann 2008](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1289222)).
What has been missing is a *machine-checkable* statement of compliance.
`lookahead-free` makes the claim "this pipeline does not peek" a CI gate
instead of an audit ritual —and where the theory says no proof exists, it
says so instead of pretending.

## Development

```bash
python -m pip install -e . pytest
python -m pytest
```

CI runs the full test suite on Ubuntu, Windows and macOS with Python 3.11
and 3.12. Issues are handled on weekends; pull requests are welcome.

## Related work

- [Fonseca (2026), Look-Ahead-Freedom as Temporal Non-Interference (arXiv:2607.04958)](https://econpapers.repec.org/paper/arxpapers/2607.04958.htm) —the formal property and its decidability boundary
- [Daniel, Sornette & Wohrmann (2008), Look-Ahead Benchmark Bias (SSRN 1289222)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1289222) —the bias, quantified
- [Kelly et al., Scaling Point-in-Time Language Models (NBER w35247)](https://www.nber.org/papers/w35247) —PIT as an industry principle
- [Look-Ahead-Bench (arXiv:2601.13770)](https://ar5iv.labs.arxiv.org/html/2601.13770) —measuring look-ahead in PIT systems
- [Temporal Leakage in LLM Backtesting (arXiv:2608.02985)](https://scirate.com/arxiv/2608.02985) —why passive scores cannot separate skill from leakage

## Project family

Part of [Foolproof Labs](https://github.com/foolproof-labs) — a toolchain
against self-deception in quantitative research:

- [pit-adjuster](https://github.com/foolproof-labs/pit-adjuster) — PIT back-adjustment with static forward-adjustment drift detection
- [falsification-ledger](https://github.com/foolproof-labs/falsification-ledger) — pre-registration and falsification ledger
- [factor-qc](https://github.com/foolproof-labs/factor-qc) — fail-closed backtest quality gate
- [lesson-book](https://github.com/foolproof-labs/lesson-book) — tuition memory for traders
- [lookahead-free](https://github.com/foolproof-labs/lookahead-free) — verifiable look-ahead-freedom checks
- [ashare-data-immunity](https://github.com/foolproof-labs/ashare-data-immunity) — data immunity for A-share daily bars

## License

MIT
