# Project Memory — Ausschreibungen Monitor

## Active Context

- **Development state:** Python CLI that searches public procurement portals. The main IT-Ausschreibung search and standalone DTVP, Brandenburg, BW, Berlin, Niedersachsen, ESA STAR, and GIZ modules are present.
- **Immediate focus:** ESA STAR REQ-14 is implemented and validated; email delivery status is a separate known gap.
- **Validation:** ESA STAR focused tests passed (15); a live search completed for all 30 unique paths and reported 0 results for each of the 32 rows. The full suite has 122 passing tests and the same pre-existing Brandenburg keyword-configuration failure. `dbv-lint.py --changed` reports no errors.
- **Owner-confirmed adoption baseline:** Python/Playwright/Chromium/pytest, local JSON history, optional CSV output, English SDD documentation, no integrated desktop AI, and no agent-facing web API.
- **Still unspecified:** Contributor count, author/company attribution, and the application's license.

## Technical Decision Log

- **2026-10-23 — Separate portal modules [INFERRED]:** Keep portal-specific selectors, parsing, date filtering, and history in independent modules because each procurement portal has a distinct search interface.
- **2026-10-23 — Local history [INFERRED]:** Use per-portal JSON files and optional CSV exports; the project has no database or hosted backend.
- **2026-10-23 — Browser automation [INFERRED]:** Use Playwright/Chromium for the interactive procurement portals.
- **2026-10-23 — Preserve framework changelog [CONFIRMED by repository evidence]:** `dbv-specs-ops/CHANGELOG.md` identifies itself as the changelog for dbv-specs-ops. Do not add application release entries there. The project owner must decide the product changelog location.
- **2026-11-11 — Combined portal result identity [CONFIRMED]:** The combined CLI searches all five configured portals and merges results only when normalized title, publication date, client, and URL match; source names and keyword/theme metadata remain visible. For IT-Ausschreibung, use the public `Auftraggeber` address as client data when the organization name is unavailable.
- **2026-11-13 — Berlin announcement fields [CONFIRMED]:** The Berlin listing exposes an execution location rather than a named contracting authority in its cards; retain it as `location`. Keep the Berlin module and `seen_berlin.json` independent and do not add it to the five-source `monitor-all` flow.
- **2026-11-13 — Niedersachsen tender scope [CONFIRMED]:** Select the `Tender` publication category and exclude `ExAnte`/`ExPost`. Result rows can display `Ausschreibung` or `TNW`; retain those displayed values and the separate contracting rule. Keep history in `seen_niedersachsen.json` and do not add it to `monitor-all`.
- **2026-11-13 — ESA STAR path reconciliation [CONFIRMED]:** Use the live ESA Technology Keywords tree as the selector when it differs from the supplied screenshot. Preserve and report both the original row path and the exact selected live path; keep all 32 row/category associations and query each unique live path once. Do not impose an additional date cutoff.
- **2026-11-13 — Product name [CONFIRMED]:** Use `Ausschreibungen Monitor` as the application display name and default Windows scheduled-task name. Preserve portal names, module names, data filenames, and the repository path.

## Lessons Learned

- The application has email-body formatting and SMTP utility code, but current monitor behavior does not provide a result indicating whether an email was sent. The send-related tests remain commented until the observable status is designed.
- Portal keyword full-text search can be noisy. A title match alone is not proof that the tender's full scope is relevant.
- The BW results page contains a hidden responsive detail table as well as the visible listing. Extraction must scope to `table.tableHorizontalHeader` so hidden detail rows are not mistaken for notices.
- Berlin's listing cards expose `Online seit`, procedure, execution location, deadline, and an external `data-href` on the details button; pagination uses a `start` query parameter.
- Niedersachsen's active `Tender` filter returns both rows labeled `Ausschreibung` and `TNW`. Pagination submits through `.browseForward` to a separate results endpoint while preserving form state; wait for its page counter to advance.
- The local repository may contain unrelated uncommitted changes. Inspect and preserve them; do not revert without explicit direction.

## 🚫 Rejection Memory

- No implementation approaches have been tested and rejected for this application yet.

## Relationship Map

- `analyse.py` → `analyse.cli` → `analyse.browser_search` for the main search command.
- `analyse.cli` → `analyse.monitor` → `analyse.storage` for new-tender detection and history persistence.
- `analyse.monitor` formats email content; `analyse.mailer` provides SMTP sending but delivery status is not exposed by the monitor.
- `analyse.cli` → `analyse.combined_monitor` → each portal's structured search/history functions for the one-command all-portal workflow.
- `analyse.tasks` creates a Windows Task Scheduler invocation of the main CLI.
- `analyse.dtvp_analysis`, `analyse.brandenburg_analysis`, `analyse.bw_analysis`, `analyse.berlin_analysis`, `analyse.niedersachsen_analysis`, and `analyse.giz_analysis` are independent portal-specific searchers, with local history and optional CSV output.
- `tests/` contains unit tests for the main monitor and each standalone portal module.
