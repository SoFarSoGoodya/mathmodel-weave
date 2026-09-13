# 来源与借鉴

本页是产品侧的简要说明。完整的独立调查、版本、证据等级和取舍记录位于独立的[研究仓库](https://github.com/<your-org>/mathmodel-research)，产品运行不依赖研究仓库。

| 来源体系 | 主要借鉴 | 产品位置 |
| --- | --- | --- |
| [Danus](https://github.com/frenzymath/Danus) | 独立 worker、角色工具边界、验证后写入 | `runtime/`、`control/` |
| [ReasFlow](https://github.com/reaslab/ReasFlow) | specialist 会话身份、任务交接和知识卡片 | `runtime/`、`workflow.py` |
| [Station](https://github.com/dualverse-ai/station) | 并行推理与单写提交、分支隔离、恢复和人工暂停 | `runtime/`、`control/` |
| [MathModelAgent](https://github.com/jihe520/MathModelAgent) | 分阶段读题、建模、代码和论文流程 | `skills/`、模块说明 |
| [MathMN](https://github.com/ShuoSachiko/MathMN) | 证据账本、路线映射、文献检索和可追踪交接 | `skills/evidence/`、`skills/exploration/` |
| [MathModel-Skill](https://github.com/yushui2022/MathModel-Skill) | 结构化题面、候选比较、复算/稳健性检查和论文发布门 | `skills/`、`execution/`、`publication/`、`templates/` |

这些项目提供机制参考，本产品重新实现自己的接口，不把任何一个上游框架作为必需底座，也不把局部 evaluator 当作数学正确性证明。上游代码和 skill 保留各自许可证；产品许可证不会重新授权第三方文件。详见 [LICENSE](../../LICENSE)、[NOTICE.md](../../NOTICE.md) 和 [licenses/](../../licenses/)。
