# Origins and Inspiration

This page provides a brief overview for product users. Full independent investigations, versions, evidence levels, and tradeoff records are maintained in the separate [research repository](https://github.com/SoFarSoGoodya/mathmodel-research). Running the product does not depend on that repository.

| Source project | Main ideas adopted | Product locations |
| --- | --- | --- |
| [Danus](https://github.com/frenzymath/Danus) | Independent workers, tool boundaries by role, and writes after validation | `runtime/`, `control/` |
| [ReasFlow](https://github.com/reaslab/ReasFlow) | Specialist session identities, task handoffs, and knowledge cards | `runtime/`, `workflow.py` |
| [Station](https://github.com/dualverse-ai/station) | Parallel reasoning with a single writer for commits, branch isolation, recovery, and human pauses | `runtime/`, `control/` |
| [MathModelAgent](https://github.com/jihe520/MathModelAgent) | A staged workflow for problem reading, modeling, coding, and paper writing | `skills/`, module documentation |
| [MathMN](https://github.com/ShuoSachiko/MathMN) | Evidence ledgers, route mapping, literature search, and traceable handoffs | `skills/evidence/`, `skills/exploration/` |
| [MathModel-Skill](https://github.com/yushui2022/MathModel-Skill) | Structured problem statements, candidate comparison, recomputation and robustness checks, and paper publication gates | `skills/`, `execution/`, `publication/`, `templates/` |

These projects provide references for mechanisms. This product implements its own interfaces, does not require any upstream framework as its foundation, and does not treat a local evaluator as proof of mathematical correctness. Upstream code and skills retain their respective licenses; the product license does not relicense third-party files. See [LICENSE](../LICENSE), [NOTICE.md](../NOTICE.md), and [licenses/](../licenses/).
