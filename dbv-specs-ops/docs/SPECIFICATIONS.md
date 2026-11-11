# Product Specifications: IT-Ausschreibung Monitor

> **Phase:** Spec
> **Status:** Initial adoption baseline; requirements below are inferred from the existing code and documentation unless marked confirmed.
> **Last reviewed:** 2026-10-23

## 1. Context and Goals

- **Problem [CONFIRMED]:** Users need to find IT-related public procurement opportunities spread across multiple tender portals.
- **Goal [CONFIRMED]:** Search configured portals, deduplicate notices, and retain history so newly discovered tenders can be identified.
- **Primary user [INFERRED]:** A procurement opportunity monitor operator who runs the Python CLI.

## 2. Functional Requirements

- [x] **REQ-01 [INFERRED] — Search IT-Ausschreibung:** Search the configured keyword groups using the public IT-Ausschreibung search page and extract valid tender links. Acceptance: matching tender URLs are returned without duplicate URLs within a search.
- [x] **REQ-02 [INFERRED] — Monitor and history:** Compare discovered URLs with persistent JSON history, preserve existing history across runs, support per-keyword/theme buckets and a global view, and back up changed history to `.bk`. Acceptance: previously stored URLs remain available; a changed history file has its prior content in the backup; a no-op save leaves the file and existing backup unchanged; each monitor run reports the total number of current matches, new matches, and already-seen matches, including when there are no new notices.
- [x] **REQ-03 [INFERRED] — Custom keyword and theme searches:** Accept the configured default themes and user-supplied keyword arguments. Acceptance: each configured keyword group is searched and duplicate tenders are consolidated by URL.
- [x] **REQ-04 [INFERRED] — CSV export:** Export tender results to a caller-selected CSV path when requested. Acceptance: the output contains the defined columns and all exported tender rows.
- [x] **REQ-05 [INFERRED] — DTVP notices:** Search configured themes with their associated keywords and CPV codes; extract, deduplicate, paginate, and filter notices by publication date; retain matching keywords/themes in JSON and optional CSV. Acceptance: notices older than the inclusive date cutoff are excluded from current search results.
- [x] **REQ-06 [INFERRED] — Brandenburg notices:** Search configured themes and keywords on the Brandenburg public procurement portal; extract, deduplicate, paginate, filter by publication date, and persist results with optional CSV export.
- [x] **REQ-07 [CONFIRMED] — GIZ notices:** Search AI, Cybersecurity, and Software/data keywords on the public GIZ extended-search page; paginate results, merge matching metadata, and filter by an inclusive publication cutoff. Acceptance: `--published-since YYYY-MM-DD` includes notices on or after that date; the default window is the previous two calendar months.
- [x] **REQ-08 [CONFIRMED] — Separate search histories:** Keep portal histories separate. The main IT-Ausschreibung monitor defaults to `seen_it-ausschreibung.json`; DTVP, Brandenburg, Baden-Württemberg, and GIZ use `seen_dtvp.json`, `seen_brandenburg.json`, `seen_bw.json`, and `seen_giz.json`, respectively. Acceptance: each portal run reads/writes its configured file and does not overwrite another portal's history.
- [ ] **REQ-09 [PENDING] — Email delivery status:** The project has email-related utilities and body formatting, but the monitor does not currently expose whether an email was sent. Define and implement observable delivery status before re-enabling the temporarily commented send-related tests.
- [x] **REQ-10 [CONFIRMED] — Combined portal monitoring:** Provide `python analyse.py monitor-all` to run IT-Ausschreibung, DTVP, Brandenburg, Baden-Württemberg, and GIZ in one invocation. Print current-run matches and optionally export them with `--csv-file`; support `--headed`. Scheduled-task changes and email delivery are out of scope.
  - **Cross-source identity:** Consolidate notices only when normalized title, publication date, client, and URL all match. Retain all matching source names and merge their themes/keywords without dropping existing metadata. Keep notices with different URLs separate, even when their other fields match.
  - **IT-Ausschreibung fields:** Extend the main portal's result model and extraction to include publication date, deadline, publication type, and client information. Read date/deadline/type from the search result and the public `Auftraggeber` address from its detail page; use that address as the client value when the portal does not publish an organization name.
  - **Histories:** Continue reading and updating the five independent existing history files and preserve each portal's current identity and date-window behavior. A failed source must not overwrite or clear its history.
  - **Failure handling:** Attempt every source even if an earlier source fails. Report each source as successful or failed and its current-run count when available. Return a non-zero process status if any source or requested export fails.
  - **CSV:** Export unique matches found during this run, including records already present in source history, under the header `source,published,deadline,title,publication_type,client,theme,keyword,url`. Fields unavailable from a source are empty; existing export paths are backed up to `.bk` before replacement.
  - **Acceptance criteria:** One CLI invocation attempts all five sources; duplicate records merge only when all four identity fields match and preserve source attribution; each printed notice shows its source, matched theme(s), and keyword(s), with multiple themes and keywords separated by commas; the IT-Ausschreibung results include publication date and `Auftraggeber` address; source failures do not block later searches or overwrite the failed source's history; the summary and exit status reflect failures; and the optional CSV has the specified schema and unique current-run rows.
- [x] **REQ-11 [CONFIRMED] — Baden-Württemberg notices:** Add an independent search module for the public Vergabeplattform Baden-Württemberg (`https://vergabe.landbw.de/NetServer`) using the same six themes and exact keyword lists as Brandenburg. Search active tender notices (`Category=InvitationToTender`) by keyword, parse and paginate the portal's listing, deduplicate by detail URL while merging matching themes and keywords, and include only notices published on or after the default two-calendar-month cutoff. Persist the accumulated results in `seen_bw.json`, back up changed JSON history with `.bk` and back up existing CSV output on export, and provide the Brandenburg-style `--seen-file`, `--csv-file`, and `--headed` options. Preserve the portal's `Rechtsrahmen` field in stored/exported records. Acceptance: the BW module has its own record/history and CLI; its configured themes match Brandenburg exactly; date filtering is inclusive and malformed dates fail explicitly; pagination and duplicate metadata are handled; existing history survives successful runs; and tests cover parsing, search behavior, persistence, CSV export, and CLI summary.

## 3. Non-functional Requirements

- [x] **RNF-01 [INFERRED] — Runtime:** Support the project's configured Python 3.14.7 environment and Playwright-driven Chromium automation.
- [x] **RNF-02 [INFERRED] — Local persistence:** Keep search history in local JSON files and optional exports in CSV; do not require a database or hosted service for the current CLI workflow.
- [x] **RNF-03 [INFERRED] — Maintainability:** Keep portal-specific parsing/search logic independently testable and preserve unit tests for parsing, date filtering, deduplication, and persistence.
- [x] **RNF-04 [INFERRED] — Secret handling:** Do not commit SMTP credentials or other secrets; read operational credentials from environment/configuration outside source control.

## 4. Current Technical Approach

- Python CLI and standalone modules automate public tender search pages with Playwright.
- Results are normalized into portal-specific data records, deduplicated by URL, date-filtered where supported, and persisted to JSON.
- CSV export is optional. The main monitor also formats email alert content; observable email delivery is pending.
- See `dbv-specs-ops/docs/ARCHITECTURE.md` for the current implementation map.

## 5. Out of Scope (Current Baseline)

- A web application, hosted backend, or database service.
- An agent-facing web API or embedded desktop AI assistant.
- Automatic submission of tenders, procurement bids, or user registrations.
- Email delivery guarantees until a delivery result/status contract is defined.

## 6. Risks

- **Portal changes:** External pages can change markup, terminology, pagination, or availability. Mitigation: portal-specific tests and explicit failures when required page structure cannot be read.
- **Search noise:** Full-text keyword searches can return broad or irrelevant matches. Mitigation: retain search terms and themes for review, and keep eligibility decisions separate from matching.
- **Operational credentials:** SMTP settings may be sensitive. Mitigation: never store credentials in source or history files.
- **Date and history correctness:** Locale-formatted dates and per-portal history can cause missed or duplicate notices. Mitigation: test inclusive date boundaries, URL identities, backup behavior, and portal-specific paths.

## 7. Open Questions

- [ ] **OPEN-01:** Who are the intended users and how many contributors maintain the project? The owner accepted the adoption draft, but did not specify solo/team contributors.
- [ ] **OPEN-02:** What author/company attribution should appear in project metadata?
- [ ] **OPEN-03:** What application license should be declared? No root application license file was found; the bundled SDD framework's MIT license is not the application's license.
- [x] **OPEN-04:** Cross-portal orchestration is the next feature; its first-release scope and acceptance criteria are specified in REQ-10.
- [ ] **OPEN-05:** What should the app's changelog path be? `dbv-specs-ops/CHANGELOG.md` currently documents the bundled framework itself and must not be mixed with application release history.
- [ ] **OPEN-06:** What user-visible result/API should represent an attempted, successful, or failed email delivery?

## 8. AI Evals

No generative AI component is present in the application. Deterministic tests are the current validation mechanism; add Evals only if a nondeterministic AI feature is introduced.
