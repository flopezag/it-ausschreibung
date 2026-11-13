# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================
"""Search Baden-Württemberg procurement notices. @spec REQ-08, REQ-11"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import re
import shutil
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence, cast
from urllib.parse import urlencode, urljoin

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Allows parsing and CSV tests without Playwright installed.
    sync_playwright = None


BW_SEARCH_URL = (
    "https://vergabe.landbw.de/NetServer/PublicationSearchControllerServlet"
)
BW_BASE_URL = "https://vergabe.landbw.de"
SEARCH_LOOKBACK_MONTHS = 2
THEME_COLOR = "\033[96m"
KEYWORD_COLOR = "\033[93m"
COLOR_RESET = "\033[0m"


@dataclass(frozen=True, slots=True)
class BWProject:
    published: str
    deadline: str
    title: str
    publication_type: str
    publisher: str
    keyword: str
    url: str | None = None
    theme: str = ""
    legal_framework: str = ""


@dataclass(frozen=True, slots=True)
class BWTheme:
    name: str
    keywords: tuple[str, ...]


THEMES = (
    BWTheme(
        "AI",
        ("Datenanalyse", "Entscheidungsunterstützung", "Sprachmodell",
         "Künstliche Intelligenz", "Maschinelles Lernen", "Generative KI", "Bildverarbeitung"),
    ),
    BWTheme(
        "Quantum",
        ("Quantensoftware", "Quantenkommunikation", "Post-Quanten-Kryptographie",
         "Quantencomputing", "Quantencomputer", "Quantenalgorithmus", "Post-Quanten-Kryptographie"),
    ),
    BWTheme(
        "Cybersecurity",
        ("NIS2", "KRITIS", "SIEM", "Identitätsmanagement", "IT-Sicherheit", 
         "Informationssicherheit", "Penetrationstest", "Schwachstellenanalyse", "ISMS"),
    ),
    BWTheme(
        "Robotics",
        ("Autonome Navigation", "Cobot", "Missionsplanung", "Robotik", "Roboter", 
         "Inspektionsroboter", "Drohne", "Fahrerloses Transportsystem"),
    ),
    BWTheme(
        "Software",
        ("ECM", "CMS", "SBOM", "Identitätsmanagement", "Digitale Identität", 
         "Dokumentenmanagementsystem", "E-Akte", "DevSecOps", "Softwaretest", "Testautomatisierung"),
    ),
    BWTheme(
        "Cross-domain",
        ("Forschungsprojekt", "Demonstrator", "Prototyp", "Machbarkeitsstudie", "Reallabor",
         "Generative KI", "Quantencomputing", "Post-Quanten-Kryptographie", "Robotik", "DevSecOps"),
    ),
)


def project_identity(project: BWProject) -> str:
    identity = project.url or "\x1f".join(
        (project.title, project.published, project.publisher)
    )
    return identity


def _merge_metadata(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for item in value.split("; "):
            item = item.strip()
            if item and item not in merged:
                merged.append(item)
    result = "; ".join(merged)
    return result


def merge_project(projects: dict[str, BWProject], project: BWProject) -> None:
    key = project_identity(project)
    existing = projects.get(key)
    if existing is None:
        projects[key] = replace(
            project,
            keyword=_merge_metadata(project.keyword),
            theme=_merge_metadata(project.theme),
        )
    else:
        merged_keyword = _merge_metadata(existing.keyword, project.keyword)
        merged_theme = _merge_metadata(existing.theme, project.theme)
        if merged_keyword != existing.keyword or merged_theme != existing.theme:
            projects[key] = replace(
                existing,
                keyword=merged_keyword,
                theme=merged_theme,
            )


def _project_detail_url(object_id: str | None, category: str | None) -> str | None:
    detail_url: str | None = None
    if object_id and category:
        query = urlencode(
            {
                "function": "Detail",
                "TOID": object_id,
                "Category": category,
            }
        )
        detail_url = urljoin(
            BW_BASE_URL,
            f"/NetServer/PublicationControllerServlet?{query}",
        )
    return detail_url


def parse_project_row(
    cells: Sequence[str],
    keyword: str,
    href: str | None = None,
    theme: str = "",
) -> BWProject | None:
    """Convert one BW result row into a project record. @spec REQ-11"""
    if len(cells) < 6 or not cells[1].strip():
        return None

    return BWProject(
        published=cells[0].strip(),
        deadline=cells[5].strip(),
        title=cells[1].strip(),
        publication_type=cells[3].strip(),
        publisher=cells[2].strip(),
        keyword=keyword,
        url=urljoin(BW_BASE_URL, href) if href else None,
        theme=theme,
        legal_framework=cells[4].strip(),
    )


def _extract_page_projects(
    page: Any, keyword: str, theme: str = ""
) -> list[BWProject]:
    projects: list[BWProject] = []
    rows = page.locator(
        "#pagePublicationSearchResult table.tableHorizontalHeader tbody tr"
    ).all()
    for row in rows:
        cells = [cell.inner_text() for cell in row.locator("td").all()]
        href = _project_detail_url(
            row.get_attribute("data-oid"),
            row.get_attribute("data-category"),
        )
        project = parse_project_row(cells, keyword, href, theme)
        if project is not None:
            projects.append(project)
    return projects


def _search_url(keyword: str) -> str:
    query = urlencode(
        {
            "function": "Search",
            "Category": "InvitationToTender",
            "Searchkey": keyword,
        }
    )
    search_url = f"{BW_SEARCH_URL}?{query}"
    return search_url


def _subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    result = date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
    return result


def _is_within_date_window(project: BWProject, since: date) -> bool:
    try:
        published = datetime.strptime(project.published, "%d.%m.%Y").date()
    except ValueError as error:
        raise ValueError(
            f"Cannot parse publication date {project.published!r} "
            f"for project {project.title!r}; expected DD.MM.YYYY."
        ) from error
    is_within = published >= since
    return is_within


def print_keyword_results(
    keyword: str, projects: Iterable[BWProject], theme: str = ""
) -> None:
    results = list(projects)
    if not results:
        print(
            "No new Baden-Württemberg tender found for "
            f"theme {theme}, keyword: {keyword}."
        )
    else:
        print(
            f"New Baden-Württemberg tender found for theme {theme}, keyword: {keyword}"
        )
        for project in results:
            print(
                f"- {project.title} | {project.published} | {project.publisher}"
            )
            if project.url:
                print(f"  Description: {project.url}")
            print()


def search_bw_projects(
    themes: Iterable[BWTheme] = THEMES,
    headless: bool = True,
    seen_keys: set[str] | None = None,
    published_since: date | None = None,
) -> list[BWProject]:
    """Search BW tenders by configured themes and keywords. @spec REQ-11"""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install"
        )

    theme_list = [theme for theme in themes if theme.keywords]
    if not theme_list:
        return []

    previously_seen = seen_keys if seen_keys is not None else set()
    date_cutoff = published_since or _subtract_months(
        date.today(), SEARCH_LOOKBACK_MONTHS
    )
    print(
        "Including Baden-Württemberg tenders published on or after "
        f"{date_cutoff:%d.%m.%Y}."
    )
    unique: dict[str, BWProject] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            for theme in theme_list:
                print(
                    f"{THEME_COLOR}Monitoring Baden-Württemberg theme: "
                    f"{theme.name}{COLOR_RESET}"
                )
                for keyword in theme.keywords:
                    print(
                        f"{KEYWORD_COLOR}Monitoring Baden-Württemberg keyword: "
                        f"{keyword}{COLOR_RESET}"
                    )
                    page.goto(_search_url(keyword), wait_until="domcontentloaded")
                    page.get_by_role(
                        "heading", name=re.compile(r"Ihr Suchergebnis")
                    ).wait_for(state="visible", timeout=60000)

                    keyword_results: dict[str, BWProject] = {}
                    while True:
                        for project in _extract_page_projects(
                            page, keyword, theme.name
                        ):
                            if not _is_within_date_window(project, date_cutoff):
                                continue
                            key = project_identity(project)
                            if key not in previously_seen:
                                merge_project(keyword_results, project)
                            merge_project(unique, project)

                        next_page = page.get_by_role("link", name="›")
                        if next_page.count() == 0:
                            break
                        next_page.click()
                        page.get_by_role(
                            "heading", name=re.compile(r"Ihr Suchergebnis")
                        ).wait_for(state="visible", timeout=60000)

                    print_keyword_results(
                        keyword, keyword_results.values(), theme=theme.name
                    )
                print()

        finally:
            browser.close()

    return list(unique.values())


def load_seen_projects(seen_file: str | Path) -> list[BWProject]:
    """Load this portal's independent JSON history. @spec REQ-08, REQ-11"""
    path = Path(seen_file)
    projects: list[BWProject] = []
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if content.strip():
            payload: Any = json.loads(content)
            if not isinstance(payload, list):
                raise ValueError(f"Expected a JSON list in {path}")

            for raw_item in cast(list[object], payload):
                if not isinstance(raw_item, dict):
                    raise ValueError(f"Expected project objects in {path}")
                item = cast(dict[str, Any], raw_item)
                projects.append(
                    BWProject(
                        published=str(item.get("published", "")),
                        deadline=str(item.get("deadline", "")),
                        title=str(item.get("title", "")),
                        publication_type=str(item.get("publication_type", "")),
                        publisher=str(item.get("publisher", "")),
                        keyword=str(item.get("keyword", "")),
                        url=str(item["url"]) if item.get("url") else None,
                        theme=str(item.get("theme", "")),
                        legal_framework=str(item.get("legal_framework", "")),
                    )
                )
    return projects


def backup_existing_file(file_path: str | Path) -> None:
    path = Path(file_path)
    if path.exists():
        shutil.copy2(path, Path(f"{path}.bk"))


def save_seen_projects(
    projects: Iterable[BWProject], seen_file: str | Path
) -> None:
    """Persist this portal's independent JSON history. @spec REQ-08, REQ-11"""
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    unique: dict[str, BWProject] = {}
    for project in projects:
        merge_project(unique, project)

    content = json.dumps(
        [asdict(project) for project in unique.values()],
        indent=2,
        ensure_ascii=False,
    )
    if path.exists():
        previous_content = path.read_text(encoding="utf-8")
        if previous_content != content:
            backup_existing_file(path)
            path.write_text(content, encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def save_projects_csv(
    projects: Iterable[BWProject], output_file: str | Path
) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    backup_existing_file(output_path)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "published",
                "deadline",
                "title",
                "publication_type",
                "legal_framework",
                "publisher",
                "theme",
                "keyword",
                "url",
            ]
        )
        for project in projects:
            writer.writerow(
                [
                    project.published,
                    project.deadline,
                    project.title,
                    project.publication_type,
                    project.legal_framework,
                    project.publisher,
                    project.theme,
                    project.keyword,
                    project.url or "",
                ]
            )


def main() -> None:
    """Run the BW search with its own history and optional CSV.

    @spec REQ-08, REQ-11
    """
    parser = argparse.ArgumentParser(
        description=(
            "Search Baden-Württemberg's Vergabeplattform for tender announcements."
        )
    )
    parser.add_argument(
        "--headed", action="store_true", help="Show the browser while searching."
    )
    parser.add_argument("--seen-file", default="seen_bw.json")
    parser.add_argument(
        "--csv-file", help="Optionally export the saved announcement history as CSV."
    )
    args = parser.parse_args()

    seen_projects = load_seen_projects(args.seen_file)
    seen_keys = {project_identity(project) for project in seen_projects}
    found_projects = search_bw_projects(
        headless=not args.headed,
        seen_keys=seen_keys,
    )

    saved: dict[str, BWProject] = {}
    for project in [*seen_projects, *found_projects]:
        merge_project(saved, project)
    save_seen_projects(saved.values(), args.seen_file)

    if args.csv_file:
        save_projects_csv(saved.values(), args.csv_file)

    new_count = sum(
        project_identity(project) not in seen_keys for project in found_projects
    )
    project_label = "project" if len(saved) == 1 else "projects"
    new_project_label = "project" if new_count == 1 else "projects"
    print(
        f"History contains {len(saved)} {project_label} total; "
        f"{new_count} new {new_project_label} this run."
    )


if __name__ == "__main__":
    main()
