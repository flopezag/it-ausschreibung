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
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Allows parsing and CSV tests without Playwright installed.
    sync_playwright = None


BRANDENBURG_SEARCH_URL = (
    "https://vergabemarktplatz.brandenburg.de/VMPCenter/common/project/"
    "search.do?method=showExtendedSearch&fromExternal=true"
)
BRANDENBURG_BASE_URL = "https://vergabemarktplatz.brandenburg.de"
SEARCH_LOOKBACK_MONTHS = 2
THEME_COLOR = "\033[96m"
KEYWORD_COLOR = "\033[93m"
COLOR_RESET = "\033[0m"


@dataclass(frozen=True)
class BrandenburgProject:
    published: str
    deadline: str
    title: str
    publication_type: str
    publisher: str
    keyword: str
    url: str | None = None
    theme: str = ""


@dataclass(frozen=True)
class BrandenburgTheme:
    name: str
    keywords: tuple[str, ...]


THEMES = (
    BrandenburgTheme(
        "AI",
        ("Datenanalyse", "Entscheidungsunterstützung", "Sprachmodell",
         "Künstliche Intelligenz", "Maschinelles Lernen", "Generative KI", "Bildverarbeitung"),
    ),
    BrandenburgTheme(
        "Quantum",
        ("Quantensoftware", "Quantenkommunikation", "Post-Quanten-Kryptographie",
         "Quantencomputing", "Quantencomputer", "Quantenalgorithmus", "Post-Quanten-Kryptographie"),
    ),
    BrandenburgTheme(
        "Cybersecurity",
        ("NIS2", "KRITIS", "SIEM", "Identitätsmanagement", "IT-Sicherheit", 
         "Informationssicherheit", "Penetrationstest", "Schwachstellenanalyse", "ISMS"),
    ),
    BrandenburgTheme(
        "Robotics",
        ("Autonome Navigation", "Cobot", "Missionsplanung", "Robotik", "Roboter", 
         "Inspektionsroboter", "Drohne", "Fahrerloses Transportsystem"),
    ),
    BrandenburgTheme(
        "Software",
        ("ECM", "CMS", "SBOM", "Identitätsmanagement", "Digitale Identität", 
         "Dokumentenmanagementsystem", "E-Akte", "DevSecOps", "Softwaretest", "Testautomatisierung"),
    ),
    BrandenburgTheme(
        "Cross-domain",
        ("Forschungsprojekt", "Demonstrator", "Prototyp", "Machbarkeitsstudie", "Reallabor",
         "Generative KI", "Quantencomputing", "Post-Quanten-Kryptographie", "Robotik", "DevSecOps"),
    ),
)


def project_identity(project: BrandenburgProject) -> str:
    if project.url:
        return project.url
    return "\x1f".join((project.title, project.published, project.publisher))


def _merge_metadata(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for item in value.split("; "):
            item = item.strip()
            if item and item not in merged:
                merged.append(item)
    return "; ".join(merged)


def merge_project(
    projects: dict[str, BrandenburgProject], project: BrandenburgProject
) -> None:
    key = project_identity(project)
    existing = projects.get(key)
    if existing is None:
        projects[key] = replace(
            project,
            keyword=_merge_metadata(project.keyword),
            theme=_merge_metadata(project.theme),
        )
        return

    merged_keyword = _merge_metadata(existing.keyword, project.keyword)
    merged_theme = _merge_metadata(existing.theme, project.theme)
    if merged_keyword != existing.keyword or merged_theme != existing.theme:
        projects[key] = replace(
            existing,
            keyword=merged_keyword,
            theme=merged_theme,
        )


def parse_project_row(
    cells: Sequence[str], keyword: str, href: str | None = None, theme: str = ""
) -> BrandenburgProject | None:
    if len(cells) < 5 or not cells[2].strip():
        return None

    return BrandenburgProject(
        published=cells[0].strip(),
        deadline=cells[1].strip(),
        title=cells[2].strip(),
        publication_type=cells[3].strip(),
        publisher=cells[4].strip(),
        keyword=keyword,
        url=urljoin(BRANDENBURG_BASE_URL, href) if href else None,
        theme=theme,
    )


def _extract_page_projects(
    page: Any, keyword: str, theme: str = ""
) -> list[BrandenburgProject]:
    projects: list[BrandenburgProject] = []
    for row in page.locator("main table tbody tr").all():
        cells = [cell.inner_text() for cell in row.locator("td").all()]
        href = None
        for link in row.locator("a[href]").all():
            candidate = link.get_attribute("href")
            if candidate and not candidate.startswith(("javascript:", "#")):
                href = candidate
                break

        project = parse_project_row(cells, keyword, href, theme)
        if project is not None:
            projects.append(project)
    return projects


def _subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _is_within_date_window(project: BrandenburgProject, since: date) -> bool:
    try:
        published = datetime.strptime(project.published, "%d.%m.%Y").date()
    except ValueError as error:
        raise ValueError(
            f"Cannot parse publication date {project.published!r} "
            f"for project {project.title!r}; expected DD.MM.YYYY."
        ) from error
    return published >= since


def _page_numbers(page: Any) -> tuple[int, int]:
    text = page.get_by_text(re.compile(r"Seite:\s*\d+\s+von\s+\d+")).inner_text()
    match = re.search(r"Seite:\s*(\d+)\s+von\s+(\d+)", text)
    if match is None:
        raise ValueError(f"Cannot read Brandenburg results pagination text: {text!r}")
    return int(match.group(1)), int(match.group(2))


def print_keyword_results(
    keyword: str, projects: Iterable[BrandenburgProject], theme: str = ""
) -> None:
    results = list(projects)
    if not results:
        print(f"No new Brandenburg tender found for theme {theme}, keyword: {keyword}.")
        print()
        return

    print(f"New Brandenburg tender found for theme {theme}, keyword: {keyword}")
    for project in results:
        print(
            f"- {project.title} | {project.published} | {project.publisher}"
        )
        if project.url:
            print(f"  Description: {project.url}")
        print()


def search_brandenburg_projects(
    themes: Iterable[BrandenburgTheme] = THEMES,
    headless: bool = True,
    seen_keys: set[str] | None = None,
    published_since: date | None = None,
) -> list[BrandenburgProject]:
    """Search Brandenburg tenders by configured themes and keywords."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install"
        )

    theme_list = [theme for theme in themes if theme.keywords]
    previously_seen = seen_keys or set()
    date_cutoff = published_since or _subtract_months(
        date.today(), SEARCH_LOOKBACK_MONTHS
    )
    if not theme_list:
        return []

    print(f"Including Brandenburg tenders published on or after {date_cutoff:%d.%m.%Y}.")
    unique: dict[str, BrandenburgProject] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(BRANDENBURG_SEARCH_URL, wait_until="domcontentloaded")
            page.get_by_role(
                "heading", name=re.compile(r"Ihre Suche lieferte")
            ).wait_for(state="visible", timeout=60000)
            page.get_by_text("Bitte warten", exact=True).first.wait_for(
                state="hidden", timeout=60000
            )
            for theme in theme_list:
                print(f"{THEME_COLOR}Monitoring Brandenburg theme: {theme.name}{COLOR_RESET}")
                for keyword in theme.keywords:
                    print(
                        f"{KEYWORD_COLOR}Monitoring Brandenburg keyword: "
                        f"{keyword}{COLOR_RESET}"
                    )
                    page.get_by_role("textbox", name="Suchbegriff").fill(keyword)
                    page.get_by_role("button", name="Suchen").click()
                    loading = page.get_by_text("Bitte warten", exact=True).first
                    loading.wait_for(state="visible", timeout=60000)
                    loading.wait_for(state="hidden", timeout=60000)
                    page.get_by_role(
                        "heading", name=re.compile(r"Ihre Suche lieferte")
                    ).wait_for(state="visible", timeout=60000)

                    keyword_results: dict[str, BrandenburgProject] = {}
                    current_page, total_pages = _page_numbers(page)
                    while True:
                        for project in _extract_page_projects(page, keyword, theme.name):
                            if not _is_within_date_window(project, date_cutoff):
                                continue
                            key = project_identity(project)
                            if key not in previously_seen:
                                merge_project(keyword_results, project)
                            merge_project(unique, project)

                        if current_page >= total_pages:
                            break

                        page.get_by_role("link", name="nächste Seite").click()
                        next_page = current_page + 1
                        page.wait_for_function(
                            "expected => document.body.innerText.includes("
                            "`Seite: ${expected} von`)",
                            arg=next_page,
                            timeout=60000,
                        )
                        current_page, total_pages = _page_numbers(page)

                    print_keyword_results(
                        keyword, keyword_results.values(), theme=theme.name
                    )
                print()
        finally:
            browser.close()

    return list(unique.values())


def load_seen_projects(seen_file: str | Path) -> list[BrandenburgProject]:
    path = Path(seen_file)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return []

    payload: Any = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")

    projects: list[BrandenburgProject] = []
    for raw_item in cast(list[object], payload):
        if not isinstance(raw_item, dict):
            raise ValueError(f"Expected project objects in {path}")
        item = cast(dict[str, Any], raw_item)
        projects.append(
            BrandenburgProject(
                published=str(item.get("published", "")),
                deadline=str(item.get("deadline", "")),
                title=str(item.get("title", "")),
                publication_type=str(item.get("publication_type", "")),
                publisher=str(item.get("publisher", "")),
                keyword=str(item.get("keyword", "")),
                url=str(item["url"]) if item.get("url") else None,
                theme=str(item.get("theme", "")),
            )
        )
    return projects


def backup_existing_file(file_path: str | Path) -> None:
    path = Path(file_path)
    if path.exists():
        shutil.copy2(path, Path(f"{path}.bk"))


def save_seen_projects(
    projects: Iterable[BrandenburgProject], seen_file: str | Path
) -> None:
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    unique: dict[str, BrandenburgProject] = {}
    for project in projects:
        merge_project(unique, project)

    content = json.dumps(
        [asdict(project) for project in unique.values()],
        indent=2,
        ensure_ascii=False,
    )
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    backup_existing_file(path)
    path.write_text(content, encoding="utf-8")


def save_projects_csv(
    projects: Iterable[BrandenburgProject], output_file: str | Path
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
                    project.publisher,
                    project.theme,
                    project.keyword,
                    project.url or "",
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Brandenburg's Vergabemarktplatz for tender announcements."
    )
    parser.add_argument(
        "--headed", action="store_true", help="Show the browser while searching."
    )
    parser.add_argument("--seen-file", default="output/seen_brandenburg.json")
    parser.add_argument(
        "--csv-file", help="Optionally export the saved announcement history as CSV."
    )
    args = parser.parse_args()

    seen_projects = load_seen_projects(args.seen_file)
    seen_keys = {project_identity(project) for project in seen_projects}
    found_projects = search_brandenburg_projects(
        headless=not args.headed,
        seen_keys=seen_keys,
    )

    saved: dict[str, BrandenburgProject] = {}
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
