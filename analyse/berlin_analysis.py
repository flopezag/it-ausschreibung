# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================
"""Search Berlin procurement announcements. @spec REQ-08, REQ-12"""

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
from typing import Any, Iterable, cast
from urllib.parse import urlencode, urljoin

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Allows parsing and CSV tests without Playwright installed.
    sync_playwright = None

from analyse.brandenburg_analysis import THEMES as BRANDENBURG_THEMES


BERLIN_SEARCH_URL = (
    "https://www.berlin.de/vergabeplattform/veroeffentlichungen/"
    "bekanntmachungen/"
)
BERLIN_BASE_URL = "https://www.berlin.de"
SEARCH_LOOKBACK_MONTHS = 2
THEME_COLOR = "\033[96m"
KEYWORD_COLOR = "\033[93m"
COLOR_RESET = "\033[0m"


@dataclass(frozen=True, slots=True)
class BerlinProject:
    published: str
    deadline: str
    title: str
    procedure: str
    location: str
    keyword: str
    url: str
    theme: str = ""


@dataclass(frozen=True, slots=True)
class BerlinTheme:
    name: str
    keywords: tuple[str, ...]


THEMES = tuple(
    BerlinTheme(theme.name, theme.keywords) for theme in BRANDENBURG_THEMES
)


def project_identity(project: BerlinProject) -> str:
    identity = project.url or "\x1f".join(
        (project.title, project.published, project.location)
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
    projects: dict[str, BerlinProject], project: BerlinProject
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


def parse_project_card(
    title: str,
    published_text: str,
    attributes: dict[str, str],
    detail_url: str | None,
    keyword: str,
    theme: str = "",
) -> BerlinProject | None:
    """Convert Berlin listing-card values into a project record. @spec REQ-12"""
    if not title.strip():
        return None

    published_match = re.search(
        r"Online seit:\s*(\d{2}\.\d{2}\.\d{4})", published_text
    )
    if published_match is None:
        raise ValueError(
            f"Cannot parse Berlin publication date for project {title!r}; "
            "expected 'Online seit: DD.MM.YYYY'."
        )
    if not detail_url:
        raise ValueError(f"Berlin announcement {title!r} has no details URL.")

    deadline = next(
        (
            value.strip()
            for label, value in attributes.items()
            if "Ablauf" in label and value.strip()
        ),
        "",
    )
    return BerlinProject(
        published=published_match.group(1),
        deadline=deadline,
        title=title.strip(),
        procedure=attributes.get("Verfahrensart", "").strip(),
        location=attributes.get("Ausführungsort", "").strip(),
        keyword=keyword,
        url=urljoin(BERLIN_BASE_URL, detail_url),
        theme=theme,
    )


def _extract_page_projects(
    page: Any, keyword: str, theme: str = ""
) -> list[BerlinProject]:
    projects: list[BerlinProject] = []
    cards = page.locator("ol.search-results article[data-offer]").all()
    for card in cards:
        title = card.locator("h3.title").inner_text()
        published_text = card.locator(".card__footer .left").inner_text()
        labels = card.locator("dl.list--horizontal dt").all()
        values = card.locator("dl.list--horizontal dd").all()
        attributes = {
            label.inner_text().strip(): value.inner_text().strip()
            for label, value in zip(labels, values, strict=True)
        }
        detail_url = card.locator("button[data-href]").get_attribute("data-href")
        project = parse_project_card(
            title,
            published_text,
            attributes,
            detail_url,
            keyword,
            theme,
        )
        if project is not None:
            projects.append(project)
    return projects


def _search_url(keyword: str, start: int = 0) -> str:
    query = urlencode({"search": keyword, "start": start})
    search_url = f"{BERLIN_SEARCH_URL}?{query}"
    return search_url


def _next_page_start(page: Any) -> int | None:
    next_link = page.locator(
        'nav.pagination a[title="Eine Seite weiter blättern"]'
    )
    if next_link.count() == 0:
        return None

    href = cast(str | None, next_link.get_attribute("href"))
    if not href:
        raise ValueError("Berlin pagination link has no href.")
    match = re.search(r"(?:[?&])start=(\d+)(?:&|#|$)", href)
    if match is None:
        raise ValueError(f"Cannot read Berlin pagination start from {href!r}.")

    start = int(match.group(1))
    return start


def _subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    result = date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
    return result


def _is_within_date_window(project: BerlinProject, since: date) -> bool:
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
    keyword: str, projects: Iterable[BerlinProject], theme: str = ""
) -> None:
    results = list(projects)
    if not results:
        print(
            f"No new Berlin tender found for theme {theme}, keyword: {keyword}."
        )
    else:
        print(f"New Berlin tender found for theme {theme}, keyword: {keyword}")
        for project in results:
            print(
                f"- {project.title} | {project.published} | "
                f"{project.procedure} | {project.location}"
            )
            print(f"  Description: {project.url}")
            print()


def search_berlin_projects(
    themes: Iterable[BerlinTheme] = THEMES,
    headless: bool = True,
    seen_keys: set[str] | None = None,
    published_since: date | None = None,
) -> list[BerlinProject]:
    """Search Berlin announcements by configured themes and keywords. @spec REQ-12"""
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
        "Including Berlin tenders published on or after "
        f"{date_cutoff:%d.%m.%Y}."
    )
    unique: dict[str, BerlinProject] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            for theme in theme_list:
                print(
                    f"{THEME_COLOR}Monitoring Berlin theme: "
                    f"{theme.name}{COLOR_RESET}"
                )
                for keyword in theme.keywords:
                    print(
                        f"{KEYWORD_COLOR}Monitoring Berlin keyword: "
                        f"{keyword}{COLOR_RESET}"
                    )
                    keyword_results: dict[str, BerlinProject] = {}
                    visited_starts: set[int] = set()
                    start: int | None = 0
                    while start is not None:
                        if start in visited_starts:
                            raise ValueError(
                                f"Berlin pagination repeated start offset {start}."
                            )
                        visited_starts.add(start)
                        page.goto(
                            _search_url(keyword, start),
                            wait_until="domcontentloaded",
                        )
                        for project in _extract_page_projects(
                            page, keyword, theme.name
                        ):
                            if not _is_within_date_window(project, date_cutoff):
                                continue
                            key = project_identity(project)
                            if key not in previously_seen:
                                merge_project(keyword_results, project)
                            merge_project(unique, project)
                        start = _next_page_start(page)

                    print_keyword_results(
                        keyword, keyword_results.values(), theme=theme.name
                    )
                print()
        finally:
            browser.close()

    return list(unique.values())


def load_seen_projects(seen_file: str | Path) -> list[BerlinProject]:
    """Load this portal's independent JSON history. @spec REQ-08, REQ-12"""
    path = Path(seen_file)
    projects: list[BerlinProject] = []
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
                    BerlinProject(
                        published=str(item.get("published", "")),
                        deadline=str(item.get("deadline", "")),
                        title=str(item.get("title", "")),
                        procedure=str(item.get("procedure", "")),
                        location=str(item.get("location", "")),
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
    projects: Iterable[BerlinProject], seen_file: str | Path
) -> None:
    """Persist this portal's independent JSON history. @spec REQ-08, REQ-12"""
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    unique: dict[str, BerlinProject] = {}
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
    projects: Iterable[BerlinProject], output_file: str | Path
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
                "procedure",
                "location",
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
                    project.procedure,
                    project.location,
                    project.theme,
                    project.keyword,
                    project.url,
                ]
            )


def main() -> None:
    """Run the Berlin search with its own history and optional CSV. @spec REQ-12"""
    parser = argparse.ArgumentParser(
        description=(
            "Search Berlin's Vergabeplattform for tender announcements."
        )
    )
    parser.add_argument(
        "--headed", action="store_true", help="Show the browser while searching."
    )
    parser.add_argument("--seen-file", default="seen_berlin.json")
    parser.add_argument(
        "--csv-file", help="Optionally export the saved announcement history as CSV."
    )
    args = parser.parse_args()

    seen_projects = load_seen_projects(args.seen_file)
    seen_keys = {project_identity(project) for project in seen_projects}
    found_projects = search_berlin_projects(
        headless=not args.headed,
        seen_keys=seen_keys,
    )

    saved: dict[str, BerlinProject] = {}
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
