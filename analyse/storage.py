from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def load_seen_urls(seen_file: str | Path) -> set[str]:
    """Load a set of seen tender URLs from a JSON file.

    Parameters
    ----------
    seen_file : str | Path
        Path to the JSON file containing seen URLs.

    Returns
    -------
    set[str]
        Set of URLs that were already seen.
    """
    path = Path(seen_file)
    if not path.exists():
        return set()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()

    if not isinstance(data, list):
        return set()

    return {str(item) for item in data}


def save_seen_urls(urls: Iterable[str], seen_file: str | Path) -> None:
    """Save a collection of seen URLs to a JSON file.

    Parameters
    ----------
    urls : Iterable[str]
        URLs to store.
    seen_file : str | Path
        Path to the JSON file that will store seen URLs.
    """
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(set(urls)), indent=2), encoding="utf-8")


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
