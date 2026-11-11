# Phase: Delivery

Follow the **Ship** phase in the Spec → Plan → Build → Test → Simplify → Ship
workflow defined in `dbv-specs-ops/docs/MASTER_PROMPT.md` and the `Ship` node
in `dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`.

Read `dbv-specs-ops/project.config.md`,
`dbv-specs-ops/docs/MASTER_PROMPT.md`,
`dbv-specs-ops/docs/SPECIFICATIONS.md`,
`dbv-specs-ops/docs/ARCHITECTURE.md`, `dbv-specs-ops/memory.md` (including
`Rejection Memory`), `dbv-specs-ops/task.md`, and
`dbv-specs-ops/CHANGELOG.md`. Verify that Test and Simplify are complete,
there are no unresolved Critical findings, and the documentation reflects
the code. If any gate fails, stop and identify whether Simplify must be
revisited.

Present a proposed memory update before editing it. Update the root README to
reflect the delivered product, synchronize derived documentation where
applicable, complete `dbv-specs-ops/walkthrough.md`, and publish the
`[Unreleased]` changelog section with the current date.

Ask the user which version level applies: Patch (bug fixes only), Minor
(backward-compatible functionality), Major (breaking change), or no version
change. Update the changelog and comparison links accordingly. If the
repository uses Git, propose a Conventional Commit message and the appropriate
tag command; never run `git push`. For GitHub Releases, follow the options and
confirmation requirements in the master workflow.

Update `dbv-specs-ops/task.md` with the final state and a Context Snapshot
that allows work to resume. Summarize what was delivered, tests run, version
decisions, and any actions still requiring user approval.

**Request and context for this run:** use the user's request and any additional
context provided with this prompt.
