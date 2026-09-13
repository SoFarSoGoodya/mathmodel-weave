# 来源与借鉴

本页是产品运行者可读的来源摘要。每个来源的独立调查、版本、证据等级和完整取舍记录位于独立的[研究仓库](https://github.com/<your-org>/mathmodel-research)；产品不要求下载或阅读研究仓库才能运行。

六个来源体系分为三类运行时与三类建模流程：

| 来源体系 | 借鉴内容 | 产品中的融合位置 |
| --- | --- | --- |
| [Danus](https://github.com/frenzymath/Danus) | 独立 worker、角色工具边界、验证后写入 | `runtime/`、`control/` |
| [ReasFlow](https://github.com/reaslab/ReasFlow) | specialist 会话身份、任务交接、knowledge card 思路 | `runtime/`、`workflow.py` |
| [Station](https://github.com/dualverse-ai/station) | 并行推理与单写提交、分支隔离、局部恢复、人工暂停 | `runtime/`、`control/` |
| [MathModelAgent](https://github.com/jihe520/MathModelAgent) | 分阶段读题、建模、代码和论文流程 | `skills/`、各模块说明 |
| [MathMN](https://github.com/ShuoSachiko/MathMN) | 证据账本、路线映射、文献检索和可追踪交接 | `skills/evidence/`、`skills/exploration/` |
| [MathModel-Skill](https://github.com/yushui2022/MathModel-Skill) | 结构化题面、候选 tournament、复算/稳健性检查和论文发布门 | `skills/`、`execution/`、`publication/`、`templates/` |

这些是机制层面的参考，不是把任何一个上游框架作为底座。产品保留了数学建模需要的开放多路线探索，同时用确定性状态、权限和人工门把探索结果变成可回看的 case 产物。没有把上游服务拓扑、房间系统、事实图或完整角色链复制进来，也不把局部 evaluator 宣称为数学正确性证明。

产品代码和流程接口由本仓库独立实现。上游项目及下载的 skill 包保留各自许可证；本仓库的许可证不会重新授权第三方文件。请同时查看 [LICENSE](../LICENSE)、[NOTICE.md](../NOTICE.md) 和 [licenses/](../licenses/)。
