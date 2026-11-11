# Phase: Review and Simplification

Follow the **Simplify** phase in the Spec → Plan → Build → Test → Simplify →
Ship workflow defined in `dbv-specs-ops/docs/MASTER_PROMPT.md` and the
`Simplify` node in `dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`.

Read `dbv-specs-ops/project.config.md`,
`dbv-specs-ops/docs/MASTER_PROMPT.md`,
`dbv-specs-ops/docs/SPECIFICATIONS.md`,
`dbv-specs-ops/docs/ARCHITECTURE.md`, `dbv-specs-ops/docs/REVIEW.md`,
`dbv-specs-ops/memory.md` (including `Rejection Memory`), and
`dbv-specs-ops/task.md`. Review the relevant diff and test results for the
task.

Perform the three passes defined in `docs/REVIEW.md`: Bugs, Security, and
Compliance with project standards. Report findings with evidence, severity,
and confidence. Critical findings that require behavior changes block
delivery: return to Build only for those fixes, repeat Test, then review
again.

Then simplify the code to improve clarity and reduce complexity without
adding functionality or changing behavior. Do not downgrade a finding or
repeat a rejected refactor without explaining the changed context. If Python
is present, run `python dbv-specs-ops/scripts/dbv-lint.py --changed` when
applicable. Rerun relevant tests after any refactor.

At the end, report open findings and validation status. Proceed to Ship only
if there are no unresolved Critical findings, applicable lint passes, and
tests remain green.

**Request and context for this run:** use the user's request and any additional
context provided with this prompt.
