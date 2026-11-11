# Phase: Specification

Follow the **Spec** phase in the Spec → Plan → Build → Test → Simplify → Ship
workflow defined in `dbv-specs-ops/docs/MASTER_PROMPT.md` and the `Spec` node
in `dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`.

Before proposing changes, read:

- `dbv-specs-ops/project.config.md`
- `dbv-specs-ops/docs/MASTER_PROMPT.md`
- `dbv-specs-ops/docs/SPECIFICATIONS.md`
- `dbv-specs-ops/memory.md`, including `Rejection Memory`
- `dbv-specs-ops/task.md`

Clarify which existing requirement is changing or what new requirement is
needed. Do not invent behavior when the request is ambiguous; ask the user.
Assign the next available unique ID (`REQ-NN` or `RNF-NN`) to every new or
modified requirement and define verifiable acceptance criteria. If the project
has a user interface, also consider relevant design requirements.

Do not write or modify code in this phase. Do not renumber or reuse existing
IDs. Do not proceed to planning while critical questions or placeholders
prevent a clear scope.

Once the specification is clear, present the updated requirements and
acceptance criteria, and identify Plan as the next phase. Wait for approval
when required by the master workflow.

**Request and context for this run:** use the user's request and any additional
context provided with this prompt.
