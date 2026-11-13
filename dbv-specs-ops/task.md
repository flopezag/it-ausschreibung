# Project Backlog — Ausschreibungen Monitor

## Project Context

* **Goal:** Find IT-related public procurement opportunities across multiple portals, retain their history, and make new notices reviewable.
* **Current state:** Active development. The main monitor and standalone DTVP, Brandenburg, BW, Berlin, Niedersachsen, ESA STAR, and GIZ search modules are present.
* **Last technical decision:** Store default portal history JSON and `.bk` backups under `output/`; keep custom `--seen-file` paths available.
* **Validation:** Output-path portal/CLI tests: 118 passed, 1 known Brandenburg keyword-configuration failure; combined-monitor tests: 5 passed. `dbv-lint.py --changed` reported three existing return-placement errors in Brandenburg, DTVP, and GIZ plus one traceability warning.
* **Next step:** Review the known Brandenburg keyword-configuration mismatch; ESA STAR REQ-14 is complete.

## Checklist

- [x] Search IT-Ausschreibung by keyword/theme, extract and deduplicate tender URLs.
- [x] Rename the application display name to `Ausschreibungen Monitor` in project metadata, documentation, source headers, and the default scheduled-task label.
- [x] Persist the main monitor's seen URLs in `output/seen_it-ausschreibung.json` by default, retaining support for `SEEN_FILE`/`--seen-file` overrides and `.bk` backups.
- [x] Store all default portal JSON histories and their `.bk` backups in the repository's `output/` directory.
- [x] Report total, new, and already-seen IT-Ausschreibung matches on every monitor run.
- [x] Add `monitor-all` for five portals, four-field cross-source deduplication, and combined current-run CSV output (REQ-10).
- [x] Show matching source, theme, and keyword metadata on each combined CLI result.
- [x] Extract IT-Ausschreibung publication date, deadline, publication type, and public `Auftraggeber` address.
- [x] Export main monitor results to CSV when requested.
- [x] Add standalone DTVP themed/CPV search with publication-date filtering, URL deduplication, persistent history, and optional CSV output.
- [x] Add standalone Brandenburg search with publication-date filtering, URL deduplication, persistent history, and optional CSV output.
- [x] Add standalone GIZ search for AI, Cybersecurity, and Software/data terms, including inclusive date filtering, pagination, persistent history, and optional CSV output.
- [x] Add standalone Baden-Württemberg search using Brandenburg's six themes and exact keyword lists, with active-tender filtering, isolated history, date filtering, pagination, legal-framework export, and optional CSV output (REQ-11).
- [x] Add standalone Berlin announcement search using the BW workflow, independent history, theme/keyword metadata, inclusive date filtering, pagination, and optional CSV export (REQ-12).
- [x] Add standalone Niedersachsen announcement search using the BW theme set, active tender type filter, independent history, pagination, and optional CSV export (REQ-13).
- [x] Implement standalone ESA STAR search using Country `DE`, full live Technology Tree paths, transparent mappings for five screenshot/live discrepancies, per-row reporting, independent history, and optional CSV export (REQ-14).
- [x] Color ESA STAR category and technology-keyword output using the shared terminal colors (REQ-14).
- [x] Add English ChatGPT phase prompts for Spec, Plan, Build, Test, Simplify, Ship, and optional Maintain.
- [x] Complete initial project specifications, as-is architecture, and project context after owner confirmation.
- [ ] Resolve the pre-existing Brandenburg keyword-configuration test failure; latest full run: 107 passed, 1 failed.
- [x] Specify and approve REQ-10: run all five portals together, preserve independent histories, report per-source failures, and merge only exact title/date/client/link matches.
- [ ] Improve CLI help to clearly describe `search`, `monitor`, and `install-task`.
- [ ] Add focused tests for `analyse.cli.parse_args()` and `analyse.cli.main()`, including empty keywords, invalid JSON, and malformed CSV-style keyword input.
- [ ] Add runtime validation for keyword values accepted by `analyse.browser_search` and `analyse.tasks`.
- [ ] Convert project imports consistently to fully qualified package imports.
- [ ] Replace direct `print()` calls with logging in `analyse.monitor` and `analyse.cli`.
- [ ] Investigate and document the specific Pylance message that needs correction; the original backlog item did not identify its text or location.
- [ ] Define an observable email delivery status before uncommenting send-related tests.
- [ ] Resolve contributor count, author/company attribution, and application license.
- [ ] Decide a separate changelog location/process for the application; preserve `dbv-specs-ops/CHANGELOG.md`, which documents the bundled framework.
- [ ] Add an IT-Ausschreibung search mode for multiple result pages; assess incremental/date-filtered search to keep large result sets manageable.
- [ ] Consider a dry-run mode that searches without changing seen-history files.
- [ ] Consider configuration for SMTP settings and default history/export paths.
- [ ] Add Windows scheduled-task uninstall support or detect/update an existing task.
- [ ] Add portal integrations: evergabe.de, Bayern, NRW, and EU Funding & Tenders.
- [ ] Decide whether packaging (`pyproject.toml`), Docker/portable environment support, or a status endpoint is needed for the intended deployment model; a status endpoint is only applicable if the CLI becomes a resident service.
- [ ] Clarify whether the historic grouped-keyword monitor verification item is fully covered by the current attribution tests and a live run.

## Technical Debt

- Main monitor has email formatting/SMTP utilities but no exposed send outcome; tests for sending are temporarily commented.
- Combined output is current-run only; accumulated all-source history export is not part of REQ-10.
- External portal selectors and search behavior can change without notice.
- Test coverage percentage has not been measured.
- The first `dbv-lint.py` run during adoption reported existing findings; current `--changed` output still flags return-placement issues in Brandenburg, DTVP, and GIZ plus legacy traceability and parse warnings, but none in the combined monitor.
- The `check` helper now invokes the all-portal workflow in one command.
- The standalone root `TODO.md` was consolidated into this project backlog; completed historical entries are omitted because current completed work is tracked above.

---

## Context Snapshot

> **Last updated:** 2026-11-13
> **Exact point:** Default portal history JSON files and `.bk` backups have been moved to repository-root `output/`; defaults, documentation, and scheduled-task history paths now point there. Custom history paths and scheduled CSV output are unchanged.
> **Decision:** Use live ESA taxonomy paths for selectors, retain the supplied screenshot paths in each row, and report both values. No additional date cutoff.
> **Validation:** Output-path portal/CLI tests: 118 passed with 1 known Brandenburg configuration failure; combined-monitor tests: 5 passed. The full suite was not rerun.
> **Next action:** Address the existing Brandenburg configuration mismatch if requested.
