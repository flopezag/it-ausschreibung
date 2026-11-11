# Project Memory — IT-Ausschreibung Monitor

## Active Context

- **Development state:** Python CLI that searches public procurement portals. The main IT-Ausschreibung search and standalone DTVP, Brandenburg, BW, and GIZ modules are present.
- **Immediate focus:** REQ-10 combined five-portal monitoring is implemented. Email delivery status is a separate known gap.
- **Validation:** The latest full suite run had 80 passing tests and one pre-existing Brandenburg keyword-configuration failure. `dbv-lint.py --changed` reports existing return-placement issues in Brandenburg, DTVP, and GIZ, plus legacy traceability and parse warnings; it reports no new errors in the combined monitor.
- **Owner-confirmed adoption baseline:** Python/Playwright/Chromium/pytest, local JSON history, optional CSV output, English SDD documentation, no integrated desktop AI, and no agent-facing web API.
- **Still unspecified:** Contributor count, author/company attribution, and the application's license.

## Technical Decision Log

- **2026-10-23 — Separate portal modules [INFERRED]:** Keep portal-specific selectors, parsing, date filtering, and history in independent modules because each procurement portal has a distinct search interface.
- **2026-10-23 — Local history [INFERRED]:** Use per-portal JSON files and optional CSV exports; the project has no database or hosted backend.
- **2026-10-23 — Browser automation [INFERRED]:** Use Playwright/Chromium for the interactive procurement portals.
- **2026-10-23 — Preserve framework changelog [CONFIRMED by repository evidence]:** `dbv-specs-ops/CHANGELOG.md` identifies itself as the changelog for dbv-specs-ops. Do not add application release entries there. The project owner must decide the product changelog location.
- **2026-11-11 — Combined portal result identity [CONFIRMED]:** The combined CLI searches all five configured portals and merges results only when normalized title, publication date, client, and URL match; source names and keyword/theme metadata remain visible. For IT-Ausschreibung, use the public `Auftraggeber` address as client data when the organization name is unavailable.

## Lessons Learned

- The application has email-body formatting and SMTP utility code, but current monitor behavior does not provide a result indicating whether an email was sent. The send-related tests remain commented until the observable status is designed.
- Portal keyword full-text search can be noisy. A title match alone is not proof that the tender's full scope is relevant.
- The BW results page contains a hidden responsive detail table as well as the visible listing. Extraction must scope to `table.tableHorizontalHeader` so hidden detail rows are not mistaken for notices.
- The local repository may contain unrelated uncommitted changes. Inspect and preserve them; do not revert without explicit direction.

## 🚫 Rejection Memory

- No implementation approaches have been tested and rejected for this application yet.

## Relationship Map

- `analyse.py` → `analyse.cli` → `analyse.browser_search` for the main search command.
- `analyse.cli` → `analyse.monitor` → `analyse.storage` for new-tender detection and history persistence.
- `analyse.monitor` formats email content; `analyse.mailer` provides SMTP sending but delivery status is not exposed by the monitor.
- `analyse.cli` → `analyse.combined_monitor` → each portal's structured search/history functions for the one-command all-portal workflow.
- `analyse.tasks` creates a Windows Task Scheduler invocation of the main CLI.
- `analyse.dtvp_analysis`, `analyse.brandenburg_analysis`, `analyse.bw_analysis`, and `analyse.giz_analysis` are independent portal-specific searchers, with local history and optional CSV output.
- `tests/` contains unit tests for the main monitor and each standalone portal module.
