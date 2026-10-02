# User guide

Open the `mathmodel-weave` project in one Codex conversation and describe what you want to do. The assistant reads repository instructions, operates the existing CLI, explains saved status and asks for real choices. You do not need to memorize commands or manually coordinate several conversations. This is a file-based workflow, without a resident chat service or automatic file watcher.

Two roles are distinct: your Codex conversation is the **operator assistant**; managed modeling agents perform bounded exploration, review and analysis. The case stores their tasks, permissions and outputs. A new operator conversation does not automatically know previous research chat, and cannot recreate missing provider conversations.

## Begin with one short prompt

> Read AGENTS.md and docs/guide.md. Use existing doctor and mmagent commands to inspect the environment and the case, explain what is missing, and carry out the work in this project. Ask me for login/admin actions, tier choice, formal route/result choices, truthful AI disclosure and final package approval. Do not invent my answers. Keep personal cases outside the release repository.

Linux/WSL and an available Codex account or user-configured compatible provider are required. Login, credentials and provider/MCP configuration remain in your trusted local environment; never send secrets into chat or answer files. The assistant can run deterministic doctor checks and explain missing tools, but login, administrator actions and installations can require you. Doctor is not a live-provider/MCP verification. Environment details are in [setup](setup.md).

If your account actually provides Luna, it may be used with medium for lightweight setup/status help, but is optional; the assistant must not assume availability or silently replace model names. Choose a suitable model for complex modeling. Historical names in the case template need checking against your actual configured account.

## Start a new problem

Keep the original PDF/XLSX files in a readable folder that you manage, ideally one per problem. Tell the assistant their paths, the goal, time/compute resources, restrictions and initial ideas. It creates a separate case and imports working copies while retaining originals. A synthetic example is not your real case.

Review the corrected problem text after intake, especially page numbers, units, formulas, table headings, variable meaning and constraints. Workbook sheets are inspected programmatically; you do not need to review every row. PDF intake reads embedded text only; scanned PDFs need external OCR/MinerU preprocessing. XLSX formulas are not calculated. There is no integrated MinerU SDK.

If you edit a problem or answer Markdown file yourself, say **“Updated; read the latest content.”** The assistant then reads and records it; it must not claim to have watched the file automatically.

Before managed research, explicitly choose a tier:

- **fast:** a quick direction check when time is short or for an initial exploration.
- **standard:** a reasonable recommendation for a normal full workflow, requiring your explicit agreement.
- **full:** harder derivations, more exploration or important cross-checks, usually taking longer.

These tiers bind human authorization and selected profile settings; they do not guarantee a fixed route count or hard token/cost/deadline cap. The approved object includes the problem hash and profile model/effort. Changed problem text or model/effort requires a new real decision through the existing flow. Ordinary experiments, recomputation and code iteration may continue within the approved scope; important scope, permission or budget changes need confirmation.

Your idea can remain an independent candidate or be challenged. Agents should explain weaknesses and compare alternatives; they must not merge routes merely to agree with you. You may choose one, request a new fusion, or reject all. A fusion starts as another candidate and needs its own review.

## Decisions only you can make

| When | What the assistant presents | Your action |
| --- | --- | --- |
| New case | Intake summary, corrected problem, tier choices | Confirm interpretation, resources/constraints and tier |
| Real ambiguity | A question and plausible interpretations | Explain your interpretation or pause |
| Formal route/result choice | Independent options, tradeoffs, fixed comparisons/results | Choose, request a fusion, or reject |
| Important permission/budget change | Proposed change, reason and effect | Explicitly approve or reject |
| Draft disclosure | Actual AI adoption, human edits and verification | Confirm only truthful facts |
| Final submission | Complete paper, AI-use details and exact staged package | Review and approve or reject that complete version |

Managed questions are saved in `human/AI_QUESTIONS.md`, your words in `human/HUMAN_ANSWERS.md`, and exact decisions in the same case's control records. You can reply in the Codex conversation and say “Record my exact words for the current question,” or edit the answer file and notify the assistant to reread it. For example:

> For the current route-choice question, I choose B because it fits the time limit. Keep A for sensitivity analysis; I do not approve another fusion.

The operator binds the real answer to the displayed question through current CLI commands. This is not an mmagent natural-language interface; workers see only saved, bound answers. Without a real answer the operator must wait. It must not fill in a choice, infer approval, or substitute a synthetic fixture. Waiting needs no repeated model calls.

## Continue later or after replacing a system

Reopen `mathmodel-weave` in one new Codex conversation. Give the case path/name and this prompt:

> Read AGENTS.md and docs/guide.md. Inspect my existing case, saved status and outputs. Tell me where it stopped, retain existing tasks/attempts/evidence and valid decisions, and continue within authorization. Distinguish missing operator chat from a managed provider session. If provider history is unavailable, explain how to continue selected saved work in a new task/session rather than pretending the old session was recovered. Ask for any missing real choice.

A new **operator conversation** can use repository Markdown and case files without its previous chat. A managed agent's `resume` is different: it needs the saved provider session to remain available. SQLite stores session IDs/attempt facts, not the complete provider conversation. Logs and outputs preserve evidence, but are not guaranteed to contain all prior chat.

After system replacement, Git restores product development, while case recovery needs the complete separately backed-up directory including hidden runtime state, inputs, workspaces, logs, artifacts, human records and paper files. Runtime paths are absolute: restore the case at its original absolute location. No rebase or in-place session replacement CLI exists. If history is lost, retain the old task/attempts/outputs and explicitly continue selected material in a new task with a distinct ID and new session. If the original case path cannot be restored, preserve it as evidence and initialize/import into a new case; decisions and dependencies do not automatically transfer. See [setup](setup.md) and [developer handoff](dev.md) for the precise boundaries.

For a fault, describe the symptom: “The run was interrupted; inspect case status and logs, explain the cause, and ask before login/admin actions or changing scope.” Authentication, rate limits, transport failure and pause must not be hidden by repeated duplicate task creation. Where original history remains available, recovery uses the original session. Never hand-edit SQLite to conceal unavailable history.

## Review and export

Ask the assistant for the exact paths of the electronic paper, AI-use details and page-review material. Review the actual files; compilation alone is not visual review, and a reviewed package is not human approval.

Final approval binds the complete fixed package shown then. If any file changes afterward, create and review a new staged package and approve it again. A verified export goes to the new destination you specify; have the assistant report the actual path before copying submission files.

The bundled synthetic allocation example demonstrates greedy/exhaustive execution and publication. It is not competition output and contains no real participant route, disclosure or final approval. A real case needs the current problem/data, applicable current competition/regional rules, real decisions and truthful AI-use facts. Those rules must be obtained and frozen per case.

Use [setup](setup.md) and [CLI reference](cli.md) for details, [status](status.md) for actual implementation/validation limits, and the root [README](../README.en.md) for product structure.
