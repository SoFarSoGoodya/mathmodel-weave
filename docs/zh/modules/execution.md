# 实验执行

`mathmodel_agent.execution` 把一条批处理算法命令转换为一个不可变运行包，用于真实的本地数值运行。内置 allocation 数据和生成值都是**合成演示，不是竞赛输出**。

## 流程

1. 构造 `ExperimentRequest` 字典并调用 `prepare_experiment(case, request)`。
2. 调用 `submit_experiment(case, prepared)`，它会快照代码、配置、输入、比较契约和 `uv.lock`，再通过 runtime 状态提交 `kind="command"` 任务。
3. 让 `runtime.scheduler.Supervisor` 执行，或使用 `run_experiment(case, request)`。
4. 显式流程中调用 `finalize_experiment(case, task_id)`，读取持久化运行事实和完整观测，写入 `run_manifest.json`，并调用一次 `runtime.artifacts.publish_bundle`。

执行模块不拥有独立 runner、数据库、调度器、按 seed 的任务循环或预算账本。重跑必须使用新的 `experiment_run_id`；同一暂存目录再次 finalize 只属于发布收据去重。

## 请求契约

请求必须是 JSON 兼容对象；`code`、`config`、每个 input 的 `path` 和 `comparison_contract` 都是相对于 case 的普通文件。正式请求必须有比较契约。`command` 是 argv 列表，只展开以下占位符：

```python
{
    "class": "formal",  # prototype | formal | recompute
    "task_id": "allocation-formal",
    "experiment_run_id": "XR-allocation-formal",
    "purpose": "What decision this run informs.",
    "code": "demo/allocation.py",
    "config": "demo/allocation_config.json",
    "inputs": [{"id": "instances", "path": "datasets/instances.json"}],
    "comparison_contract": "demo/comparison_contract.json",
    "instances": [{"id": "case-a", "seed": None}],
    "command": ["uv", "run", "python", "{code}", "--config", "{config}",
                "--input", "{input:instances}", "--output", "{output_dir}"],
    "timeout_seconds": 120,
}
```

完整占位符集合是 `{code}`、`{config}`、`{input:<id>}` 和 `{output_dir}`，不接受任意 shell 字符串。确定性算法使用 `seed: None`，不会凭空增加重复次数。

每条完整观测记录需要 `instance_id` 和 `status`（`completed`、`failed` 或 `timed_out`）。结果包包含运行清单、实际复制的代码/配置/输入、冻结的 `uv.lock`、观测、重算指标、检查证据和声明的图文件。

`complete` 表示所有规划实例完成且检查通过；`partial` 表示覆盖不完整但仍保留可用观测；`invalid` 表示指标或独立约束失败；`not_run` 表示没有运行尝试；无可靠完整观测的已启动命令为 `unknown`。坏 JSONL 记录会被排除并写入 `issues`。

`redraw_figure(run_directory, display_config)` 只从已保存 CSV 重绘 PNG，不改变指标或运行清单。改变样本、单位或聚合方式属于新的科学运行，不能只重绘。

## 合成运行

从产品根目录运行：

```bash
MPLCONFIGDIR=/tmp/mmagent-mpl uv run python examples/experiment/allocation/run_demo.py /tmp/synthetic-allocation-case
```

结果位于 `/tmp/synthetic-allocation-case/artifacts/bundle-*/run_manifest.json`。演示包含 greedy 平均值 `16.5`、exhaustive 平均值 `19.5` 和 `1/3` 失败分母，仅用于展示流程。

