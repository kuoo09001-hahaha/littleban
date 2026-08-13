# 小伴 Harness 实验层

这个目录是对现有 Agent API 的轻量运行层，不替换 `HDZB_agent` 的产品逻辑。

它为每条评测生成标准化 `harness_trace`：开始、每轮 HTTP 调用、重试次数、
下游 `trace_id`、工具使用和耗时。当前策略只对网络/HTTP 调用异常重试一次，
不会对模型回答静默重试，避免掩盖模型质量问题。

对比命令：

```bash
python evaluation/run_live_eval.py --runner baseline --dataset evaluation/datasets/family_memory_bench.jsonl
python evaluation/run_live_eval.py --runner harness --dataset evaluation/datasets/family_memory_bench.jsonl
```

两个 runner 调用同一 Agent、同一 SQLite 和同一数据集；区别是 Harness 额外提供
可观测步骤与失败重试。这样可以分别比较任务成功率、平均延迟、失败恢复和轨迹完整性。
