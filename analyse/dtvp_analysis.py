from __future__ import annotations

import argparse
import calendar
import csv
import json
import re
import shutil
import time
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence, cast
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Allows parsing and CSV tests without Playwright installed.
    sync_playwright = None


DTVP_URL = "https://www.dtvp.de/Center/company/announcements/categoryOverview.do?method=showCategoryOverview"
DTVP_BASE_URL = "https://www.dtvp.de"
SEARCH_LOOKBACK_MONTHS = 2
THEME_COLOR = "\033[96m"
KEYWORD_COLOR = "\033[93m"
COLOR_RESET = "\033[0m"

CPV_DESCRIPTIONS = {
    "30000000-9": "Office and computing machinery, equipment and supplies except furniture and software packages",
    "32000000-3": "Radio, television, communication, telecommunication and related equipment",
    "34000000-7": "Transport equipment and auxiliary products to transportation",
    "35000000-4": "Security, fire-fighting, police and defence equipment",
    "38000000-5": "Laboratory, optical and precision equipments (excl. glasses)",
    "42000000-6": "Industrial machinery",
    "48000000-8": "Software package and information systems",
    "72000000-5": "IT services: consulting, software development, Internet and support",
    "73000000-2": "Research and development services and related consultancy services",
}


@dataclass(frozen=True)
class DtvpAnnouncement:
    published: str
    deadline: str
    title: str
    publication_type: str
    publisher: str
    keyword: str
    url: str | None = None
    theme: str = ""


@dataclass(frozen=True)
class DtvpTheme:
    name: str
    keywords: tuple[str, ...]
    cpv_codes: tuple[str, ...]


THEMES = (
    DtvpTheme(
        "AI",
        (
            "Künstliche Intelligenz",
            "Maschinelles Lernen",
            "Generative KI",
            "Large Language Model",
            "Computer Vision"
        ),
        ("48000000-8", "72000000-5", "73000000-2"),
    ),
    DtvpTheme(
        "Quantum",
        ("Quantencomputing", "Quantencomputer", "Quantenalgorithmus", "Quantensoftware"),
        ("30000000-9", "38000000-5", "48000000-8", "72000000-5", "73000000-2"),
    ),
    DtvpTheme(
        "Cybersecurity",
        (
            "IT-Sicherheit",
            "Informationssicherheit",
            "ISMS",
            "BSI IT-Grundschutz",
            "Penetrationstest",
            "SIEM",
            "CRA"
        ),
        ("48000000-8", "72000000-5", "32000000-3"),
    ),
    DtvpTheme(
        "Robotics",
        (
            "Robotik",
            "Robotersystem",
            "Inspektionsroboter",
            "Autonomer mobiler Roboter",
            "Drohne"
        ),
        (
            "42000000-6",
            "38000000-5",
            "48000000-8",
            "72000000-5",
            "73000000-2",
            "34000000-7",
            "35000000-4",
            "32000000-3"
        ),
    ),
    DtvpTheme(
        "Software",
        (
            "Dokumentenmanagementsystem",
            "E-Akte",
            "DevSecOps",
            "SBOM",
            "Testautomatisierung",
            "Digitale Identität"
        ),
        ("48000000-8", "72000000-5"),
    ),
)


def build_cpv_payload(cpv_codes: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    """Build the CPV objects expected by DTVP's search form."""
    return [{"code": code, "name": name} for code, name in cpv_codes]


def parse_announcement_row(
    cells: Sequence[str], keyword: str, href: str | None = None, theme: str = ""
) -> DtvpAnnouncement | None:
    """Convert one DTVP result row into an announcement record."""
    if len(cells) < 5 or not cells[2].strip():
        return None

    url = urljoin(DTVP_BASE_URL, href) if href else None
    return DtvpAnnouncement(
        published=cells[0].strip(),
        deadline=cells[1].strip(),
        title=cells[2].strip(),
        publication_type=cells[3].strip(),
        publisher=cells[4].strip(),
        keyword=keyword,
        url=url,
        theme=theme,
    )


def _extract_page_announcements(
    page: Any, keyword: str, theme: str = ""
) -> list[DtvpAnnouncement]:
    announcements: list[DtvpAnnouncement] = []

    for row in page.locator("#listTemplate tbody tr").all():
        cells = [cell.inner_text() for cell in row.locator("td").all()]
        href = None
        for link in row.locator("a[href]").all():
            candidate = link.get_attribute("href")
            if candidate and not candidate.startswith(("javascript:", "#")):
                href = candidate
                break

        announcement = parse_announcement_row(cells, keyword, href, theme)
        if announcement is not None:
            announcements.append(announcement)

    return announcements


def announcement_identity(announcement: DtvpAnnouncement) -> str:
    if announcement.url:
        return announcement.url
    return "\x1f".join((announcement.title, announcement.published, announcement.publisher))


def _merge_metadata(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for item in value.split("; "):
            item = item.strip()
            if item and item not in merged:
                merged.append(item)
    return "; ".join(merged)


def merge_announcement(
    announcements: dict[str, DtvpAnnouncement],
    announcement: DtvpAnnouncement,
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


def _is_within_date_window(announcement: DtvpAnnouncement, since: date) -> bool:
    try:
        published = datetime.strptime(announcement.published, "%d.%m.%Y").date()
    except ValueError as error:
        raise ValueError(
            f"Cannot parse publication date {announcement.published!r} "
            f"for announcement {announcement.title!r}; expected DD.MM.YYYY."
        ) from error
    return published >= since


def print_keyword_results(
    keyword: str, announcements: Iterable[DtvpAnnouncement], theme: str = ""
) -> None:
    results = list(announcements)
    if not results:
        if theme:
            print(f"No new ausschreibung found for theme {theme}, keyword: {keyword}.")
        else:
            print("No new ausschreibung found.")
        print()
        print()
        return

    if theme:
        print(f"New DTVP ausschreibung found for theme {theme}, keyword: {keyword}")
    else:
        print(f"New DTVP ausschreibung found for keyword: {keyword}")
    for announcement in results:
        print(f"- {announcement.title} | {announcement.published} | {announcement.publisher}")
        if announcement.url:
            print(f"  Description: {announcement.url}")
        print()
    print()


def _page_numbers(page: Any) -> tuple[int, int]:
    text = page.locator(".browsePagesText").inner_text()
    match = re.search(r"Seite:\s*(\d+)\s+von\s+(\d+)", text)
    if match is None:
        return 1, 1
    return int(match.group(1)), int(match.group(2))


def _dismiss_cookie_dialog(page: Any) -> None:
    for label in ("Ablehnen", "Reject all"):
        try:
            page.get_by_role("button", name=re.compile(label, re.IGNORECASE)).first.click(
                timeout=1500
            )
            return
        except Exception:
            continue


def search_dtvp_announcements(
    themes: Iterable[DtvpTheme] = THEMES,
    headless: bool = True,
    seen_keys: set[str] | None = None,
    published_since: date | None = None,
) -> list[DtvpAnnouncement]:
    """Search DTVP with each theme's keywords and CPVs within the date window."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install"
        )

    theme_list = [theme for theme in themes if theme.keywords]
    previously_seen = seen_keys or set()
    date_cutoff = published_since or _subtract_months(date.today(), SEARCH_LOOKBACK_MONTHS)
    if not theme_list:
        return []

    print(f"Including announcements published on or after {date_cutoff:%d.%m.%Y}.")
    print()
    unique: dict[str, DtvpAnnouncement] = {}
    run_started_at = time.perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            for theme in theme_list:
                cpv_payload = json.dumps(
                    build_cpv_payload(
                        (code, CPV_DESCRIPTIONS[code]) for code in theme.cpv_codes
                    )
                )
                print(f"{THEME_COLOR}Monitoring DTVP theme: {theme.name}{COLOR_RESET}")
                for keyword in theme.keywords:
                    print(
                        f"{KEYWORD_COLOR}Monitoring DTVP keyword: {keyword}{COLOR_RESET}"
                    )
                    keyword_started_at = time.perf_counter()
                    page.goto(DTVP_URL, wait_until="domcontentloaded")
                    _dismiss_cookie_dialog(page)
                    page.locator("#searchText").fill(keyword)
                    page.locator("#cpvCodes").evaluate(
                        "(element, value) => element.value = value", cpv_payload
                    )
                    page.locator("#searchStart").click()
                    page.locator("#listTemplate h2").first.wait_for(
                        state="visible", timeout=60000
                    )
                    results_loaded_at = time.perf_counter()

                    keyword_results: dict[str, DtvpAnnouncement] = {}
                    current_page, total_pages = _page_numbers(page)
                    page_count = 0
                    while True:
                        page_count += 1
                        for announcement in _extract_page_announcements(
                            page, keyword, theme.name
                        ):
                            if not _is_within_date_window(announcement, date_cutoff):
                                continue
                            if announcement_identity(announcement) not in previously_seen:
                                merge_announcement(keyword_results, announcement)
                            merge_announcement(unique, announcement)

                        if current_page >= total_pages:
                            break

                        page.locator("#nextPage").click()
                        next_page = current_page + 1
                        page.wait_for_function(
                            "expected => { const node = document.querySelector('.browsePagesText'); "
                            "return node && node.textContent.includes(`Seite: ${expected} von`); }",
                            arg=next_page,
                            timeout=60000,
                        )
                        current_page, total_pages = _page_numbers(page)
                    keyword_finished_at = time.perf_counter()
                    print_keyword_results(
                        keyword, keyword_results.values(), theme=theme.name
                    )
                    print(
                        f"Timing DTVP keyword {keyword!r}: "
                        f"search/setup/results wait "
                        f"{results_loaded_at - keyword_started_at:.2f}s; "
                        f"pagination/extraction "
                        f"{keyword_finished_at - results_loaded_at:.2f}s; "
                        f"{page_count} page(s), "
                        f"{keyword_finished_at - keyword_started_at:.2f}s total."
                    )
                print("\n\n")
        finally:
            browser.close()

    print(f"DTVP search completed in {time.perf_counter() - run_started_at:.2f}s.")
    return list(unique.values())


def load_seen_announcements(seen_file: str | Path) -> list[DtvpAnnouncement]:
    path = Path(seen_file)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return []

    payload: Any = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")

    announcements: list[DtvpAnnouncement] = []
    for raw_item in cast(list[object], payload):
        if not isinstance(raw_item, dict):
            raise ValueError(f"Expected announcement objects in {path}")
        item = cast(dict[str, Any], raw_item)
        announcements.append(
            DtvpAnnouncement(
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
    announcements: Iterable[DtvpAnnouncement], seen_file: str | Path
) -> None:
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    unique: dict[str, DtvpAnnouncement] = {}
    for announcement in announcements:
        merge_announcement(unique, announcement)

    backup_existing_file(path)
    path.write_text(
        json.dumps(
            [asdict(announcement) for announcement in unique.values()],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def save_announcements_csv(
    announcements: Iterable[DtvpAnnouncement], output_file: str | Path
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
    parser = argparse.ArgumentParser(description="Search DTVP announcements by keyword and CPV.")
    parser.add_argument("--headed", action="store_true", help="Show the browser while searching.")
    parser.add_argument("--seen-file", default="seen_dtvp.json")
    parser.add_argument("--csv-file", help="Optionally export the saved announcement history as CSV.")
    args = parser.parse_args()

    seen_announcements = load_seen_announcements(args.seen_file)
    seen_keys = {announcement_identity(announcement) for announcement in seen_announcements}
    found_announcements = search_dtvp_announcements(
        headless=not args.headed,
        seen_keys=seen_keys,
    )

    saved: dict[str, DtvpAnnouncement] = {}
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