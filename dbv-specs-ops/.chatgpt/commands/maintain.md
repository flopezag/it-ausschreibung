# Phase: Maintenance (Optional)

Follow **Maintain** in `dbv-specs-ops/docs/MAINTAIN.md` and the `Maintain`
node in `dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`. This phase is enabled only
if `dbv-specs-ops/project.config.md` explicitly says
`Maintain (Phase 7) → Enabled: yes`. If it is not enabled, do not run this
phase.

Read `dbv-specs-ops/project.config.md`,
`dbv-specs-ops/docs/MASTER_PROMPT.md`,
`dbv-specs-ops/docs/SPECIFICATIONS.md`, `dbv-specs-ops/memory.md` (including
`Rejection Memory`), `dbv-specs-ops/task.md`, and the supplied incident/log.
Diagnose the issue read-only; do not change code, deploy, or merge. For long
logs, preserve and analyze the end, where the failure is likely to appear.

Based on evidence, document the finding as a new
`## [Automatically detected] <date>` entry in
`dbv-specs-ops/docs/SPECIFICATIONS.md`, with Problem, Objective, and
Criteria. Do not assign a requirement ID yet or start implementing a fix. The
finding returns to Plan only if a human decides to address it.

Report the likely cause, evidence, uncertainties, and the entry added.

**Incident or log to investigate:** use the content provided by the user with
this prompt.
