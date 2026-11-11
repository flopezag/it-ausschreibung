# ChatGPT Phase Prompts

These files adapt the phases included in `.claude/commands/` for manual use
with ChatGPT. ChatGPT does not automatically load or register prompts from
this repository folder as slash commands.

## How to use

1. Open a ChatGPT conversation with access to this repository, or attach the
   project files you need.
2. Copy and paste the contents of the prompt for the phase you want to run.
3. Add your concrete request and any relevant context to the end of your
   message.
4. The prompt tells the assistant to consult
   `dbv-specs-ops/docs/MASTER_PROMPT.md` and the project state before acting.

| Phase | Prompt |
| --- | --- |
| Specification | `spec.md` |
| Planning | `plan.md` |
| Implementation | `build.md` |
| Testing | `test.md` |
| Review and simplification | `code-simplify.md` |
| Delivery | `ship.md` |
| Maintenance (optional) | `maintain.md` |

The authoritative instructions and procedural graph remain in
`dbv-specs-ops/docs/MASTER_PROMPT.md` and
`dbv-specs-ops/docs/PROCEDURAL_GRAPH.json`. These prompts are manual ChatGPT
launchers; they do not replace or modify the Claude Code commands.
