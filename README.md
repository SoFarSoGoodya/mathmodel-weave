# MathModel Weave：数学建模多智能体工作台

本产品仓库是一个可独立运行的数学建模工作台。对应的框架逆向分析、来源证据和融合决策保存在独立的[研究仓库](https://github.com/SoFarSoGoodya/mathmodel-research)；研究仓库不属于运行依赖。发布到 GitHub 时，只需把链接中的 `SoFarSoGoodya` 换成你的账号或组织名。

## 项目特点

本项目同时提供两层能力：

1. **建模 skill 与流程层**：把读题、数据整理、文献证据、候选路线、实验、审阅、论文和 AI 使用披露组织成有明确输入输出的步骤。它约束应该检查什么、产物如何交接，以及哪些事项必须由人确认。
2. **真实的多 agent 运行时层**：用独立任务、权限范围、会话身份、持久状态、并行探索和受控提交来运行多个 agent。不同 agent 不是同一个聊天窗口里换几段提示词，而是拥有可追踪边界的受管任务。

中文数学建模领域的工具主要集中在 skill 流程上，给出了不同建模阶段的明确约束与操作指导，但较为缺乏可恢复的多 agent 协作运行时，典型例子包括 [MathModel-Skill](https://github.com/yushui2022/MathModel-Skill)、[MathModelAgent](https://github.com/jihe520/MathModelAgent) 以及基于 MathModelAgent 开发的 [MathMN](https://github.com/ShuoSachiko/MathMN)。而 AI for Math/应用数学领域的工具主要提供通用的 agent 编排，例如主攻纯数学多 agent 协作探索的 [Danus](https://github.com/frenzymath/Danus)、应用数学科研的 [ReasFlow](https://github.com/reaslab/ReasFlow) 和 [Station](https://github.com/dualverse-ai/station)，但针对特定的建模比赛项目，往往缺乏所需的题意校正、路线比较、证据冻结和论文验收。本项目深度挖掘并参考了这六个项目，把两层能力放在同一套 case 协议中，同时保留 agent 探索层面的自由开发，以及流程层面的 skill 外部约束和人类决策与介入。

## 六大模块

| 层           | 模块          | 作用                                                        | 主要产物                       |
| ------------ | ------------- | ----------------------------------------------------------- | ------------------------------ |
| 运行时与治理 | `runtime`     | 启动受管任务、保存会话与进程状态、处理有限恢复              | task state、事件日志、attempt  |
| 运行时与治理 | `control`     | 记录权限、研究档位、人工问题与决定，设置明确的人为门槛      | decision、permission、approval |
| skill 与流程 | `evidence`    | 导入 PDF/XLSX，校正题面，维护文献和数据证据，冻结可引用版本 | source text、registry、freeze  |
| skill 与流程 | `exploration` | 生成独立候选路线，定义比较合同，支持开放式多路径探索        | candidate、comparison          |
| skill 与流程 | `execution`   | 按声明的输入和命令运行代码，记录指标、失败和检查结果        | run manifest、metrics、checks  |
| skill 与流程 | `publication` | 组织图表、TeX、参考文献、AI 使用详情并生成精确发布包        | paper、figures、release bundle |

运行时层负责“谁在什么权限下运行、状态如何恢复”；skill 层负责“数学建模工作的每一步如何完成和验收”。两层通过 case-relative 文件、manifest、检查结果和人工决定交接。

```text
题目/数据 -> evidence -> exploration -> runtime 执行
                                      -> execution/checks
                                      -> publication -> 人工批准 -> 发布包
                       control 在各阶段记录权限、问题与决定
```

## 快速开始

你只需要准备bash/zsh环境(作者对本项目开发测试和正式使用的环境为wsl2+Ubuntu24LTS+Codex CLI, Windows的适配留待后续开发)、Python、`uv`，以及用于生成论文的 XeLaTeX。没有使用经验时，不必先学习命令行：

1. 安装并打开 Codex(CLI或者客户端均可)，在本产品仓库目录创建一个新的主沟通会话。推荐使用 Luna档位 作为日常引导模型。
2. 把下面这段提示词发给 Codex：

    > 请先阅读 `AGENTS.md`、`docs/guide.md`、`docs/setup.md` 和 `docs/status.md`。你是本项目的协调助手：先检查环境并告诉我缺什么，再一步步引导我准备题目；后续由你负责启动和管理后台 agent、记录状态、提出需要我决定的问题。我只通过对话做选择和确认，不直接操作底层代码或命令行。

3. 按助手的提问提供题目文件、选择研究档位并确认题面。助手会继续安排后台工作，遇到必须由人决定的路线、结果或发布事项时再询问你。

熟悉命令行的开发者也可以直接运行：

```bash
uv sync --locked
uv run mmagent doctor
uv run mmagent init CASE
```

手动命令、配置文件、MinerU 外部预处理和故障处理见 [环境配置](docs/setup.md) 与 [命令参考](docs/cli.md)。内置 PDF/XLSX 读取使用 `pypdf` 和 `openpyxl`；扫描 PDF 可先用外部 OCR 或 MinerU 处理，本产品当前不包含 MinerU SDK 适配器。

## 人机协作

把 Codex 主会话当作唯一入口即可。你负责说明目标、回答问题和作出决定；协调助手负责检查配置、初始化 case、启动和管理后台 agent、在断流或中断后按规则重试/恢复、读取最新状态，并把需要你确认的内容用自然语言说清楚。你不需要记住后台 agent 的名称，也不需要手动反复执行 CLI 命令。

开始新题时，先发送上面的短提示词。之后按顺序完成三件事：确认题面文字，选择研究档位，批准或否决候选路线。实验迭代、状态保存和可恢复运行由助手处理；最终路线、结果、AI 使用说明和发布包仍由你确认。以后换设备或聊天中断时，重新打开仓库并让助手读取 `AGENTS.md`、`docs/guide.md` 和当前 case 状态，就能继续。

如果你直接编辑了 case 中的 Markdown，只需告诉助手“我已更新文件，请读取最新内容”。账号密钥和模型配置由 Codex 管理，不要写进仓库或 case 文件。

## 文档与目录

- [用户指南](docs/guide.md)：第一次使用、交题、确认和恢复。
- [环境配置](docs/setup.md)：依赖、模型、MCP、TeX 和可选预处理。
- [命令参考](docs/cli.md)：命令行输入输出和示例。
- [设计说明](docs/design.md)：分层架构、数据流和状态边界。
- [开发交接](docs/dev.md)：换设备后从零恢复并继续开发。
- [当前状态](docs/status.md)：已验证能力、限制和后续入口。
- [来源与借鉴](docs/origins.md)：六个来源体系、采用机制和许可边界。
- [模块说明](docs/modules/)：六大模块的接口和行为。
- 中文专题文档位于 [docs/zh](docs/zh/)。

目录中的 `skills/` 是流程约束与任务说明，`mathmodel_agent/` 是运行时代码，`templates/` 是论文和发布模板，`examples/` 是合成示例。研究记录、上游源码和下载的 skill 包不是运行或开发前提。

## 来源与许可

本项目尊重并研究了 [Danus](https://github.com/frenzymath/Danus)、[ReasFlow](https://github.com/reaslab/ReasFlow)、[Station](https://github.com/dualverse-ai/station)、[MathModelAgent](https://github.com/jihe520/MathModelAgent)、[MathMN](https://github.com/ShuoSachiko/MathMN) 和 [MathModel-Skill](https://github.com/yushui2022/MathModel-Skill) 六个独立项目。它们提供了可借鉴的角色协作、会话恢复、建模流程、证据管理和论文约束；本仓库重新实现自己的接口，不默示复制或继承上游许可证。来源映射见 [docs/origins.md](docs/origins.md)，法律条款见 [LICENSE](LICENSE)、[NOTICE.md](NOTICE.md) 和 [licenses/](licenses/)。

本仓库示例使用合成数据，不代表任何竞赛提交。
