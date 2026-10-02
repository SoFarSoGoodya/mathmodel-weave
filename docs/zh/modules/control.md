# 人工控制与路线探索

control 由文件驱动，不新增调度器或任务数据库：`State` 仍是任务状态的事实来源，`human/control.json` 只保存回答游标、固定的已展示对象、人工决定和采纳事实。`human/coordinator.json` 保存请求指纹，防止对同一已完成协调轮次的重复轮询派发重复任务。

## 最小使用路径

在仓库根目录创建 case，由真人直接编辑题目文字。以下 `/tmp` 路径与环境变量赋值示例使用 POSIX shell；Windows 可运行 `rtk uv run mmagent init 'D:\MathModelCases\case-one'`，并在 Python 示例中替换为该 case 路径（例如原始字符串 `r'D:\MathModelCases\case-one'`）。不要求 Unix 缓存变量。

```bash
UV_CACHE_DIR=/tmp/mmagent-uv-cache uv run mmagent init /tmp/mm-case
```

将确认后的题面放在 `/tmp/mm-case/problem/question.md`。通过 `mathmodel_agent.control.ask_human` 创建模式/范围问题，展示精确的题面引用并设置 `limits={"bounds": {...}}`；真人在 `/tmp/mm-case/human/HUMAN_ANSWERS.md` 中以 `A-###` 标题和 `For: Q-###` 作答。当前共享 CLI 提供 `human ask-tier`、`human answer`、`human refresh` 和 `human decide`，通过 control API 记录真实回答与已展示选项的明确选择。`mathmodel_agent/cli.py` 也已接入 `start` 和 `workflow poll`。这说明当前源码接入情况，不代表新增的实时 provider 测试。

以下自定义 Python 问题入口演示精确对象控制，但不是 `start` 接受的档位对象。启动流程应使用 `human ask-tier`，它绑定所选 profile 的 model/effort 和题面 hash；选档操作不承担 provider session 恢复。

Python 入口示例：

```python
from mathmodel_agent.control import ask_human, record_human_decision

question = ask_human(
    "/tmp/mm-case",
    scope="research_scope",
    displayed={"path": "problem/question.md", "sha256": "<actual-hash>"},
    prompt="Choose the mode and bounds for this exact problem.",
    choices=["standard", "reject"],
    approval_choices=["standard"],
    limits={"bounds": {"max_runs": 2}},
)
# After a real human appends A-001 naming "standard":
record_human_decision("/tmp/mm-case", question_id=question["question_id"], answer_id="A-001", choice="standard")
```

回答通过字节游标只消费一次；末尾的空回答在填入文字前保持未消费。迟到的回答仍绑定最初展示的固定对象，不能批准替换后的对象。测试 fixture 使用 `append_fixture_answer`，始终标为 `simulated`，不构成真实竞赛批准。agent 任务输出不能创建人工决定。

使用 `write_candidate`、`write_variant`、`create_comparison_contract` 和 `write_comparison_pack` 在 `candidates/` 与 `comparisons/` 下创建可读材料。正式 execution 之前，比较合同须明确数据/划分、带单位的指标、约束、基线、预算、失败分母和停止条件。融合方案是带父候选的新 Candidate，初始状态仍为待审。

## 协调任务入口

将 coordinator 作为普通 runtime main agent 任务提交，再运行 supervisor 并轮询：

```python
from mathmodel_agent.workflow import Coordinator, submit_coordinator

task_id = submit_coordinator("/tmp/mm-case", task_id="coordinator-1", prompt="Explore the confirmed case.", inputs=["problem/question.md"])
# The shared CLI exposes `mmagent serve /tmp/mm-case` and `workflow poll`.
result = Coordinator("/tmp/mm-case").poll(task_id)
```

已完成的协调轮次可在 runtime 的 `RESULT.json` 中声明 `requests`、`wait_for` 和 `deliverables`，以及可选的 `human_requests`、`wait_for_human`。workflow 只提交有效的 case 相对路径请求。正式科学任务须包含 `research_class: "formal"`、`research_scope`、非空 `bounds` 和匹配的已批准人工范围。正式路线、结果、融合方案或论文包的选择，还须有绑定同一选定对象的精确人工决定。普通内部迭代不需要额外的正式选择门槛。

子任务或明确的人工问题未解决时，`Coordinator.poll()` 保持等待，不让 coordinator 进程持续运行。依赖解决后，它用有界结果材料调用 `State.resume(task_id, followup=...)`。失败、取消和未知的子任务状态仍会展示，不能被当成成功证据。当前 `mmagent workflow poll CASE TASK` 命令提供这一交接循环；它续接保存的 provider session，不能重建不可用的对话历史。

草稿审阅时，用 `ai_disclosure` 问题展示精确 task ID，以及采纳、修改和人工核验事实。真人确认后，`record_ai_adoption` 可在 PDF 包生成前记录这些事实。构建并暂存完整包后，再用独立的 `paper_package` 问题展示其精确 ArtifactRef。包内容改变后，需要新的问题和决定。
