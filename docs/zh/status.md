# 当前实现与验证证据

当前源码已实现统一 CLI 生命周期：case 初始化/配置与 doctor；任务 submit/status/resume/cancel/serve；档位问题、人工回答和精确对象决定；经授权的 coordinator start 与 workflow polling；PDF/XLSX 导入/校正/验证；证据登记/pin/refresh/freeze；候选与比较契约；经 runtime 执行的数值实验；出版构建、AI 事实、不变暂存、包批准和核验导出。源码导航与针对性测试见[开发交接](dev.md)。

`fast`、`standard`、`full` 是显式人工授权/profile 选择。`start` 将批准档位绑定到展示的题面哈希和 profile model/effort。这些名称本身不实现硬 cost/token/deadline 预算或固定路线数。尚不支持的 deadline/token/cost 任务限制会明确报错；普通范围内工作可以持续推进，重要范围、权限或预算变化仍须真实决定。

## 已记录验证

[ACCEPTANCE.md](../../ACCEPTANCE.md) 记录 `accepted_basic_flow`，不代表真实竞赛运行。继承的 D5 证据包括 58 个产品测试、18 个出版测试，以及经过审阅的 XeLaTeX/BibTeX/Poppler 合成演示。这些数量描述当时记录的测试套件，不是本轮重新执行的当前套件。D6 复用了它，并记录了使用合成人工决定、本地命令、暂存和导出的干净副本 CLI smoke；没有重跑全套测试或重建 PDF。

此前仅更新交接文档的工作没有增加运行或 provider 证据。以下 Windows 检查与继承的验收证据分开记录。

### Windows 11 适配，2026-10-02

`runtime/platform.py` 将 Linux 专有的发布锁、进程身份和进程组机制替换为 Windows 字节锁、创建时间身份及 Job Object，同时保留 POSIX 实现。CLI 和出版子进程会解析 Windows 程序路径并容忍不可解码的诊断字节；doctor 可查询 Windows 字体注册表。选定输入树和发布 staging 同时拒绝符号链接及 junction。

在当前 Windows 11 / Python 3.14.3 主机执行：

```text
rtk uv sync --locked
rtk uv run mmagent --help
rtk uv run mmagent doctor
rtk uv run pytest tests/runtime/test_platform.py tests/runtime/test_scheduler.py tests/runtime/test_cli.py tests/runtime/test_artifacts.py tests/runtime/test_state.py -q -k "not agent_profile_and_policy_are_snapshotted"
```

针对性测试结果为 **29 passed, 1 deselected**，Windows 下没有 skip。覆盖真实本地进程启动/并行、取消和强制回收进程树、超时、supervisor 崩溃清理与存活 job 协调、包含退出码 259 的进程身份判断、持锁方崩溃后的释放及并发发布回执去重、UTF-8 诊断、含空格的批处理启动器/任务独立 PATH/相对程序路径、本机字体检查及 junction 拒绝。Windows 不允许创建符号链接时，链接 fixture 使用 junction。provider 形态的重试/后续测试使用本地 Python JSONL fixture，没有调用模型。被排除的 snapshot 测试仍预期旧默认 `gpt-5.6-sol`/high，当前初始化器实际为 `gpt-5.6-terra`/high；该原有不匹配与适配无关，本次不修复。

Doctor 在本机完成，找到 CLI/TeX/Poppler 工具及 CTeX/xeCJK/zhnumber；所需 Noto Serif/Sans CJK SC 字体缺失。这不代表论文构建通过。本轮未启动完整建模 case，未运行全产品套件、实时 provider/MCP、PDF 重建或页面审阅，也未在当前主机重新验证 Linux 分支。

## 恢复与能力限制

Git 能在没有历史 Codex session 的情况下恢复产品研发。个人 case 与用户级 provider/MCP/登录配置需要另行备份或重建。应备份完整 case，包括隐藏 `.runtime`、SQLite 状态及附属文件、回执、任务、日志、产物、人工记录、输入和出版文件。SQLite 不能重建 provider 的完整对话。

Runtime 记录包含绝对 workspace、events/stderr 路径，也可能包含绝对 extra write paths。继续现有 case 需要原绝对路径；当前没有 rebase CLI。`resume` 使用保存的 provider session，无法重建不可用历史。需要换 session 时保留旧 task/attempt/输出，在新任务与新 session 中显式接续选定材料。详见[环境配置](setup.md)和[开发交接](dev.md)；不得手改 SQLite 后宣称完成迁移。

需要 Windows 11 或 Linux/WSL 和已配置的本地工具。原生 Windows runtime 不会迁移旧 Linux 绝对路径或恢复 provider 历史。PDF 导入通过 `pypdf` 读取内嵌文本；扫描 PDF 的 OCR/MinerU 是外部预处理，没有内置 MinerU SDK。XLSX 通过 `openpyxl` 导入，不计算公式。TeX、字体和 Poppler 是主机依赖。新的科学图 schema 需要题目专用 renderer。每个真实 case 都须获取并冻结当年适用的竞赛/赛区规则，使用真实人工决定和真实 AI 采纳事实。

## 未决工作

- 定义并验证显式 case 路径迁移，同时保留任务/attempt/产物来源。
- 提供安全的新 session 任务替换和 coordinator 依赖处理；当前 CLI 没有原地替换 session 的能力。
- 在获得授权后验证实际目标主机/provider、认证、MCP/工具及 provider 特定恢复行为。
- 只在真实任务需要时添加题目专用图形 renderer 和证据检查。

行为变化时，用实际检查结果同步更新本页、英文文档和所属模块说明。文档改变不等于功能实现或实时系统验证。
