# TODO

## Completed

- [x] Add standalone Brandenburg Vergabemarktplatz analysis with theme-based keyword searches, pagination, two-month publication filtering, persistent JSON history with backups, and optional CSV export.
  - Run with `python -m analyse.brandenburg_analysis` to search the six configured themes and report newly discovered tenders.
  - Keep accumulated results in `seen_brandenburg.json`, deduplicated by project URL with matching keywords and themes combined.
- [x] Add standalone DTVP announcement analysis with theme-specific keywords and CPVs, pagination, date filtering, per-keyword reporting, description links, persistent JSON history, and backups.
  - Run with `python -m analyse.dtvp_analysis` to search the five configured themes and print only new matches from the last two calendar months.
  - Keep the complete matching history in `seen_dtvp.json`, deduplicated by announcement URL; merge matching keywords and themes for the same URL.
  - Normalize merged keyword and theme values to remove duplicates from new and existing records; legacy duplicates are cleaned on the next run.
  - Use `--csv-file "C:\path\to\results.csv"` to choose a Windows output path, or `--headed` to show the browser.
  - Each overwrite backs up the prior file as `<filename>.json.bk` or `<filename>.csv.bk`.
  - Use `--seen-file "C:\path\to\seen_dtvp.json"` to choose a different JSON history file.
  - Edit `THEMES` in `analyse/dtvp_analysis.py` to change theme names, keywords, and CPV filters.
  - Each keyword prints only previously unseen matching notices and their description links, or `No new ausschreibung found.`
  - Print per-keyword search/setup, pagination/extraction, page-count, and total-run timings to guide performance improvements.
  - Install the Playwright browser if needed with `python -m playwright install chromium`.
- [x] Improve `seen.json` persistence so multiple keyword runs preserve previously seen URLs instead of overwriting the file.
  - Implementation note: merge new URLs into the existing seen set instead of replacing the file on each run.
  - Implementation note: support per-keyword buckets or a global URL set so unrelated keyword scans do not clear previous    
    results.
- [x] Back up the previous `seen.json` as `seen.json.bk` before saving changed history, and preserve that backup when a run adds no new URLs.
- [x] Add README usage examples for the new package layout and command-line entrypoint.
- [x] Add search operation for the web portal: Brandenburg

## Immediate enhancements

- [ ] Improve CLI help text to clearly describe `search`, `monitor`, and `install-task` commands.
- [ ] Add unit tests for `analyse.cli.parse_args()` and `analyse.cli.main()` flow.
- [ ] Add integration tests for keyword parsing edge cases (empty string, invalid JSON, malformed CSV input).
- [ ] Verify the IT-Ausschreibung grouped keyword monitor after the recent reporting fix; confirm each result is attributed to the correct matching keyword and the seen-history behavior is expected.
- [ ] Integrate the dtvp_analysis.py into the current logic to execute the check for it-ausschreibung and dtvp and the rest of search operations
- [ ] Change the output file of seen.json to seen_it-ausschreibung.json file name and check the creation of backup file
- [ ] Add search operation for the web portal: evergabe.de
- [ ] Add search operation for the web portal: BW
- [ ] Add search operation for the web portal: Bayern
- [ ] Add search operation for the web portal: Berlin
- [ ] Add search operation for the web portal: Niedersachsen
- [ ] Add search operation for the web portal: NRW
- [ ] Add search operation for the web portal: ESA-STAR

## Quality and maintainability

- [ ] Convert project imports to fully qualified package imports consistently across all modules.
- [ ] Add type validation / runtime checks for `keyword` values in `analyse.browser_search` and `analyse.tasks`.
- [ ] Add logging support instead of direct `print()` calls in `analyse.monitor` and `analyse.cli`.
- [ ] Correct message of `pylance`

## Features to consider

- [ ] Add support for multiple search pages or pagination in `analyse.browser_search.search_tenders()`.
- [ ] Add a configuration file option for SMTP settings and default file locations.
- [ ] Add a mode to run monitor only once without modifying `seen.json` for dry runs.
- [ ] Implementation note: keep bucketed search metadata explicit in `seen.json` for faster membership checks and to support backwards-compatible global list loading.
  - Implementation note: normalize and deduplicate URLs before saving so equivalent URLs do not create duplicate entries.
  - Implementation note: add tests covering both legacy global-list and new bucketed `seen.json` formats.
- [ ] Improve tender search scalability to handle growing result volumes over time (pagination, incremental search, or filtered search).
  - Implementation note: add paged browsing in `analyse.browser_search.search_tenders()` and stop when no new results are returned.
  - Implementation note: add filter options (date range, category, or keywords) so users can narrow searches as tender volume increases.
- [ ] Add Windows task uninstall support or task update detection.

## Long-term improvements

- [ ] Add a `setup.py` / `pyproject.toml` so this package can be installed and imported cleanly.
- [ ] Add Docker support or a portable environment script for running the monitor on CI/servers.
- [ ] Add a health-check or status endpoint if the monitor is used as a service.
