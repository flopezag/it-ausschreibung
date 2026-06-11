# IT-Ausschreibung Monitor

This tool searches `it-ausschreibung.de` for tenders and can monitor results over time.

Usage examples:

- Search with a single keyword:

  ```bash
  python analyse.py search --keyword penetration
  ```

- Monitor with a single keyword:

  ```bash
  python analyse.py monitor --keyword penetration
  ```

- Provide multiple keywords as comma-separated values:

  ```bash
  python analyse.py monitor --keyword "penetration, it security, cloud"
  ```

- Provide named keywords as a JSON object (advanced searching across multiple terms):

  PowerShell:
  ```powershell
  python analyse.py monitor --keyword '{"a":"penetration","b":"it security"}'
  ```

  CMD (Windows):
  ```cmd
  python analyse.py monitor --keyword "{\"a\":\"penetration\",\"b\":\"it security\"}"
  ```

  Bash (Linux/macOS):
  ```bash
  python analyse.py monitor --keyword '{"a":"penetration","b":"it security"}'
  ```

Notes:
- `--keyword` accepts:
  - a single string,
  - comma-separated keywords,
  - a JSON object with string values.
- When multiple keywords are used, results are aggregated and deduplicated by URL.
- `install-task` serializes dict keywords to JSON when scheduling the command.

## Function reference

### search_tenders(keyword, headless=True)
- `keyword`: a string, a comma-separated string list, a list of strings, or a dict of named strings.
- `headless`: run browser in headless mode if `True`.

### save_results_csv(tenders, output_file)
- `tenders`: iterable of `Tender` objects.
- `output_file`: path to write CSV results.

### load_seen_urls(seen_file)
- `seen_file`: path to the JSON file storing seen URLs.

### save_seen_urls(urls, seen_file)
- `urls`: iterable of URLs to save.
- `seen_file`: path to store the JSON file.

### find_new_tenders(tenders, seen_urls)
- `tenders`: iterable of `Tender` objects.
- `seen_urls`: set of already-seen URLs.

### build_email_body(keyword, tenders)
- `keyword`: either a string, list of strings, or dict of named strings.
- `tenders`: iterable of `Tender` objects to format into the email.

### send_email_alert(subject, body, ...)
- `subject`: email subject.
- `body`: email body text.
- optional SMTP/email configuration parameters.

### monitor(keyword, seen_file, csv_file=None, headless=True)
- `keyword`: string, comma-separated string, list of strings, or dict of named strings.
- `seen_file`: path to the JSON file storing seen URLs.
- `csv_file`: optional CSV output path.
- `headless`: whether to run browser headless.

### install_windows_task(keyword, script_path, task_name='IT-Ausschreibung Monitor', python_executable=None)
- `keyword`: string, list of strings, or dict of named strings.
- `script_path`: path to this script.
- `task_name`: scheduled task name.
- `python_executable`: optional Python executable path.
