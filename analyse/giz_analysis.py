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


GIZ_SEARCH_URL = (
    "https://ausschreibungen.giz.de/Satellite/common/project/search.do"
    "?method=showExtendedSearch&fromExternal=true"
)
GIZ_BASE_URL = "https://ausschreibungen.giz.de"
SEARCH_LOOKBACK_MONTHS = 2
THEME_COLOR = "\033[96m"
KEYWORD_COLOR = "\033[93m"
COLOR_RESET = "\033[0m"


@dataclass(frozen=True)
class GIZAnnouncement:
    published: str
    deadline: str
    title: str
    publication_type: str
    publisher: str
    keyword: str
    url: str | None = None
    theme: str = ""


@dataclass(frozen=True)
class GIZTheme:
    name: str
    keywords: tuple[str, ...]


THEMES = (
    GIZTheme(
        "AI",
        (
            "Artificial Intelligence",
            "AI",
            "machine learning",
            "digital transformation",
            "data governance",
            "data ecosystem",
            "data platform",
            "digital public infrastructure",
            "AI governance",
            "responsible AI",
            "AI policy",
            "open data",
            "digital skills",
        ),
    ),
    GIZTheme(
        "Cybersecurity",
        (
            "cybersecurity",
            "cyber security",
            "information security",
            "IT security",
            "digital security",
            "cyber capacity building",
            "critical infrastructure",
            "incident response",
            "data protection",
            "privacy",
            "digital resilience",
        ),
    ),
    GIZTheme(
        "Software/data",
        (
            "digital platform",
            "information system",
            "software development",
            "data management",
            "digital public goods",
            "open source",
            "interoperability",
            "digital identity",
            "e-government",
            "GovTech",
        ),
    ),
)


def parse_announcement_row(
    cells: Sequence[str], keyword: str, href: str | None = None, theme: str = ""
) -> GIZAnnouncement | None:
    """Convert one GIZ search result row into an announcement record."""
    if len(cells) < 5 or not cells[2].strip():
        return None

    return GIZAnnouncement(
        published=cells[0].strip(),
        deadline=cells[1].strip(),
        title=cells[2].strip(),
        publication_type=cells[3].strip(),
        publisher=cells[4].strip(),
        keyword=keyword,
        url=urljoin(GIZ_BASE_URL, href) if href else None,
        theme=theme,
    )


def _extract_page_announcements(
    page: Any, keyword: str, theme: str = ""
) -> list[GIZAnnouncement]:
    announcements: list[GIZAnnouncement] = []
    for row in page.locator("table tbody tr").all():
        cells = [cell.inner_text() for cell in row.locator("td").all()]
        href = None
        for link in row.locator("a[href]").all():
            candidate = link.get_attribute("href")
            if candidate and "projectForwarding.do" in candidate:
                href = candidate
                break

        announcement = parse_announcement_row(cells, keyword, href, theme)
        if announcement is not None:
            announcements.append(announcement)
    return announcements


def announcement_identity(announcement: GIZAnnouncement) -> str:
    if announcement.url:
        return announcement.url
    return "\x1f".join(
        (announcement.title, announcement.published, announcement.publisher)
    )


def _merge_metadata(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for item in value.split("; "):
            item = item.strip()
            if item and item not in merged:
                merged.append(item)
    return "; ".join(merged)


def merge_announcement(
    announcements: dict[str, GIZAnnouncement],
    announcement: GIZAnnouncement,
) -> None:
    key = announcement_identity(announcement)
    existing = announcements.get(key)
    if existing is None:
        announcements[key] = replace(
            announcement,
            keyword=_merge_metadata(announcement.keyword),
            theme=_merge_metadata(announcement.theme),
        )
        return

    merged_keyword = _merge_metadata(existing.keyword, announcement.keyword)
    merged_theme = _merge_metadata(existing.theme, announcement.theme)
    if merged_keyword != existing.keyword or merged_theme != existing.theme:
        announcements[key] = replace(
            existing,
            keyword=merged_keyword,
            theme=merged_theme,
        )


def _subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _is_within_date_window(announcement: GIZAnnouncement, since: date) -> bool:
    try:
        published = datetime.strptime(announcement.published, "%d.%m.%Y").date()
    except ValueError as error:
        raise ValueError(
            f"Cannot parse publication date {announcement.published!r} "
            f"for announcement {announcement.title!r}; expected DD.MM.YYYY."
        ) from error
    return published >= since


def _page_numbers(page: Any) -> tuple[int, int]:
    text = page.locator("body").inner_text()
    match = re.search(r"Seite:\s*(\d+)\s+von\s+(\d+)", text)
    if match is None:
        return 1, 1
    return int(match.group(1)), int(match.group(2))


def print_keyword_results(
    keyword: str, announcements: Iterable[GIZAnnouncement], theme: str = ""
) -> None:
    results = list(announcements)
    if not results:
        print(f"No new GIZ ausschreibung found for theme {theme}, keyword: {keyword}.")
        print()
        return

    print(f"New GIZ ausschreibung found for theme {theme}, keyword: {keyword}")
    for announcement in results:
        print(
            f"- {announcement.title} | {announcement.published} "
            f"| {announcement.publisher}"
        )
        if announcement.url:
            print(f"  Description: {announcement.url}")
        print()


def search_giz_announcements(
    themes: Iterable[GIZTheme] = THEMES,
    headless: bool = True,
    seen_keys: set[str] | None = None,
    published_since: date | None = None,
) -> list[GIZAnnouncement]:
    """Search GIZ with each configured keyword and filter by publication date."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && "
            "python -m playwright install"
        )

    theme_list = [theme for theme in themes if theme.keywords]
    previously_seen = seen_keys or set()
    date_cutoff = published_since or _subtract_months(
        date.today(), SEARCH_LOOKBACK_MONTHS
    )
    if not theme_list:
        return []

    print(f"Including GIZ announcements published on or after {date_cutoff:%d.%m.%Y}.")
    unique: dict[str, GIZAnnouncement] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(GIZ_SEARCH_URL, wait_until="domcontentloaded")
            page.get_by_role(
                "heading", name=re.compile(r"Nach Bekanntmachungen suchen")
            ).wait_for(state="visible", timeout=60000)

            for theme in theme_list:
                print(f"{THEME_COLOR}Monitoring GIZ theme: {theme.name}{COLOR_RESET}")
                for keyword in theme.keywords:
                    print(
                        f"{KEYWORD_COLOR}Monitoring GIZ keyword: "
                        f"{keyword}{COLOR_RESET}"
                    )
                    page.locator('input[name="searchText"]').fill(keyword)
                    page.get_by_role("button", name="Suchen").click()
                    page.wait_for_function(
                        "() => document.body.innerText.includes("
                        "'Ihre Suche lieferte Treffer') || "
                        "document.body.innerText.includes("
                        "'Es wurden keine passenden Bekanntmachungen gefunden')",
                        timeout=60000,
                    )

                    keyword_results: dict[str, GIZAnnouncement] = {}
                    current_page, total_pages = _page_numbers(page)
                    while True:
                        for announcement in _extract_page_announcements(
                            page, keyword, theme.name
                        ):
                            if not _is_within_date_window(announcement, date_cutoff):
                                continue
                            key = announcement_identity(announcement)
                            if key not in previously_seen:
                                merge_announcement(keyword_results, announcement)
                            merge_announcement(unique, announcement)

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


def load_seen_announcements(seen_file: str | Path) -> list[GIZAnnouncement]:
    path = Path(seen_file)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return []

    payload: Any = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")

    announcements: list[GIZAnnouncement] = []
    for raw_item in cast(list[object], payload):
        if not isinstance(raw_item, dict):
            raise ValueError(f"Expected announcement objects in {path}")
        item = cast(dict[str, Any], raw_item)
        announcements.append(
            GIZAnnouncement(
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
    return announcements


def backup_existing_file(file_path: str | Path) -> None:
    path = Path(file_path)
    if path.exists():
        shutil.copy2(path, Path(f"{path}.bk"))


def save_seen_announcements(
    announcements: Iterable[GIZAnnouncement], seen_file: str | Path
) -> None:
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    unique: dict[str, GIZAnnouncement] = {}
    for announcement in announcements:
        merge_announcement(unique, announcement)

    content = json.dumps(
        [asdict(announcement) for announcement in unique.values()],
        indent=2,
        ensure_ascii=False,
    )
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    backup_existing_file(path)
    path.write_text(content, encoding="utf-8")


def save_announcements_csv(
    announcements: Iterable[GIZAnnouncement], output_file: str | Path
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
        for announcement in announcements:
            writer.writerow(
                [
                    announcement.published,
                    announcement.deadline,
                    announcement.title,
                    announcement.publication_type,
                    announcement.publisher,
                    announcement.theme,
                    announcement.keyword,
                    announcement.url or "",
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search GIZ's Vergabemarktplatz for tender announcements."
    )
    parser.add_argument("--headed", action="store_true", help="Show the browser.")
    parser.add_argument("--seen-file", default="seen_giz.json")
    parser.add_argument("--csv-file", help="Optionally export announcement history as CSV.")
    parser.add_argument(
        "--published-since",
        type=date.fromisoformat,
        help="Include announcements published on or after YYYY-MM-DD "
        "(default: last two calendar months).",
    )
    args = parser.parse_args()

    seen_announcements = load_seen_announcements(args.seen_file)
    seen_keys = {
        announcement_identity(announcement) for announcement in seen_announcements
    }
    found_announcements = search_giz_announcements(
        headless=not args.headed,
        seen_keys=seen_keys,
        published_since=args.published_since,
    )

    saved: dict[str, GIZAnnouncement] = {}
    for announcement in [*seen_announcements, *found_announcements]:
        merge_announcement(saved, announcement)
    save_seen_announcements(saved.values(), args.seen_file)

    if args.csv_file:
        save_announcements_csv(saved.values(), args.csv_file)

    new_count = sum(
        announcement_identity(announcement) not in seen_keys
        for announcement in found_announcements
    )
    announcement_label = "announcement" if len(saved) == 1 else "announcements"
    new_announcement_label = "announcement" if new_count == 1 else "announcements"
    print(
        f"History contains {len(saved)} {announcement_label} total; "
        f"{new_count} new {new_announcement_label} this run."
    )


if __name__ == "__main__":
    main()
