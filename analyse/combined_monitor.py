# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================

from __future__ import annotations

import csv
import os
import shutil
from contextlib import redirect_stdout
from dataclasses import dataclass, replace
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Callable, Iterable, TypeVar
from urllib.parse import urlsplit, urlunsplit

from analyse import (
    brandenburg_analysis,
    bw_analysis,
    dtvp_analysis,
    giz_analysis,
)
from analyse.browser_search import search_tenders_by_keyword
from analyse.models import Tender
from analyse.storage import save_seen_urls


@dataclass(frozen=True)
class CombinedNotice:
    source: str
    published: str
    deadline: str
    title: str
    publication_type: str
    client: str
    theme: str
    keyword: str
    url: str


@dataclass(frozen=True)
class SourceOutcome:
    source: str
    notices: tuple[CombinedNotice, ...]
    error: str = ""


T = TypeVar("T")

CSV_COLUMNS = (
    "source",
    "published",
    "deadline",
    "title",
    "publication_type",
    "client",
    "theme",
    "keyword",
    "url",
)

HISTORY_FILES = {
    "IT-Ausschreibung": "output/seen_it-ausschreibung.json",
    "DTVP": "output/seen_dtvp.json",
    "Brandenburg": "output/seen_brandenburg.json",
    "Baden-Württemberg": "output/seen_bw.json",
    "GIZ": "output/seen_giz.json",
}


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalize_date(value: str) -> str:
    normalized = _normalize_text(value)
    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            normalized = datetime.strptime(value.strip(), date_format).date().isoformat()
            break
        except ValueError:
            continue
    return normalized


def _normalize_url(value: str) -> str:
    if not value.strip():
        return ""
    parts = urlsplit(value.strip())
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/") or "/",
            parts.query,
            "",
        )
    )


def notice_identity(notice: CombinedNotice) -> tuple[str, str, str, str]:
    """Return the agreed cross-source identity fields. @spec REQ-10"""
    return (
        _normalize_text(notice.title),
        _normalize_date(notice.published),
        _normalize_text(notice.client),
        _normalize_url(notice.url),
    )


def _merge_values(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for item in value.split(";"):
            normalized = item.strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
    return "; ".join(merged)


def deduplicate_notices(notices: Iterable[CombinedNotice]) -> list[CombinedNotice]:
    """Merge matching notice metadata while preserving each source label. @spec REQ-10"""
    unique: dict[tuple[str, str, str, str], CombinedNotice] = {}
    for notice in notices:
        key = notice_identity(notice)
        existing = unique.get(key)
        if existing is None:
            unique[key] = notice
            continue
        unique[key] = replace(
            existing,
            source=_merge_values(existing.source, notice.source),
            theme=_merge_values(existing.theme, notice.theme),
            keyword=_merge_values(existing.keyword, notice.keyword),
        )
    return list(unique.values())


def _as_notice(
    record: object, source: str, theme: str = "", keyword: str = ""
) -> CombinedNotice:
    return CombinedNotice(
        source=source,
        published=str(getattr(record, "published", "")),
        deadline=str(getattr(record, "deadline", "")),
        title=str(getattr(record, "title", "")),
        publication_type=str(getattr(record, "publication_type", "")),
        client=str(getattr(record, "publisher", "")),
        theme=theme or str(getattr(record, "theme", "")),
        keyword=keyword or str(getattr(record, "keyword", "")),
        url=str(getattr(record, "url", "") or ""),
    )


def _run_history_source(
    source: str,
    seen_file: str | Path,
    load: Callable[[str | Path], list[T]],
    identity: Callable[[T], str],
    search: Callable[[set[str], bool], list[T]],
    merge: Callable[[dict[str, T], T], None],
    save: Callable[[Iterable[T], str | Path], None],
    headless: bool,
) -> SourceOutcome:
    found: list[T] = []
    notices: list[CombinedNotice] = []
    error_message = ""
    try:
        history = load(seen_file)
        seen_keys = {identity(record) for record in history}
        found = search(seen_keys, headless)
        notices = deduplicate_notices(_as_notice(item, source) for item in found)

        saved: dict[str, T] = {}
        for record in [*history, *found]:
            merge(saved, record)
        save(saved.values(), seen_file)
    except Exception as error:
        notices = deduplicate_notices(
            _as_notice(item, source) for item in found
        )
        error_message = f"{type(error).__name__}: {error}"
    return SourceOutcome(source, tuple(notices), error_message)


def _run_it_ausschreibung(
    headless: bool,
    keyword_groups: dict[str, tuple[str, ...]],
    seen_file: str | Path,
) -> SourceOutcome:
    """Search and update the main portal's independent history. @spec REQ-10"""
    source = "IT-Ausschreibung"
    found_by_keyword: dict[str, list[Tender]] = {}
    notices: list[CombinedNotice] = []
    error_message = ""
    theme_for_keyword = {
        keyword: theme
        for theme, keywords in keyword_groups.items()
        for keyword in keywords
    }
    try:
        keywords = [keyword for group in keyword_groups.values() for keyword in group]
        found_by_keyword = search_tenders_by_keyword(keywords, headless=headless)
        for theme, theme_keywords in keyword_groups.items():
            theme_by_url: dict[str, Tender] = {}
            for keyword in theme_keywords:
                for tender in found_by_keyword.get(keyword, []):
                    theme_by_url[tender.url] = tender
                    notices.append(_as_notice(tender, source, theme, keyword))
            save_seen_urls(
                (tender.url for tender in theme_by_url.values()),
                seen_file,
                keyword=theme,
            )
    except Exception as error:
        notices = [
            _as_notice(
                tender,
                source,
                theme_for_keyword.get(keyword, ""),
                keyword,
            )
            for keyword, tenders in found_by_keyword.items()
            for tender in tenders
        ]
        error_message = f"{type(error).__name__}: {error}"
    return SourceOutcome(
        source,
        tuple(deduplicate_notices(notices)),
        error_message,
    )


def _run_quietly(operation: Callable[[], SourceOutcome]) -> SourceOutcome:
    output = StringIO()
    with redirect_stdout(output):
        outcome = operation()
    for line in output.getvalue().splitlines():
        if line.startswith("Warning:"):
            print(line)
    return outcome


def _export_csv(notices: Iterable[CombinedNotice], output_file: str | Path) -> None:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, Path(f"{path}.bk"))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for notice in notices:
            writer.writerow({column: getattr(notice, column) for column in CSV_COLUMNS})


def run_combined_monitor(
    headless: bool = True,
    csv_file: str | Path | None = None,
    keyword_groups: dict[str, tuple[str, ...]] | None = None,
) -> int:
    """Run all portal searches and publish unique current-run notices. @spec REQ-10"""
    if keyword_groups is None:
        from analyse.cli import THEME_KEYWORDS

        keyword_groups = THEME_KEYWORDS

    history_files = dict(HISTORY_FILES)
    history_files["IT-Ausschreibung"] = os.getenv(
        "SEEN_FILE", history_files["IT-Ausschreibung"]
    )
    outcomes = [
        _run_quietly(
            lambda: _run_it_ausschreibung(
                headless,
                keyword_groups,
                history_files["IT-Ausschreibung"],
            )
        ),
        _run_quietly(
            lambda: _run_history_source(
                "DTVP",
                history_files["DTVP"],
                dtvp_analysis.load_seen_announcements,
                dtvp_analysis.announcement_identity,
                lambda seen, visible: dtvp_analysis.search_dtvp_announcements(
                    headless=visible, seen_keys=seen
                ),
                dtvp_analysis.merge_announcement,
                dtvp_analysis.save_seen_announcements,
                headless,
            ),
        ),
        _run_quietly(
            lambda: _run_history_source(
                "Brandenburg",
                history_files["Brandenburg"],
                brandenburg_analysis.load_seen_projects,
                brandenburg_analysis.project_identity,
                lambda seen, visible: brandenburg_analysis.search_brandenburg_projects(
                    headless=visible, seen_keys=seen
                ),
                brandenburg_analysis.merge_project,
                brandenburg_analysis.save_seen_projects,
                headless,
            ),
        ),
        _run_quietly(
            lambda: _run_history_source(
                "Baden-Württemberg",
                history_files["Baden-Württemberg"],
                bw_analysis.load_seen_projects,
                bw_analysis.project_identity,
                lambda seen, visible: bw_analysis.search_bw_projects(
                    headless=visible, seen_keys=seen
                ),
                bw_analysis.merge_project,
                bw_analysis.save_seen_projects,
                headless,
            ),
        ),
        _run_quietly(
            lambda: _run_history_source(
                "GIZ",
                history_files["GIZ"],
                giz_analysis.load_seen_announcements,
                giz_analysis.announcement_identity,
                lambda seen, visible: giz_analysis.search_giz_announcements(
                    headless=visible, seen_keys=seen
                ),
                giz_analysis.merge_announcement,
                giz_analysis.save_seen_announcements,
                headless,
            ),
        ),
    ]

    for outcome in outcomes:
        status = f"FAILED ({outcome.error})" if outcome.error else "OK"
        print(f"{outcome.source}: {status}; {len(outcome.notices)} current match(es).")

    unique_notices = deduplicate_notices(
        notice for outcome in outcomes for notice in outcome.notices
    )
    print(f"\n{len(unique_notices)} unique current-run notice(s):")
    for notice in unique_notices:
        match_details = [notice.source]
        if notice.theme:
            themes = ", ".join(item.strip() for item in notice.theme.split(";"))
            match_details.append(f"themes: {themes}")
        if notice.keyword:
            keywords = ", ".join(
                item.strip() for item in notice.keyword.split(";")
            )
            match_details.append(f"keywords: {keywords}")
        print(
            f"- [{' | '.join(match_details)}] {notice.title} | "
            f"{notice.published} | {notice.client}\n  {notice.url}"
        )

    export_failed = False
    if csv_file:
        try:
            _export_csv(unique_notices, csv_file)
        except OSError as error:
            export_failed = True
            print(f"Combined CSV export failed: {type(error).__name__}: {error}")

    return int(export_failed or any(outcome.error for outcome in outcomes))
