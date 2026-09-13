# Human Control And Exploration

D3 is file-driven. It adds no scheduler or task database: `State` remains the source of task status, while `human/control.json` retains only answer cursors, fixed displayed objects, decisions, and adoption facts. `human/coordinator.json` retains request fingerprints so polling the same completed coordinator turn cannot dispatch duplicate work.

## Minimal Path

From `product/`, create a case and let the human edit the problem text directly:

```bash
UV_CACHE_DIR=/tmp/mmagent-uv-cache uv run mmagent init /tmp/mm-case
```

Put the confirmed problem statement in `/tmp/mm-case/problem/question.md`. Create the mode/scope question through `mathmodel_agent.control.ask_human`, displaying the exact problem reference and setting `limits={"bounds": {...}}`; the human answers in `/tmp/mm-case/human/HUMAN_ANSWERS.md` with an `A-###` heading and `For: Q-###`. A D6 CLI subcommand should call `capture_human_answer`, `consume_answers`, and `record_human_decision` after the human explicitly names one displayed choice. D3 intentionally does not add that CLI wiring.

The equivalent current Python hook is:

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

An answer is consumed once by byte cursor. A blank trailing answer remains unconsumed until it has text. A late answer is bound to its original fixed displayed object; it cannot approve a replacement. Test fixtures use `append_fixture_answer` and remain `simulated`, never real competition approval. Agent task output cannot create a human decision.

Use `write_candidate`, `write_variant`, `create_comparison_contract`, and `write_comparison_pack` to create readable material under `candidates/` and `comparisons/`. The contract has data/split, metrics with units, constraints, baseline, budget, failure denominator, and stopping condition before D4 formal execution. A fusion is another Candidate with parents and starts unreviewed.

## Coordinator Hook

Submit the coordinator as a normal D1 main agent task, then run the D1 supervisor and poll:

```python
from mathmodel_agent.workflow import Coordinator, submit_coordinator

task_id = submit_coordinator("/tmp/mm-case", task_id="coordinator-1", prompt="Explore the confirmed case.", inputs=["problem/question.md"])
# D6 wires the normal `mmagent serve /tmp/mm-case` command.
result = Coordinator("/tmp/mm-case").poll(task_id)
```

A completed coordinator turn can place `requests`, `wait_for`, and `deliverables` in D1's `RESULT.json` shape, plus D3's optional `human_requests` and `wait_for_human`. D3 submits only valid case-relative requests. Formal scientific requests require `research_class: "formal"`, `research_scope`, non-empty `bounds`, and a matching approved human scope. Formal selection of a route, result, fusion, or paper package also requires an exact human decision bound to the same selected object. Routine internal iterations do not need that extra gate.

`Coordinator.poll()` waits while child tasks or explicit human questions are unresolved. It does not keep the coordinator process running. Once they resolve, it calls `State.resume(task_id, followup=...)` with bounded result material. Failed, cancelled, and unknown children remain visible in that continuation and are not promoted to successful evidence. D6 should expose this poll/resume cycle as its domain CLI command.

During draft review, ask an `ai_disclosure` question displaying the exact task ID,
adoption, modification, and human-verification facts. After the human confirms those facts,
`record_ai_adoption` may record them before the PDF package exists. Build and stage the
completed package, then ask a separate `paper_package` question displaying its exact
ArtifactRef. Any changed package needs a new question and decision.
