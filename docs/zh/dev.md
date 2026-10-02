# 不依赖旧会话的开发交接

本仓库包含在所有旧 Codex 对话丢失后继续研发所需的产品源码、测试、契约和维护说明。恢复个人建模 case 是另一项操作；迁移前请看[环境配置](setup.md)。

## 维护入口与阅读顺序

先读 `AGENTS.md`、`PROJECT_MEMORY.md`、本文、[当前状态](status.md)、[设计](design.md)，再读 `docs/zh/modules/` 中对应模块说明。修改前检查当前 Git diff。历史里程碑描述与源码冲突时，以当前实现为准。产品文档和产品记忆只在本仓库维护，个人 case 放在仓库之外。

受 Git 跟踪的 skill 源文件是 `skills/*/SKILL.md`；`.codex/`、`.agents/` 没有被跟踪的产品 skill 文件。克隆后不能依赖这些本地目录、上层仓库或旧的用户级指令。受管任务只接收显式选中的材料和 runtime 提示词；`runtime/scheduler.py` 禁用了隐式项目文档。

## 新设备最小开发步骤

1. 恢复或克隆产品仓库，包括 `uv.lock`，进入产品根目录。Python 要求 3.12 或更新；进程监督器支持 Windows 11 与 Linux/WSL。
2. 运行 `rtk uv sync --locked`、`rtk uv run mmagent --help`、`rtk uv run mmagent doctor`。doctor 是本地诊断，不是 provider 登录或实时模型测试。
3. 阅读所属源码、直接调用者和针对性测试；修改前明确期望行为与范围有限的验证方法。
4. Python 使用 `uv`/`uv add`，可选 Node 工具使用 `bun`，shell 命令使用 `rtk`。出版工作需补齐 TeX 工具，但不要求每次源码修改都先构建论文。

## 源码导航与状态拥有者

表中源码路径相对 `mathmodel_agent/`，测试路径相对仓库根目录，持久状态路径相对 case 根目录。

| 拥有者 | 接口与持久状态 | 针对性检查 |
| --- | --- | --- |
| CLI/配置 | `cli.py:build_parser/main/doctor`；`runtime/config.py:init_case/load_case_config`；`case.toml` | `tests/runtime/test_cli.py`、`tests/runtime/test_state.py`；CLI help |
| Runtime | `runtime/state.py:State`；`runtime/scheduler.py:Supervisor`；`runtime/provider.py`；`.runtime/state.sqlite`、任务输入/工作目录/attempt 日志 | `tests/runtime/test_state.py`、`tests/runtime/test_provider.py`、`tests/runtime/test_scheduler.py` |
| 主机适配 | `runtime/platform.py`：本机文件锁、可执行程序解析、进程创建身份、POSIX 进程组与 Windows Job Object；没有第二个状态库 | `tests/runtime/test_platform.py`；本地 doctor |
| 不可变产物 | `runtime/artifacts.py:publish_bundle/resolve_bundle`；bundle 与回执 | `tests/runtime/test_artifacts.py` |
| 人工控制/协调 | `control.py:ask_human/record_human_decision/record_ai_adoption`；`workflow.py:Coordinator.poll`；人工 Markdown、`human/control.json`、`human/coordinator.json`、worker `RESULT.json` | `tests/control/test_control.py`、`tests/exploration/test_workflow.py` |
| 证据 | `evidence/intake.py`、`evidence/pool.py`、`evidence/freeze.py`；原件、提取数据、`knowledge/registry.json`、`freezes/` | `tests/evidence/test_intake.py`、`tests/evidence/test_pool_freeze.py` |
| 候选/比较 | `exploration.py:write_candidate/write_variant/create_comparison_contract/write_comparison_pack`；`candidates/`、`comparisons/` | `tests/exploration/test_exploration.py` |
| 数值执行 | `execution/worker.py:prepare_experiment/submit_experiment/run_experiment/finalize_experiment`；通过 runtime 发布的不可变运行包 | `tests/execution/test_execution_flow.py` |
| 论文/导出 | `publication/pipeline.py:build_publication`；`publication/checks.py:record_visual_review`；`publication/ai_usage.py`、`publication/manifest.py`、`publication/cli.py`；构建报告、暂存包与导出 | `tests/publication/test_manifest.py`、`tests/publication/test_ai_usage.py`；针对性 `tests/publication/test_pipeline.py` 用例 |

## Windows 针对性验证

Windows runtime 维护不要求研究档位、完整建模 case、实时 provider 请求或 PDF 重建。针对性主机检查可运行 `rtk uv run pytest tests/runtime/test_platform.py tests/runtime/test_scheduler.py tests/runtime/test_cli.py tests/runtime/test_artifacts.py tests/runtime/test_state.py -q -k "not agent_profile_and_policy_are_snapshotted"`。被排除的 profile snapshot 测试沿用了不匹配当前默认模型的旧预期，与 Windows 适配无关，本次不修复。实际结果见[当前状态](status.md)；原生 Windows 细节和 shell 示例见[环境配置](setup.md)与[runtime](modules/runtime.md)。

## 换系统后什么能够恢复

仅凭 Git 即可恢复产品研发：源码、已跟踪 Markdown、测试、模板、示例、`pyproject.toml` 和 `uv.lock`。它不会恢复个人 case 或 provider 的本地历史。用 `uv sync --locked` 重建 `.venv`，用 doctor 检查并重新配置主机工具。如果旧 `.runtime` 中的 TeX 补充树是所需宏包唯一安装副本，就不能把它当作可随意丢弃的缓存。

换系统前停止 supervisor 和其他写入方，然后备份**包含隐藏文件的整个 case 目录**：`case.toml`、`.runtime/state.sqlite` 及当时存在的 SQLite WAL/SHM 文件、`.runtime/receipts`、`tasks/*/input`、`tasks/*/workspace`、`tasks/*/runtime-runs`、`artifacts/`、`human/`、`problem/`、`datasets/`、`sources/`、`knowledge/`、`freezes/`、`candidates/`、`comparisons/`，以及论文、配置、构建和 request 文件。同时保留 case 外的原始文件与已经导出的提交包。单独的数据库既不是完整 case 备份，也不是 provider 对话备份；应复制停止写入后的完整一致状态，不要单独复制仍在写入的数据库文件。

用户另行拥有 Codex/provider profiles、认证、MCP 配置/登录、可选 provider 会话历史、字体和 TeX/系统工具，应在可信本机环境恢复或重建。不得把秘密写入 Git、case TOML/JSON/Markdown、人工回答或聊天。即使所有 provider 历史丢失，也仍能维护产品源码。

### Case 路径与会话边界

`State` 保存绝对任务 workspace 路径与 attempt 的 events/stderr 路径；策略快照也可能包含绝对 extra write paths。当前**没有 case rebase/迁移 CLI**。继续原 case 的 runtime 时，应恢复到原绝对路径。换目录后可能仍能读文件，但不代表 serve、resume、AI 使用事实采集或引用旧路径的命令可以正常运行。无法恢复原路径时，保留旧 case 作为证据，初始化新 case，再用现有 API 显式复制/导入所需材料并记录来源。决定与 ArtifactRef 不会自动跨 case 转移；不得手工修改 SQLite 路径后宣称完成了验证过的迁移。

`mmagent resume CASE TASK` 与 coordinator polling 使用已保存的 provider session，需要该会话仍可由当前 provider/client 访问。SQLite 保存观察到的 ID 与 attempt，不保存 provider 的完整对话。JSONL 日志与 worker 输出可作证据，但不保证包含原始聊天的全部内容。新系统上的旧 session ID 本身无法恢复丢失的历史；unknown-session 或认证失败必须如实保留。

历史不可用时，保留旧 task、attempt 记录、日志、输入快照、`RESULT.json`、产物和人工决定。在恢复原路径的 case 中，提交一个**具有不同 task ID 的新任务**，使用新的 provider session，显式选择已保存的输入/结果，并在提示词中写明旧 task 与未完成事项。不要抹掉旧 session ID、伪造成功 attempt、反复恢复不可用会话或静默创建重复 coordinator 树。CLI 没有原地替换任务 session 的命令。coordinator 的 `wait_for` 与请求指纹仍引用旧 task ID；重新分配需要显式协调，不能假定新任务自动满足旧依赖。

启动经过授权的 coordinator，使用现有 `human ask-tier`/answer/decide 与 `start` 命令。`start` 会校验当前 profile 的 model/effort 和题面哈希是否与批准的档位对象一致。model/effort 或题面改变时，必须重新获得真实决定；扩大权限或重要预算也须确认。绑定对象未变且仍有效的决定应保留。不得从丢失的聊天推断选择，也不得用 synthetic fixture 充当批准。新进程成功仍不等于科学有效。

## 契约与单写规则

`contracts.py` 拥有 `ArtifactRef`（`artifact_id`、`sha256`）和原子 JSON 替换，明确要求调用者保证单写拥有权。人工控制/协调使用 `control-v1`、`coordinator-v1`；探索使用 `candidate-v1`、`variant-v1`、`comparison-contract-v1`、`comparison-pack-v1`；执行使用 `execution-spec-v1`、`execution-run-v1`；出版请求/规则使用 `publication-request-v1`、`publication-rules-v1`。证据 registry/freeze 记录由 evidence 模块拥有，不存在统一覆盖全部记录的版本 schema。

SQLite 通过 WAL 和事务作为任务/attempt 的权威状态。human/control、coordinator、evidence JSON 是各领域记录，不是替代任务数据库。每个 case 使用一个 operator/文件记录写入方和一个 supervisor，不要引入并发的 read-modify-write 调用。publisher 使用 `.runtime/publish.lock` 串行发布、核验哈希与文件集、去重提交回执；这个锁不保护所有领域 JSON。已发布 bundle 与已批准的精确对象必须固定；包改变后需要重新暂存和批准。

## 修改与验证流程

1. 写清要改变的具体行为、所属模块、针对性测试或输入/输出检查。保留无关文件和公开的 case 相对路径契约。
2. 做最小修改。契约改变时，先记录兼容性与迁移限制，再依赖旧 case。不要新增第二套 scheduler、数据库、隐藏自动配置器或文件监听器。
3. 运行上表对应检查，例如 `rtk uv run pytest tests/runtime/test_state.py -q`，加上受影响的 CLI help。出版 pipeline 测试含真实 XeLaTeX 用例；本轮不允许构建时，应选择具体单元用例。实时 provider/MCP 调用、全套测试、论文重建属于额外明确检查。
4. 同步更新对应中英文 guide/module 页面；状态拥有者改变时更新本文，并在 status 写下实际验证。区分源码实现、新执行测试和继承的验收证据；不要把 D5/D6 的测试数量说成新跑的结果。
5. 会话结束前在 Markdown 记录未决工作和限制。检查 diff 是否含凭据、真实 case 数据、生成缓存或非预期改动。

当前后续缺口包括：明确的 case 路径迁移契约、安全的新 session 任务替换/依赖处理、目标主机/provider 的恢复验证，以及 synthetic allocation 以外的题目专用 renderer。写入文档不等于已实现。已接受证据与其他能力限制见[当前状态](status.md)。

## 新会话研发开场提示词

```text
请阅读 AGENTS.md、PROJECT_MEMORY.md、docs/zh/dev.md、docs/zh/status.md、docs/zh/design.md 和对应模块说明。假设所有旧 Codex session 都不可用。检查当前 Git diff 和相关源码/调用者/测试，说明当前行为、状态拥有者、契约和未决限制；使用 rtk、uv/uv add、bun 做授权范围内的最小修改。只执行相关验证，把真实结果同步记录到中英文 Markdown。个人 case 和凭据放在发布仓库外。恢复 case 时保留旧 task/attempt，区分已保存证据和不可访问的 provider 聊天；不得编造批准或宣称支持尚未实现的路径/session 迁移。
```
