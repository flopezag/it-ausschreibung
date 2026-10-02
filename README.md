# IT-Ausschreibung Monitor

Searches `it-ausschreibung.de` for tenders, tracks previously seen results, and
includes a separate search for announcements on DTVP.

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

Search once:

```bash
python analyse.py search --keyword penetration
```

Monitor for new results and save them in the default `seen.json` history:

```bash
python analyse.py monitor --keyword penetration
```

Search multiple keywords using a comma-separated list:

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
by default. The monitor keeps previously seen URLs in `seen.json`, grouped by
keyword set, so later runs do not discard earlier search history. Choose a
different history file with `--seen-file path/to/seen.json`.

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
  BSI IT-Grundschutz, Penetrationstest, SIEM. CPVs: 48000000-8, 72000000-5,
  32000000-3.
- **Robotics** — Keywords: Robotik, Robotersystem, Inspektionsroboter,
  Autonomer mobiler Roboter, Drohne. CPVs: 42000000-6, 38000000-5, 48000000-8,
  72000000-5, 73000000-2, 34000000-7, 35000000-4, 32000000-3.
- **Software** — Keywords: Dokumentenmanagementsystem, E-Akte, DevSecOps, SBOM,
  Testautomatisierung, Digitale Identität. CPVs: 48000000-8, 72000000-5.

Cybersecurity includes the optional CPV 32000000-3. Results retain the matching
theme and keyword in the JSON history and CSV export. Run the search with:

```bash
python -m analyse.dtvp_analysis
```

It reports new matches, saves the accumulated history to `seen_dtvp.json`, and
searches announcements published within the last two calendar months (including
the cutoff date). Existing history is retained even if entries are older than
the search window. The accumulated history can optionally be exported to CSV:

```bash
python -m analyse.dtvp_analysis --csv-file dtvp_results.csv
```

Use `--seen-file path/to/seen_dtvp.json` to select a different history file, or
`--headed` to display the browser. Existing DTVP JSON and CSV output files are
copied to a `.bk` backup before they are overwritten.

## Tests

Install both requirement files as described above, then run:

```bash
pytest
```
