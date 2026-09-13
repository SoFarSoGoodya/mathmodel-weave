# MathModel Weave: Mathematical Modeling Multi-Agent Workbench

This is the standalone `mathmodel-weave` product repository. Architecture research, source evidence, and fusion decisions live in the independent [research repository](https://github.com/SoFarSoGoodya/mathmodel-research); that repository is not a runtime dependency. Replace `SoFarSoGoodya` with your GitHub account or organization when publishing.

## What makes it different

The product combines two layers:

1. **Modeling skills and process contracts** define how problem reading, data intake, literature evidence, candidate routes, experiments, review, paper writing, and AI-use disclosure are performed and handed off.
2. **A real multi-agent runtime** runs independent, permission-scoped tasks with session identity, persistent state, parallel exploration, and controlled commits. Multiple agents are managed tasks with traceable boundaries, not prompt variants in one chat.

Skill-only math tools usually lack a recoverable collaboration runtime. Generic AI-for-math runtimes usually lack competition-oriented problem correction, route comparison, evidence freezing, and publication gates. This project combines both in one case protocol while preserving open-ended exploration and explicit human decisions. The six baselines are [Danus](https://github.com/frenzymath/Danus), [ReasFlow](https://github.com/reaslab/ReasFlow), [Station](https://github.com/dualverse-ai/station), [MathModelAgent](https://github.com/jihe520/MathModelAgent), [MathMN](https://github.com/ShuoSachiko/MathMN), and [MathModel-Skill](https://github.com/yushui2022/MathModel-Skill).

## Six modules

| Layer | Module | Responsibility | Main artifacts |
| --- | --- | --- | --- |
| Runtime and governance | `runtime` | Launch managed tasks, persist process/session state, and perform bounded recovery | task state, events, attempts |
| Runtime and governance | `control` | Record permissions, research tier, human questions, and decisions | decisions, permissions, approvals |
| Skill and process | `evidence` | Ingest PDF/XLSX, correct the problem statement, manage evidence, and freeze cited versions | source text, registry, freeze |
| Skill and process | `exploration` | Produce independent candidate routes and comparison contracts | candidates, comparisons |
| Skill and process | `execution` | Run declared code and inputs, recording metrics, failures, and checks | manifests, metrics, checks |
| Skill and process | `publication` | Assemble figures, TeX, references, AI-use details, and exact release bundles | paper, figures, release bundle |

The runtime layer answers who runs with which permissions and how state resumes. The skill layer answers how each modeling step is performed and accepted. They exchange case-relative files, manifests, checks, and human decisions.

```text
problem/data -> evidence -> exploration -> managed runtime
                                      -> execution/checks
                                      -> publication -> human approval -> release
                         control records permissions and decisions throughout
```

## Quick start

You need Linux or WSL, Python, `uv`, and XeLaTeX for paper output. If you are new to this workflow, you do not need to learn the CLI first:

1. Open Codex in this repository and start one main conversation. Luna/medium is recommended for everyday guidance.
2. Send this short prompt:

   > Read `AGENTS.md`, `docs/guide.md`, `docs/setup.md`, and `docs/status.md` first. Act as the coordinator for this project: check my environment and tell me what is missing, guide me through preparing the problem, then start and manage the background agents, track their state, and ask me only for decisions. I will work through the conversation and will not operate the underlying code or CLI myself.

3. Answer the coordinator's questions, provide the problem files, choose a research tier, and confirm the problem statement. The coordinator continues the managed work and asks when a human decision is required.

Developers who prefer the CLI can run:

```bash
uv sync --locked
uv run mmagent doctor
uv run mmagent init CASE
```

See [setup](docs/setup.md) and the [CLI reference](docs/cli.md) for configuration, optional MinerU/OCR preprocessing, and troubleshooting. Built-in PDF/XLSX intake uses `pypdf` and `openpyxl`; this release has no MinerU SDK adapter.

## Human collaboration

Use the Codex main conversation as the single entry point. You describe goals, answer questions, and make decisions. The coordinator checks configuration, initializes cases, starts and manages background agents, retries or resumes interrupted work according to project rules, reads current state, and explains decisions in plain language. You do not need to remember agent names or repeatedly run CLI commands.

At the start of a case, send the short prompt above. Then confirm the problem statement, choose a research tier, and approve or reject candidate routes. The coordinator handles experiments, state persistence, and recovery; you confirm the final route, results, AI-use disclosure, and release package. To continue on another device or after a disconnected chat, reopen the repository and ask the coordinator to read `AGENTS.md`, `docs/guide.md`, and the current case state.

If you edit a case Markdown file, tell the coordinator: “I updated the file; please read the latest content.” Keep credentials and model settings in Codex configuration, never in the repository or case files.

## Documentation

- [User guide](docs/guide.md)
- [Setup](docs/setup.md) · [CLI](docs/cli.md)
- [Design](docs/design.md) · [Developer handoff](docs/dev.md)
- [Status](docs/status.md) · [Origins](docs/origins.md)
- [Module notes](docs/modules/)
- [Chinese topic docs](docs/zh/)

`skills/` contains process contracts, `mathmodel_agent/` contains runtime code, `templates/` contains publication templates, and `examples/` contains synthetic demonstrations. Research records, upstream checkouts, and downloaded skill packages are not required to run or develop this repository.

## Sources and license

[Danus](https://github.com/frenzymath/Danus), [ReasFlow](https://github.com/reaslab/ReasFlow), [Station](https://github.com/dualverse-ai/station), [MathModelAgent](https://github.com/jihe520/MathModelAgent), [MathMN](https://github.com/ShuoSachiko/MathMN), and [MathModel-Skill](https://github.com/yushui2022/MathModel-Skill) are independent projects that this product respects and studies. Their mechanisms informed role coordination, recovery, modeling process, evidence handling, and publication constraints; this repository defines its own interfaces and does not silently copy or inherit upstream licenses. See [docs/origins.md](docs/origins.md), [LICENSE](LICENSE), [NOTICE.md](NOTICE.md), and [licenses/](licenses/).

Examples use synthetic data and are not competition submissions.
