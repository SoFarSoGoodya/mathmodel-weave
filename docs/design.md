# Design

The deterministic control plane owns case state, task identity, permissions, human decisions, evidence references, run manifests, and immutable publication bundles. Managed workers propose routes and artifacts but cannot create a human decision or silently replace a selected object.

Data flow: intake -> corrected problem/evidence -> candidate routes and comparison contracts -> runtime attempts -> observations/checks -> selected result -> paper and AI-use details -> exact package approval/export.

Modules are runtime (process supervision), control (human gates), evidence (ingest/freeze), exploration (candidates/comparisons), execution (declared commands/metrics), and publication (figures, TeX, checks, package). See `docs/modules/`.
