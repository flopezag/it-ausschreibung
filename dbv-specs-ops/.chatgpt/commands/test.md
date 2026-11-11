# Phase: Testing

Follow the **Test** phase in the Spec → Plan → Build → Test → Simplify → Ship
workflow defined in `dbv-specs-ops/docs/MASTER_PROMPT.md` and the `Test` node
in `dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`.

Read `dbv-specs-ops/project.config.md`,
`dbv-specs-ops/docs/MASTER_PROMPT.md`,
`dbv-specs-ops/docs/SPECIFICATIONS.md`,
`dbv-specs-ops/docs/ARCHITECTURE.md`, `dbv-specs-ops/memory.md` (including
`Rejection Memory`), and `dbv-specs-ops/task.md`. Identify implemented
requirements with IDs and the tests that cover them.

Write and run deterministic tests for the affected requirements; tag each new
or updated test with `@spec REQ-NN` where applicable. If the project has
nondeterministic AI functionality, add Evals as described by the master
workflow. Run the smallest relevant validation and expand it if the results
reveal problems. Record fixed bugs in `dbv-specs-ops/CHANGELOG.md`.

Do not claim success if tests fail, requirements have no test coverage, or
required validations were not run. Do not delete or weaken an assertion to
make the suite pass. If a test fails, find the cause: fix the code in Build
and rerun the tests. If the failure disproves an assumption, update the
relevant lesson or specification.

When all tests pass and every requirement is covered, report the results and
continue to Simplify according to the phase graph.

**Request and context for this run:** use the user's request and any additional
context provided with this prompt.
