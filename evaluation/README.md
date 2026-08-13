# CompanionBench

`CompanionBench` is a small, versioned evaluation set for the Agent's core
capabilities: tool selection, tool arguments, long-term memory, and safety.
It intentionally uses a transparent JSONL schema so every failure can be read
and annotated by hand.

Run a saved set of Agent outputs:

```bash
python evaluation/run_eval.py \
  --dataset evaluation/datasets/companion_bench.jsonl \
  --results path/to/agent_results.jsonl
```

Each result line contains an `id`, `answer`, and optional `tool_calls` list.
The runner writes a JSON report with overall and per-category scores. For
live evaluation, a future runner can call `/agent/chat` and collect its
`trace_id`; keeping the scoring code model-independent makes comparisons
reproducible.

## Run against the local Agent

Start the Agent first, then run a small smoke test before a full benchmark.
This calls your configured model and external tools, so it creates real API
usage and may take several minutes.

```bash
python evaluation/run_live_eval.py --limit 2
python evaluation/run_live_eval.py
```

The runner gives every case a fresh session and preserves context inside each
multi-turn case. Raw outputs go to `evaluation/results/`; the paired report
shows task success rate plus scores for tool calls, memory, reminders, and
safety. Review each failed JSONL record and its `trace_id` before changing
code or prompts.

`long_memory` cases cover family-scoped, time-aware health events. They must
use a non-default `family_id` and an `actor_name` when a person says “我…”, so
the event can be attributed to the correct family member.

## 家庭多用户与长期记忆测评

新增的 `family_memory_bench.jsonl` 专门测真实的跨用户链路：一位家庭成员
在自己的会话中说出不适，另一位成员从不同会话查询；脚本还会调用
`/agent/health-memory`，确认 SQLite 中确实写入了对应家庭和对应成员的记录。

先启动 Agent（默认 `8017`），再运行：

```bash
python evaluation/run_live_eval.py \
  --dataset evaluation/datasets/family_memory_bench.jsonl
```

每一次运行都会给每条 case 自动生成一个新的 `family_id`，因此旧的 SQLite
健康记录不会让这次测评“虚高”。终端会输出两个文件，例如：

```text
Raw results: evaluation/results/live-20260812-xxxxxx.jsonl
Report: evaluation/results/live-20260812-xxxxxx.report.json
```

查看报告：

```bash
cat evaluation/results/live-20260812-xxxxxx.report.json
```

重点看 `family_long_memory`（跨会话健康记忆）和 `multi_user_isolation`
（奶奶的提醒不会出现在爸爸会话）。原始 JSONL 中的 `family_id`、`turns` 和
`storage_check.events` 可用于复盘每一条失败；其中 `storage_check.events`
不是模型生成内容，而是直接从 SQLite 经 API 读出的持久化证据。

## Baseline 与 Harness 对比

默认 `baseline` 直接请求 Agent。`harness` 使用 `harness/` 中的轻量运行层，
对相同请求补充标准步骤、下游 trace 关联和一次传输失败重试；它不改变产品
Agent 的提示词、模型、SQLite 或网页。因此两份结果可以公平对比。

```bash
python evaluation/run_live_eval.py --runner baseline --dataset evaluation/datasets/family_memory_bench.jsonl
python evaluation/run_live_eval.py --runner harness --dataset evaluation/datasets/family_memory_bench.jsonl
```

在 Harness 的原始 JSONL 里查看 `harness_trace`：每轮有 `attempts`、`latency_ms`、
`tool_used` 与 Agent 原始 `trace_id`。报告仍使用同一个评分器计算任务成功率。

## 困难集与故障注入

`family_memory_challenge_bench.jsonl` 不保证满分，它刻意覆盖同义表达、否定、
多成员混合记录、最新事件、关系名与真实姓名的关联、空记录和家庭隔离。它用于
发现当前记忆抽取规则的边界：

```bash
python evaluation/run_live_eval.py --runner baseline \
  --dataset evaluation/datasets/family_memory_challenge_bench.jsonl
```

`harness_fault_injection_bench.jsonl` 配合 `--inject-first-attempt-failure`
在**评测脚本进程内**让每个会话的首个 Agent HTTP 尝试失败一次，不会影响网页、
Agent 服务或真实数据。Baseline 没有重试，预期失败；Harness 应通过一次重试恢复：

```bash
python evaluation/run_live_eval.py --runner baseline --inject-first-attempt-failure \
  --dataset evaluation/datasets/harness_fault_injection_bench.jsonl

python evaluation/run_live_eval.py --runner harness --inject-first-attempt-failure \
  --dataset evaluation/datasets/harness_fault_injection_bench.jsonl
```

这组实验的正确结论是：稳定路径不一定提升成功率；受控瞬时网络故障下，Harness
通过显式重试提升恢复率，并在 `harness_trace` 中留下 `attempts: 2` 的证据。

## 记忆策略优化与 Holdout 验证

困难集是开发集：用来定位同义表达、否定和最新事件等问题。优化后，必须再跑
独立的 `family_memory_holdout_bench.jsonl`，避免只针对困难集写规则：

```bash
python evaluation/run_live_eval.py --runner baseline \
  --dataset evaluation/datasets/family_memory_challenge_bench.jsonl

python evaluation/run_live_eval.py --runner baseline \
  --dataset evaluation/datasets/family_memory_holdout_bench.jsonl
```

Holdout 使用未在困难集出现过的表达，例如“脑壳疼”“有点发热”“去泳池游个泳”
和“没有去学校”。报告时应分别列出开发集与 Holdout 的得分，不能只报告开发集。
