# Architecture: Ausschreibungen Monitor

> **Phase:** Plan
> **Status:** As-is architecture, inferred from the repository.
> **Last reviewed:** 2026-11-13

## 1. Stack

| Layer | Technology | Current use |
| --- | --- | --- |
| Language | Python 3.14.7 | CLI, parsing, monitoring and portal-specific search modules |
| Browser automation | Playwright 1.63.0 / Chromium | Public procurement portal searches |
| Testing | pytest 9.1.1 | Unit and mocked browser-flow tests |
| Persistence | JSON files | Per-source URL/announcement histories |
| Export | Python CSV support | Optional tender/announcement output |
| Scheduling | Windows Task Scheduler (`schtasks`) | Optional weekday monitor task |
| CI/CD | None identified in the current project configuration | No release/deployment workflow confirmed |

## 2. Repository Structure

```text
/
├── analyse.py                 # Main CLI entry point
├── analyse/
│   ├── cli.py                  # search, monitor, combined-monitor, and task commands
│   ├── browser_search.py       # IT-Ausschreibung search, metadata extraction, and links
│   ├── combined_monitor.py     # five-source orchestration, cross-source dedup, combined CSV
│   ├── monitor.py              # seen/new comparison, theme aggregation and reporting
│   ├── storage.py              # IT-Ausschreibung JSON history and CSV persistence
│   ├── models.py               # Shared Tender record
│   ├── mailer.py               # SMTP email utility
│   ├── tasks.py                # Windows scheduled task creation
│   ├── dtvp_analysis.py        # Standalone DTVP themed/CPV announcement search
│   ├── brandenburg_analysis.py # Standalone Brandenburg portal search
│   ├── bw_analysis.py          # Standalone Baden-Württemberg portal search
│   ├── berlin_analysis.py      # Standalone Berlin announcement search
│   ├── niedersachsen_analysis.py # Standalone Niedersachsen announcement search
│   ├── esa_star_analysis.py    # Standalone ESA STAR intended-call search
│   └── giz_analysis.py         # Standalone GIZ portal search
├── tests/
│   ├── test_analyse.py
│   ├── test_combined_monitor.py
│   ├── test_dtvp_analysis.py
│   ├── test_brandenburg_analysis.py
│   ├── test_bw_analysis.py
│   ├── test_berlin_analysis.py
│   ├── test_niedersachsen_analysis.py
│   ├── test_esa_star_analysis.py
│   └── test_giz_analysis.py
├── requirements.txt
└── requirements-dev.txt
```

The repository's `output/` directory contains JSON histories and their
backups. These are operational data, not source modules.

## 3. Component Relationships

- `analyse.py` delegates to `analyse.cli`.
- `analyse.cli` selects configured/custom keywords and calls
  `browser_search.search_tenders` for the main website.
- `analyse.monitor` calls `browser_search`, reads and updates histories using
  `storage`, reports current-run match counts, optionally exports CSV, and
  formats notification content.
- `analyse.combined_monitor` runs each portal's structured search workflow,
  keeps portal histories independent, normalizes current-run records, merges
  only records sharing title, publication date, client, and URL, and reports
  source status plus an optional combined CSV.
- `analyse.mailer` contains SMTP delivery functionality. The current monitor
  flow does not report a delivery result, and the send-related tests are
  commented pending that status contract.
- `analyse.tasks` constructs a Windows Task Scheduler command that invokes the
  main CLI.
- `dtvp_analysis`, `brandenburg_analysis`, `bw_analysis`, `berlin_analysis`,
  `niedersachsen_analysis`, `esa_star_analysis`, and `giz_analysis`
  are standalone portal workflows. Each owns its portal-specific theme/search
  configuration, parsing, date handling, JSON history, CSV output, and
  command-line entry point.
- Each portal retains its standalone command and history workflow. The
  `monitor-all` command orchestrates all five search functions without
  replacing their portal-specific parsing or persistence.

## 4. Persistence and Interfaces

- The main monitor stores URLs in `output/seen_it-ausschreibung.json` by
  default.
  `SEEN_FILE` and `--seen-file` can select another path.
- DTVP, Brandenburg, Baden-Württemberg, Berlin, Niedersachsen, ESA STAR, and
  GIZ keep separate histories in `output/seen_dtvp.json`,
  `output/seen_brandenburg.json`, `output/seen_bw.json`,
  `output/seen_berlin.json`, `output/seen_niedersachsen.json`,
  `output/seen_esa_star.json`, and `output/seen_giz.json`.
- Default JSON histories and their `.bk` backups are stored in the repository
  `output/` directory; callers may override a history with `--seen-file`.
- The BW search uses the portal's active-tender category and records its
  `Rechtsrahmen` field alongside the shared announcement fields.
- The Berlin search uses the public Bekanntmachungen listing, keyword form,
  start-based pagination, and external tender detail links. Its result record
  retains procedure, execution location, publication date, and deadline, with
  history isolated in `output/seen_berlin.json`.
- The Niedersachsen search uses the public extended-search POST form, selects
  the active `Tender` category (“Ausschreibung”; result rows can show
  `Ausschreibung` or `TNW`), and reads its table pagination controls. It
  retains publication type, contracting rule, issuing authority, deadline,
  publication date, and detail URL in its independent history.
- The ESA STAR search targets intended calls, filters Country `DE`, and
  resolves full paths in the live Technology Keywords tree rather than using
  the adjacent keyword label. It preserves each supplied row, explicitly maps
  five supplied paths to their live equivalents, and reports both paths and
  results per row. Duplicate live-path queries are merged while category and
  path attribution are retained in independent history at
  `output/seen_esa_star.json`. It remains outside `monitor-all`.
- The main IT-Ausschreibung result model includes publication date, deadline,
  publication type, and the public `Auftraggeber` address as client information.
  The combined monitor maps each portal's publisher field into the shared
  `client` export column.
- Histories are deduplicated and changed JSON files are backed up with a `.bk`
  suffix. The main storage module preserves the existing global-list format
  and supports keyword buckets.
- CSV output is a user-selected filesystem path; there is no database.
- User interaction is through command-line arguments and printed output.
- Combined notice lines include the merged source, theme, and keyword values
  so operators can see which configured searches matched each result.

## 5. External Integrations and Constraints

- Procurement portals are public third-party websites, not stable application
  APIs. Their markup, response time, and search behavior are outside the
  project's control.
- Playwright's Chromium installation is required for live browser searches;
  parsing and most persistence logic can be unit-tested without live sites.
- SMTP credentials are expected from environment-based configuration; secrets
  must not be committed.
- Windows scheduled tasks are platform-specific; direct CLI execution remains
  available on other supported environments.

## 6. Current Technical Decisions (Inferred)

- **ADR [INFERRED] — Separate per-portal search implementations:** Keep site
  selectors and parsing isolated because portal interfaces differ.
- **ADR [INFERRED] — File-based history:** Use local JSON and optional CSV
  rather than introducing a database for the current operator-oriented CLI.
- **ADR [INFERRED] — Browser automation for portal search:** Use Playwright
  because these public procurement sites expose interactive search forms.
- **ADR [INFERRED] — No app-facing agent API or embedded AI:** The current
  product is a CLI monitor, not an AI-integrated web/desktop application.

Do not treat these inferred decisions as immutable; update them when the owner
confirms a change.

## 7. Known Constraints and Risks

- Portal-specific selectors can break after website changes.
- Search results can be broad, and the site may cap/paginate results.
- Cross-source duplicate detection depends on matching title, publication
  date, client, and URL; the main IT-Ausschreibung client value is the public
  Auftraggeber address rather than an organization name.
- The root README documents usage; the full test suite is the principal
  regression check. The latest targeted portal/CLI run passed 118 tests and
  failed one known Brandenburg theme-configuration expectation; all five
  combined-monitor tests passed. The full suite was not rerun.
