from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable


def _load_seen_payload(path: Path) -> Any:
    """Read raw JSON from the seen URLs file.

    Parameters
    ----------
    path : Path
        Path to the JSON file containing seen URLs.

    Returns
    -------
    Any
        Parsed JSON payload, or an empty dict on missing or invalid content.
    """
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _normalize_seen_data(data: Any) -> dict[str, set[str]]:
    """Normalize raw seen-file data into keyword buckets.

    Parameters
    ----------
    data : Any
        Raw parsed JSON from the seen URLs file.

    Returns
    -------
    dict[str, set[str]]
        A mapping from keyword bucket to a set of normalized URLs.
    """
    if isinstance(data, dict):
        buckets: dict[str, set[str]] = {}
        for keyword, values in data.items():
            if isinstance(values, list):
                buckets[str(keyword)] = {str(item) for item in values}
        return buckets

    if isinstance(data, list):
        return {"__global__": {str(item) for item in data}}

    return {}


def load_seen_urls(seen_file: str | Path, keyword: str | None = None) -> set[str]:
    """Load seen tender URLs from a JSON file.

    Parameters
    ----------
    seen_file : str | Path
        Path to the JSON file containing seen URLs.
    keyword : str | None, optional
        Optional keyword bucket to read. When omitted, the global set of URLs is returned.

    Returns
    -------
    set[str]
        Set of URLs that were already seen.
    """
    path = Path(seen_file)
    buckets = _normalize_seen_data(_load_seen_payload(path))

    if keyword is None:
        return set().union(*buckets.values()) if buckets else set()

    if str(keyword) in buckets:
        return buckets[str(keyword)]

    return buckets.get("__global__", set())


def save_seen_urls(urls: Iterable[str], seen_file: str | Path, keyword: str | None = None) -> None:
    """Save a collection of seen URLs to a JSON file.

    Parameters
    ----------
    urls : Iterable[str]
        URLs to store.
    seen_file : str | Path
        Path to the JSON file that will store seen URLs.
    keyword : str | None, optional
        Optional keyword bucket to update. When omitted, the global bucket is used.
    """
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    buckets = _normalize_seen_data(_load_seen_payload(path))
    bucket_name = "__global__" if keyword is None else str(keyword)
    existing_urls = buckets.get(bucket_name, set())
    updated_urls = existing_urls | {str(url) for url in urls}
    buckets[bucket_name] = updated_urls

    if keyword is None and len(buckets) == 1 and "__global__" in buckets:
        content = json.dumps(sorted(updated_urls), indent=2)
    else:
        payload: dict[str, list[str]] = {}
        for name, values in buckets.items():
            payload[name] = sorted(values)
        content = json.dumps(payload, indent=2)

    if path.exists() and path.read_text(encoding="utf-8") == content:
        return

    if path.exists():
        shutil.copy2(path, Path(f"{path}.bk"))
    path.write_text(content, encoding="utf-8")


def save_results_csv(tenders: Iterable["models.Tender"], output_file: str | Path) -> None:
    """Save tenders into a CSV file.

    Parameters
    ----------
    tenders : Iterable[Tender]
        Tenders to write.
    output_file : str | Path
        Path to the output CSV file.
    """
    from csv import writer
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        csv_writer = writer(file)
        csv_writer.writerow(["title", "url"])
        for tender in tenders:
            csv_writer.writerow([tender.title, tender.url])
