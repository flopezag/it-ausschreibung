# Phase: Implementation

Follow the **Build** phase in the Spec → Plan → Build → Test → Simplify →
Ship workflow defined in `dbv-specs-ops/docs/MASTER_PROMPT.md` and the
`Build` node in `dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`.

Before modifying code, read `dbv-specs-ops/project.config.md`,
`dbv-specs-ops/docs/MASTER_PROMPT.md`,
`dbv-specs-ops/docs/SPECIFICATIONS.md`,
`dbv-specs-ops/docs/ARCHITECTURE.md`, `dbv-specs-ops/memory.md` (including
`Rejection Memory`), and `dbv-specs-ops/task.md`.

An approved plan with clear steps must exist. If the specification or plan is
missing, do not reject the request: complete the Spec and Plan phases first,
resolve critical questions, and get explicit plan approval before
implementation.

Implement incrementally, one slice at a time, following the technical
decisions and standards in the master workflow. Keep changes within the
approved scope; add `@spec REQ-NN` to new code implementing identified
requirements. Update `dbv-specs-ops/CHANGELOG.md` under `[Unreleased]` when
appropriate, and record any necessary deviation from `ARCHITECTURE.md` in
`memory.md`.

Do not mark work complete without successful tests. Do not weaken assertions
to hide failures; if a test fails, address the cause in the code and record
any attempted and rejected approach in `Rejection Memory`.

When implementation is complete, summarize affected files and requirements,
what remains to validate, and the transition to Test.

**Request and context for this run:** use the user's request and any additional
context provided with this prompt.
