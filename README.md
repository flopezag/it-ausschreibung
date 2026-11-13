# Ausschreibungen Monitor

Searches `it-ausschreibung.de` for tenders, tracks previously seen results, and
includes standalone searches for announcements on DTVP and the Brandenburg,
Baden-Württemberg, Berlin, Niedersachsen, and GIZ procurement portals, plus
intended calls from ESA STAR.

Default JSON histories and their `.bk` backups are stored in the repository's
`output/` directory. You can override a history location with `--seen-file`.

## Requirements and setup

The project is configured for Python 3.14.7 and uses a virtual environment so
its Python packages stay isolated from other projects.

Create a virtual environment in the repository root:

```bash
python -m venv .venv
```

Activate it in your shell:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Windows Command Prompt
.venv\Scripts\activate.bat
```

Install the application and development dependencies into the active
environment:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

The project uses Playwright to automate Chromium. After installing Playwright,
download its matching Chromium browser:

```bash
python -m playwright install chromium
```

Run this command again after upgrading or changing the Playwright version so
the browser binaries match the installed package. Use `python -m ...` while the
virtual environment is active to ensure commands use that environment's
interpreter. To leave the environment, run `deactivate`.

## IT-Ausschreibung commands

Run commands from the repository root with the virtual environment activated.

Search all configured keyword themes:

```bash
python analyse.py search
```

Monitor all configured keyword themes and save new results in
`output/seen_it-ausschreibung.json`:

```bash
python analyse.py monitor
```

The configured terms from `check` are grouped in `analyse/cli.py`: AI
(`chatbot`, `llm`, `KI`, `generative`, `predictive`), Quantum (`quantum`,
`quanten`, `qml`, `qnn`, `pqc`), Cybersecurity (`penetration`, `pet`, `red`,
`blue`), and Robotics (`roboter`, `drohne`, `inspektion`, `atex`). Each run
searches all terms and deduplicates matching tender URLs.

The `search` command prints unique tenders matching any configured term. The
`monitor` command reports the total number of tenders found, how many are
new, and how many were already in history, including when no new tenders are
found. It lists details and matching keyword(s) for new tenders. Its optional
`--csv-file` exports all tenders found during that run, including tenders
already in history.

Run all five portal monitors together and print only unique current-run
matches:

```bash
python analyse.py monitor-all
```

Records are merged only when title, publication date, client, and link match;
their sources and matching keywords/themes are combined and shown in brackets
before each result, with multiple themes and keywords separated by commas. Add
`--csv-file combined.csv` to export the results, or `--headed` to show the
browsers. Each portal keeps its own history, and later searches continue if a
source fails. The command reports failures and exits non-zero if any source or
requested export fails. IT-Ausschreibung's public `Auftraggeber` address is
used as the client value because its organization name is not shown publicly.

To search or monitor a custom set of keywords, pass a comma-separated list:

```bash
python analyse.py monitor --keyword "penetration, it security, cloud"
```

Or use a JSON object to assign names to keywords. Quote the JSON argument as
shown for your shell:

```powershell
# PowerShell
python analyse.py monitor --keyword '{"a":"penetration","b":"it security"}'
```

```cmd
:: Windows Command Prompt
python analyse.py monitor --keyword "{\"a\":\"penetration\",\"b\":\"it security\"}"
```

```bash
# Bash (Linux / macOS)
python analyse.py monitor --keyword '{"a":"penetration","b":"it security"}'
```

Both `search` and `monitor` accept `--csv-file results.csv` to export results.
Use `--headed` to show the browser while a command runs; searches are headless
by default. The monitor keeps previously seen URLs in
`output/seen_it-ausschreibung.json`, grouped by
theme for the default search or by keyword set for a custom search, so later
runs do not discard earlier search history. Choose a different history file
with `--seen-file path/to/history.json`. Before an existing
history file is updated, it is copied to the same path with `.bk` appended
(for example, `output/seen_it-ausschreibung.json.bk`). Set `SEEN_FILE` to override
the default history path.

All portals' default JSON histories and their `.bk` backups are stored in the
repository-root `output/` directory. A custom `--seen-file` keeps its backup
beside the selected file.

On Windows, `install-task` creates a weekday scheduled task. Point it to the
project's `analyse.py` entry point and the Python executable inside the virtual
environment:

```powershell
python analyse.py install-task `
  --keyword penetration `
  --script-path "C:\path\to\it-ausschreibung\analyse.py" `
  --python-executable "C:\path\to\it-ausschreibung\.venv\Scripts\python.exe"
```

## DTVP announcements

The standalone DTVP search groups searches by theme. Every keyword in a theme
is searched with that theme's CPV filters; the mapping is configured in
`analyse/dtvp_analysis.py`.

- **AI** — Keywords: Künstliche Intelligenz, Maschinelles Lernen, Generative KI,
  Large Language Model, Computer Vision. CPVs: 48000000-8, 72000000-5,
  73000000-2.
- **Quantum** — Keywords: Quantencomputing, Quantencomputer, Quantenalgorithmus,
  Quantensoftware. CPVs: 30000000-9, 38000000-5, 48000000-8, 72000000-5,
  73000000-2.
- **Cybersecurity** — Keywords: IT-Sicherheit, Informationssicherheit, ISMS,
  BSI IT-Grundschutz, Penetrationstest, SIEM, CRA. CPVs: 48000000-8,
  72000000-5, 32000000-3.
- **Robotics** — Keywords: Robotik, Robotersystem, Inspektionsroboter,
  Autonomer mobiler Roboter, Drohne. CPVs: 42000000-6, 38000000-5, 48000000-8,
  72000000-5, 73000000-2, 34000000-7, 35000000-4, 32000000-3.
- **Software** — Keywords: Dokumentenmanagementsystem, E-Akte, DevSecOps, SBOM,
  Testautomatisierung, Digitale Identität. CPVs: 48000000-8, 72000000-5.

Cybersecurity searches include CPV 32000000-3. Results retain the matching
theme and keyword in the JSON history and CSV export. Run the search with:

```bash
python -m analyse.dtvp_analysis
```

It reports new matches, saves the accumulated history to
`output/seen_dtvp.json`, and
searches announcements published within the last two calendar months (including
the cutoff date). Existing history is retained even if entries are older than
the search window, with announcements deduplicated by their URL and matching
keywords/themes combined. The accumulated history can optionally be exported
to CSV:

```bash
python -m analyse.dtvp_analysis --csv-file dtvp_results.csv
```

Use `--seen-file path/to/seen_dtvp.json` to select a different history file, or
`--headed` to display the browser. Existing DTVP JSON and CSV output files are
copied to a `.bk` backup before they are overwritten. The command prints
per-keyword search and pagination timings to help identify slow stages.

## Brandenburg Vergabemarktplatz

The standalone Brandenburg search uses the public extended search on the
Vergabemarktplatz and searches these themes and terms:

- **AI** — Datenanalyse, Entscheidungsunterstützung, Sprachmodell.
- **Quantum** — Quantensoftware, Quantenkommunikation,
  Post-Quanten-Kryptographie.
- **Cybersecurity** — NIS2, KRITIS, SIEM, Identitätsmanagement.
- **Robotics** — Autonome Navigation, Cobot, Missionsplanung.
- **Software** — ECM, CMS, SBOM, Identitätsmanagement, Digitale Identität.
- **Cross-domain** — Forschungsprojekt, Demonstrator, Prototyp,
  Machbarkeitsstudie, Reallabor.

Run it from the repository root:

```bash
python -m analyse.brandenburg_analysis
```

The search reports new matches published within the last two calendar months
and accumulates deduplicated history in `output/seen_brandenburg.json`. The optional
`--csv-file path/to/results.csv` exports the history, `--seen-file
path/to/seen_brandenburg.json` selects another history file, and `--headed` displays the
browser. Existing JSON history is backed up to `.bk` before changed data is
saved; unchanged history does not replace the backup. Existing CSV output is
backed up to `.bk` on each export.

## Baden-Württemberg Vergabeplattform

The standalone Baden-Württemberg search at
`https://vergabe.landbw.de/NetServer` uses the same six themes and exact
keywords listed in the Brandenburg section. It searches active tender notices,
keeps the portal's legal framework (`Rechtsrahmen`) alongside the Brandenburg
result fields, follows result pagination, and merges matching themes and
keywords by notice URL.

Run the search from the repository root:

```bash
python -m analyse.bw_analysis
```

The command reports new matches published within the last two calendar months
and accumulates history in `output/seen_bw.json`. Use `--seen-file
path/to/seen_bw.json` to select another history file, `--csv-file
path/to/results.csv` to export the accumulated history, or `--headed` to show
the browser. Existing JSON and CSV files are backed up to `.bk` before changed
JSON history is saved or CSV output is replaced.

## Berlin Vergabeplattform

The standalone Berlin search at
`https://www.berlin.de/vergabeplattform/veroeffentlichungen/bekanntmachungen/`
uses the same six themes and exact keywords listed in the Brandenburg section.
It searches by keyword, follows the listing's pagination, and merges matching
themes and keywords by the public tender detail URL. Results retain the
publication date, deadline, procedure, and execution location shown by Berlin;
the location is not treated as the contracting authority.

Run the search from the repository root:

```bash
python -m analyse.berlin_analysis
```

The command reports new announcements published within the last two calendar
months and accumulates history in `output/seen_berlin.json`. Use `--seen-file
path/to/seen_berlin.json` to select another history file,
`--csv-file path/to/results.csv` to export the accumulated history, or
`--headed` to show the browser. Changed JSON history and existing CSV output
are backed up to `.bk`. Berlin has its own standalone command and is not part
of `monitor-all`.

## Niedersachsen Vergabeplattform

The standalone Niedersachsen search uses
`https://vergabe.niedersachsen.de/Satellite/company/announcements/categoryOverview.do?method=showCategoryOverview`
and the same six themes and exact keywords listed in the Brandenburg section.
It submits the portal's extended-search form and selects the `Tender`
publication category (“Ausschreibung”), excluding intended notices and awarded
contracts. The result status may be shown as “Ausschreibung” or “TNW”.
Published date, deadline (`nv` where none is listed), title, publication type,
contracting rule, issuing authority, and public detail URL are retained.

Run the search from the repository root:

```bash
python -m analyse.niedersachsen_analysis
```

The search includes notices published within the last two calendar months and
accumulates history in `output/seen_niedersachsen.json`. Use `--seen-file` to select
another history, `--csv-file path/to/results.csv` to export accumulated
results, or `--headed` to show the browser. Changed JSON history and existing
CSV output are backed up to `.bk`. The command is standalone and is not part
of `monitor-all`.

## ESA STAR intended calls

The standalone ESA STAR search uses
`https://esastar-publication-ext.sso.esa.int/ESATenderActions/filter/cfp_intended`,
filters Country `DE`, and searches the full ESA Technology Keywords tree for
each of the 32 supplied category/path rows. When the live tree differs from a
supplied path, the search uses an explicit live-path mapping and prints both
the supplied and selected paths. Terminal output highlights each category and
technology keyword using the same colors as the other portal searches. The
current mappings include an intermediate parent for two on-board
machine-learning rows, portal spelling/spacing
differences for two rows, and the live `I` Mission Control node where the
supplied list says `II`. Repeated paths are queried once and reported for each
associated row. The search uses the portal's current Intended listing without
an additional local date cutoff.

Run it from the repository root:

```bash
python -m analyse.esa_star_analysis
```

Results and history are kept separately in `output/seen_esa_star.json`. Use
`--seen-file path/to/history.json` to select another history,
`--csv-file path/to/results.csv` to export accumulated results, or `--headed`
to show the browser. Changed JSON history and existing CSV output are backed
up to `.bk`. ESA STAR is a standalone command and is not part of `monitor-all`.

## GIZ Vergabemarktplatz

The standalone GIZ search uses the public extended-search page and searches
the configured English-language keywords in three themes: AI, Cybersecurity,
and Software/data. It deduplicates notices by project URL, combines matching
keywords and themes, and filters by publication date.

Run the default search from the repository root:

```bash
python -m analyse.giz_analysis
```

By default, it includes notices published in the last two calendar months.
To search from a specific inclusive cutoff date, pass `--published-since` in
ISO format; for example, to search since 1 August 2026:

```bash
python -m analyse.giz_analysis --published-since 2026-08-01
```

The accumulated history is saved to `output/seen_giz.json`; use `--seen-file` to
choose another path. Pass `--csv-file giz_results.csv` to export the history,
or `--headed` to display the browser. Existing JSON and CSV files are backed
up to `.bk` before changed data is saved.

## Tests

Install both requirement files as described above, then run:

```bash
pytest
```
