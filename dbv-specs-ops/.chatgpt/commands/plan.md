# Phase: Planning

Follow the **Plan** phase in the Spec → Plan → Build → Test → Simplify → Ship
workflow defined in `dbv-specs-ops/docs/MASTER_PROMPT.md` and the `Plan` node
in `dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`.

Read `dbv-specs-ops/project.config.md`,
`dbv-specs-ops/docs/MASTER_PROMPT.md`,
`dbv-specs-ops/docs/SPECIFICATIONS.md`,
`dbv-specs-ops/docs/ARCHITECTURE.md`, `dbv-specs-ops/memory.md` (including
`Rejection Memory`), and `dbv-specs-ops/task.md`.

If the specification does not contain relevant, verifiable requirements for
the request, complete the Spec phase first in the same response; do not reject
the request solely because preparation is missing. Assign requirement IDs and
resolve critical questions before planning.

Prepare a plan with the adversarial architect review required by the master
workflow: cite repository/specification evidence, assess confidence for edge
cases, security, and concurrency, and present an adversarial review. Break the
work into small steps that reference their `REQ-NN`/`RNF-NN` IDs. For complex
work, create or update `dbv-specs-ops/implementation_plan.md` with the
required frontmatter; for simple work, record the plan in
`dbv-specs-ops/task.md`.

Do not use an approach that is still active in `Rejection Memory` without
explaining what evidence or changed context makes it applicable now. Do not
proceed with `low` confidence without human validation. If the specification
is ambiguous or the user rejects the plan, update only the affected
requirements and review it again.

Do not implement until the user explicitly approves the plan. Present the
plan, identify open decisions, and ask for that approval.

**Request and context for this run:** use the user's request and any additional
context provided with this prompt.
