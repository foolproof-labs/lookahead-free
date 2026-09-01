# lookahead-free

![PyPI version](https://img.shields.io/pypi/v/lookahead-free.svg)
![PyPI downloads](https://img.shields.io/pypi/dm/lookahead-free.svg)
![CI](https://github.com/holdout-labs/lookahead-free/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

## 中文说明

`lookahead-free` 用于检查量化数据流程是否使用了当时尚未公开的数据，
适合 A 股回测中的行情、财务和公司行为数据流程。你用带时间标记的流程描述
输入数据何时可用，`lf check` 再检查决策是否只读取了当时已知的信息。对于
依赖数据值才决定发布时间的复杂操作，它只报告边界，不声称可以完全证明没有
未来数据，因此不能替代数据供应商和研究流程的人工核验。

**针对数据流程的值无关（value-independent）片段，提供可验证的前视自由
（look-ahead-freedom）。** 将流程声明为一个带时间标注的有向无环图（DAG）
——带发布时间的读取、带结束时间的窗口、带截止时点的 PIT（point-in-time，
时点）读取、带决策时点的决策——然后 `lf check` 以线性时间证明：没有任何
决策消费了当时尚不可知的数据。Python 3.11+，**零依赖**，
支持 Windows / Linux / macOS。

**状态：** v0.1.1 alpha，已发布到 PyPI。模型遵循 Fonseca (2026)；
操作种类与 CLI 预计会继续扩展。

## 为什么存在

前视偏差（look-ahead bias，亦称"未来函数"）是回测的无声杀手：一个用
16:00 才可用的数据计算今日信号、却在 15:00 就"做出决策"的流程，看起来
很好，实则撒谎。通常的防御手段是启发式的——审阅者肉眼检查代码、linter
按模式匹配。这个工具不同：它检查流程的**声明式**（declarative）描述，并在
可以做到精确的片段上给出*精确*的结论。

**它适用于哪里。** `lookahead-free` 检查的是*代码*——即流程的数据流时序
是否可验证地干净（对声明式流程描述做静态扫描）。它不约束研究者的行为；
那是 [`falsification-ledger`](https://github.com/holdout-labs/falsification-ledger)
的职责，后者负责预注册声明并保留防篡改凭证（一种流程约束）。二者互补而
不重叠：一个证明流程没有偷看，另一个证明研究者没有在看到结果后修改预期。

**理论基础。** Fonseca (2026)，
["Look-Ahead-Freedom as Temporal Non-Interference"](https://econpapers.repec.org/paper/arxpapers/2607.04958.htm)
（arXiv:2607.04958，已投稿 ACM TOSEM）证明：前视自由（look-ahead-freedom，
即时序无干扰，temporal non-interference）在一般情况下是**不可判定的**
（当可用性依赖于数据值时，为 Pi-0-1-hard），但在值无关（value-independent）
片段上存在一个**线性时间可判定的类型效应系统**（type-effect system）
——窗口化、重采样、连接、时点（point-in-time）与历史版本（vintage）读取。
本工具实现的正是该系统：

- 每个操作都携带一个时间界（发布 / 窗口结束 / PIT 截止 / 决策时点），
- 输出可用性被精确推导（单调：任何操作都不可能早于其所消费的事实产生事实），
- 决策可用性被精确检查：决策的每个输入都必须在决策时点或之前可用。

**诚实的边界（明确声明，而非隐藏）。** 被声明为 `value_dependent: true`
的操作会在**启发式边界**（heuristic boundary，P1）处被标记：其时序结构
仍被精确检查，但对该操作本身不存在任何可验证的声明——Fonseca 的不可判定
性结果恰恰针对的是值依赖可用性。工具在报告中每次都说明这一点。

## 快速开始

```bash
# install the published package from PyPI
pip install lookahead-free

# or run without installing anything:
#   PYTHONPATH=src python -m lookahead_free --help

python examples/demo.py                    # clean pipeline passes, leaky one fails

lf check --pipeline examples/factor-pipeline.json
lf check --pipeline pipeline.json --json   # machine-readable verdict
```

退出码：`0` = 值无关片段中无前视，`1` = 至少一个 P0 时序违规
（或 DAG 无法解析），`2` = 用法错误。可将其接入 CI，作为每个流程定义的
硬性门槛。

## 流程格式

一个 JSON 对象，包含 `name` 和 `operations` 列表。每个操作：

| 字段 | 含义 |
| --- | --- |
| `op_id` | 唯一节点 id |
| `kind` | `read` / `window` / `resample` / `join` / `pit_read` / `vintage_read` / `transform` / `decision` / `write` |
| `inputs` | 对其他操作的引用——按 `op_id` **或输出名**（数据流语义；有歧义的输出名会被拒绝） |
| `outputs` | 该操作产生的数据名 |
| `release` | （read）数据何时变为可知 |
| `window_end` | （window/resample，必填）回看窗口的结束时间 |
| `read_cutoff` | （pit_read/vintage_read，必填）PIT 截止时点 |
| `decision_time` | （decision，必填）决策作出的时间 |
| `value_dependent` | 可选；标记位于不可判定片段中的操作（智能体检索、值条件可用性） |
| `note` | 自由格式 |

操作的输出可用性 = 其显式边界，或其所有输入可用性的最大值。参见
[examples/factor-pipeline.json](https://github.com/holdout-labs/lookahead-free/blob/main/examples/factor-pipeline.json)
获取一个完整的因子流程示例（行情 → 窗口 → PIT 基本面 → 连接 → 智能体检索
→ 决策）。

## 检查项

| 检查 | 严重级别 | 证明内容 |
| --- | --- | --- |
| `dag` | P0 | 输入可解析（op_id 或输出名）、无重复 id、无环 |
| `monotonicity` | P0 | 没有操作的边界早于某个输入的可用性（不可能的可用性） |
| `decision_availability` | P0 | 决策的每个输入都在决策时点或之前可用——**核心前视检查** |
| `window_boundary` | P0 | window/resample 操作声明其窗口结束时间 |
| `pit_reads` | P0 | PIT/vintage 读取声明其截止时点 |
| `heuristic_boundary` | P1 | 存在值依赖操作 → 结构检查精确，操作语义为启发式（依据 Fonseca 的不可判定性） |
| `pipeline_shape` | P2 | 信息性 |

## 理念

**价格必须可知；决策必须诚实；不可判定性必须被言明。**

计算研究中的可复现性危机是结构性的，而在量化金融中，它首先表现为泄漏
（leakage）：时点数据纪律
（[Kelly et al., NBER w35247](https://www.nber.org/papers/w35247)；
[Look-Ahead-Bench, arXiv:2601.13770](https://ar5iv.labs.arxiv.org/html/2601.13770)）
如今已成为全行业的准则，因为前视会无声地抬高 alpha
（[Daniel, Sornette & Wohrmann 2008](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1289222)）。
一直以来缺少的是一个*机器可检查*的合规声明。`lookahead-free` 把"此流程
没有偷看"这一主张变成一道 CI 门槛，而不是一种审计仪式——并且在理论表明
不存在证明的地方，它明说这一点，而不是假装。

## 开发

```bash
python -m pip install -e . pytest
python -m pytest
```

CI 在 Ubuntu、Windows 和 macOS 上以 Python 3.11 和 3.12 运行完整测试套件。
问题在周末处理；欢迎提交拉取请求（pull request）。

## 相关工作

- [Fonseca (2026), Look-Ahead-Freedom as Temporal Non-Interference (arXiv:2607.04958)](https://econpapers.repec.org/paper/arxpapers/2607.04958.htm) —形式化性质及其可判定性边界
- [Daniel, Sornette & Wohrmann (2008), Look-Ahead Benchmark Bias (SSRN 1289222)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1289222) —被量化的偏差
- [Kelly et al., Scaling Point-in-Time Language Models (NBER w35247)](https://www.nber.org/papers/w35247) —作为行业原则的 PIT
- [Look-Ahead-Bench (arXiv:2601.13770)](https://ar5iv.labs.arxiv.org/html/2601.13770) —在 PIT 系统中测量前视
- [Temporal Leakage in LLM Backtesting (arXiv:2608.02985)](https://scirate.com/arxiv/2608.02985) —为什么被动得分无法区分技能与泄漏

## 项目家族

[Holdout](https://github.com/holdout-labs) 的一部分——用于对抗量化研究中的
自我欺骗的工具链：

- [pit-adjuster](https://github.com/holdout-labs/pit-adjuster) — 带静态前向复权漂移检测的 PIT 后复权调整
- [falsification-ledger](https://github.com/holdout-labs/falsification-ledger) — 预注册与证伪账本
- [factor-qc](https://github.com/holdout-labs/factor-qc) — 失败即关闭（fail-closed）的回测质量门槛
- [lesson-book](https://github.com/holdout-labs/lesson-book) — 交易者的学费记忆
- [lookahead-free](https://github.com/holdout-labs/lookahead-free) — 可验证的前视自由检查
- [ashare-data-immunity](https://github.com/holdout-labs/ashare-data-immunity) — A 股日线数据免疫

姊妹组织：[Metabolism Tools](https://github.com/metabolism-tools) —
[`workspace-metabolism`](https://github.com/metabolism-tools/workspace-metabolism)，
面向智能体工作区（agentic workspace）的策略驱动文件生命周期管理。

## 许可证

MIT
