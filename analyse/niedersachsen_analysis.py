# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================
"""Search Niedersachsen procurement announcements. @spec REQ-08, REQ-13"""

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

from analyse.bw_analysis import THEMES as BW_THEMES


NIEDERSACHSEN_SEARCH_URL = (
    "https://vergabe.niedersachsen.de/Satellite/company/announcements/"
    "categoryOverview.do?method=showCategoryOverview"
)
NIEDERSACHSEN_BASE_URL = "https://vergabe.niedersachsen.de"
SEARCH_LOOKBACK_MONTHS = 2
THEME_COLOR = "\033[96m"
KEYWORD_COLOR = "\033[93m"
COLOR_RESET = "\033[0m"


@dataclass(frozen=True, slots=True)
class NiedersachsenProject:
    published: str
    deadline: str
    title: str
    publication_type: str
    contracting_rule: str
    publisher: str
    keyword: str
    url: str
    theme: str = ""


@dataclass(frozen=True, slots=True)
class NiedersachsenTheme:
    name: str
    keywords: tuple[str, ...]


THEMES = tuple(
    NiedersachsenTheme(theme.name, theme.keywords) for theme in BW_THEMES
)


def project_identity(project: NiedersachsenProject) -> str:
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


def merge_project(
    projects: dict[str, NiedersachsenProject],
    project: NiedersachsenProject,
) -> None:
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


def parse_project_row(
    cells: Sequence[str],
    keyword: str,
    href: str | None = None,
    theme: str = "",
) -> NiedersachsenProject | None:
    """Convert one Niedersachsen result row into a project. @spec REQ-13"""
    if len(cells) < 5 or not cells[2].strip():
        return None
    if not href:
        raise ValueError(
            f"Niedersachsen announcement {cells[2].strip()!r} has no detail URL."
        )

    type_parts = [part.strip() for part in cells[3].splitlines() if part.strip()]
    contracting_rule = type_parts[0] if len(type_parts) > 1 else ""
    publication_type = " ".join(type_parts[1:]) if len(type_parts) > 1 else (
        type_parts[0] if type_parts else ""
    )
    return NiedersachsenProject(
        published=cells[0].strip(),
        deadline=cells[1].strip(),
        title=cells[2].strip(),
        publication_type=publication_type,
        contracting_rule=contracting_rule,
        publisher=cells[4].strip(),
        keyword=keyword,
        url=urljoin(NIEDERSACHSEN_BASE_URL, href),
        theme=theme,
    )


def _extract_page_projects(
    page: Any, keyword: str, theme: str = ""
) -> list[NiedersachsenProject]:
    projects: list[NiedersachsenProject] = []
    rows = page.locator("table.csx-new-table tbody tr").all()
    for row in rows:
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
    result = date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
    return result


def _is_within_date_window(
    project: NiedersachsenProject, since: date
) -> bool:
    try:
        published = datetime.strptime(project.published, "%d.%m.%Y").date()
    except ValueError as error:
        raise ValueError(
            f"Cannot parse publication date {project.published!r} "
            f"for project {project.title!r}; expected DD.MM.YYYY."
        ) from error
    is_within = published >= since
    return is_within


def _page_numbers(page: Any) -> tuple[int, int]:
    text = page.locator(".browsePagesText").inner_text()
    match = re.search(r"Seite:\s*(\d+)\s+von\s+(\d+)", text)
    if match is None:
        raise ValueError(
            f"Cannot read Niedersachsen result pagination text: {text!r}"
        )
    current_page, total_pages = (int(value) for value in match.groups())
    return current_page, total_pages


def _configure_search_form(page: Any, keyword: str) -> None:
    page.goto(NIEDERSACHSEN_SEARCH_URL, wait_until="domcontentloaded")
    page.locator("#alle2").evaluate("(checkbox) => { checkbox.checked = false; }")
    page.locator("#selectedPublicationTypesTender").check()
    page.locator("#searchText").fill(keyword)
    page.locator(
        "form#masterForm[action*='searchExtended'] input[type='submit']"
    ).click()
    page.wait_for_load_state("domcontentloaded", timeout=60000)


def print_keyword_results(
    keyword: str,
    projects: Iterable[NiedersachsenProject],
    theme: str = "",
) -> None:
    results = list(projects)
    if not results:
        print(
            "No new Niedersachsen tender found for "
            f"theme {theme}, keyword: {keyword}."
        )
    else:
        print(
            f"New Niedersachsen tender found for theme {theme}, keyword: {keyword}"
        )
        for project in results:
            print(
                f"- {project.title} | {project.published} | "
                f"{project.publication_type} | {project.publisher}"
            )
            print(f"  Description: {project.url}")
            print()


def search_niedersachsen_projects(
    themes: Iterable[NiedersachsenTheme] = THEMES,
    headless: bool = True,
    seen_keys: set[str] | None = None,
    published_since: date | None = None,
) -> list[NiedersachsenProject]:
    """Search active Niedersachsen tenders by configured themes. @spec REQ-13"""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && "
            "python -m playwright install"
        )

    theme_list = [theme for theme in themes if theme.keywords]
    if not theme_list:
        return []

    previously_seen = seen_keys if seen_keys is not None else set[str]()
    date_cutoff = published_since or _subtract_months(
        date.today(), SEARCH_LOOKBACK_MONTHS
    )
    print(
        "Including Niedersachsen tenders published on or after "
        f"{date_cutoff:%d.%m.%Y}."
    )
    unique: dict[str, NiedersachsenProject] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            for theme in theme_list:
                print(
                    f"{THEME_COLOR}Monitoring Niedersachsen theme: "
                    f"{theme.name}{COLOR_RESET}"
                )
                for keyword in theme.keywords:
                    print(
                        f"{KEYWORD_COLOR}Monitoring Niedersachsen keyword: "
                        f"{keyword}{COLOR_RESET}"
                    )
                    _configure_search_form(page, keyword)
                    keyword_results: dict[str, NiedersachsenProject] = {}
                    current_page, total_pages = _page_numbers(page)
                    while current_page <= total_pages:
                        for project in _extract_page_projects(
                            page, keyword, theme.name
                        ):
                            if not _is_within_date_window(project, date_cutoff):
                                continue
                            key = project_identity(project)
                            if key not in previously_seen:
                                merge_project(keyword_results, project)
                            merge_project(unique, project)

                        if current_page >= total_pages:
                            break

                        next_page = current_page + 1
                        next_link = page.locator(
                            '.browseForward[title="nächste Seite"]'
                        )
                        if next_link.count() == 0:
                            raise ValueError(
                                "Niedersachsen pagination ended before page "
                                f"{total_pages}."
                            )
                        next_link.click()
                        page.wait_for_function(
                            "expected => document.querySelector("
                            "'.browsePagesText')?.innerText.includes("
                            "`Seite: ${expected} von`)",
                            arg=next_page,
                            timeout=60000,
                        )
                        current_page, total_pages = _page_numbers(page)
                        if current_page != next_page:
                            raise ValueError(
                                "Niedersachsen pagination did not advance to "
                                f"page {next_page}."
                            )

                    print_keyword_results(
                        keyword, keyword_results.values(), theme=theme.name
                    )
                print()
        finally:
            browser.close()

    return list(unique.values())


def load_seen_projects(seen_file: str | Path) -> list[NiedersachsenProject]:
    """Load this portal's independent JSON history. @spec REQ-08, REQ-13"""
    path = Path(seen_file)
    projects: list[NiedersachsenProject] = []
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
                    NiedersachsenProject(
                        published=str(item.get("published", "")),
                        deadline=str(item.get("deadline", "")),
                        title=str(item.get("title", "")),
                        publication_type=str(item.get("publication_type", "")),
                        contracting_rule=str(item.get("contracting_rule", "")),
                        publisher=str(item.get("publisher", "")),
                        keyword=str(item.get("keyword", "")),
                        url=str(item.get("url", "")),
                        theme=str(item.get("theme", "")),
                    )
                )
    return projects


def backup_existing_file(file_path: str | Path) -> None:
    path = Path(file_path)
    if path.exists():
        shutil.copy2(path, Path(f"{path}.bk"))


def save_seen_projects(
    projects: Iterable[NiedersachsenProject], seen_file: str | Path
) -> None:
    """Persist this portal's independent JSON history. @spec REQ-08, REQ-13"""
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    unique: dict[str, NiedersachsenProject] = {}
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
    projects: Iterable[NiedersachsenProject], output_file: str | Path
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
                "contracting_rule",
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
                    project.contracting_rule,
                    project.publisher,
                    project.theme,
                    project.keyword,
                    project.url,
                ]
            )


def main() -> None:
    """Run Niedersachsen search with its own history and optional CSV. @spec REQ-13"""
    parser = argparse.ArgumentParser(
        description=(
            "Search Niedersachsen's Vergabeplattform for current tenders."
        )
    )
    parser.add_argument(
        "--headed", action="store_true", help="Show the browser while searching."
    )
    parser.add_argument("--seen-file", default="seen_niedersachsen.json")
    parser.add_argument(
        "--csv-file", help="Optionally export the saved announcement history as CSV."
    )
    args = parser.parse_args()

    seen_projects = load_seen_projects(args.seen_file)
    seen_keys = {project_identity(project) for project in seen_projects}
    found_projects = search_niedersachsen_projects(
        headless=not args.headed,
        seen_keys=seen_keys,
    )

    saved: dict[str, NiedersachsenProject] = {}
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
