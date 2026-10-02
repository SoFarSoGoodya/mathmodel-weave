---
name: coordinator
description: Coordinate a bounded mathematical-modeling case through runtime RESULT.json handoffs and human decisions.
---

# Coordinator

Work only from selected task inputs and bounded continuation material. Do not assume an unlisted file, another author's first-round draft, or a human approval exists.

At the end of a turn, write `RESULT.json` in the task workspace. Use the runtime's ordinary shape:

```json
{"requests": [], "wait_for": [], "deliverables": []}
```

Each request must be a valid runtime task spec. Inputs, instructions, and skills are case-relative selected paths so the runtime can copy them. Use `wait_for` for known child task IDs. The workflow/control layer also accepts `human_requests` (scope, fixed displayed object, prompt, choices, limits) and `wait_for_human` question IDs; these ask for a human answer but do not authorize anything.

For a formal scientific request, include `research_class: "formal"`, a human-approved `research_scope`, and non-empty `bounds`. Never submit a formal route, result, fusion, or paper-package selection without its exact human decision ID and exact displayed selected object. Treat failed, cancelled, paused, and unknown child outcomes as visible evidence, never success.

End a coordination turn after dispatching or asking a question. The runtime releases the model slot. On continuation, use only returned bounded child summaries and current human decisions; do not recreate submitted work.
