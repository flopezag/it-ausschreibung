from __future__ import annotations

from pathlib import Path
from typing import Iterable

from analyse.browser_search import search_tenders, search_tenders_by_keyword
from analyse.mailer import send_email_alert
from analyse.models import Tender
from analyse.storage import load_seen_urls, save_results_csv, save_seen_urls
from analyse.terminal import COLOR_RESET, KEYWORD_COLOR, THEME_COLOR


def _bucket_name_for_keyword(keyword: str | Iterable[str] | dict[str, str]) -> str:
    if isinstance(keyword, dict):
        return ", ".join([str(v) for v in keyword.values()])
    if isinstance(keyword, str):
        return keyword
    return ", ".join([str(v) for v in keyword])


def find_new_tenders(tenders: Iterable[Tender], seen_urls: set[str]) -> list[Tender]:
    """Filter out tenders that have already been seen.

    Parameters
    ----------
    tenders : Iterable[Tender]
        Tenders to check for new URLs.
    seen_urls : set[str]
        URLs that were already seen.

    Returns
    -------
    list[Tender]
        Tenders whose URLs are not in the seen set.
    """
    return [tender for tender in tenders if tender.url not in seen_urls]


def build_email_body(
    keyword: str | Iterable[str] | dict[str, str | Iterable[str]],
    tenders: Iterable[Tender],
    matched_keywords: dict[str, Iterable[str]] | None = None,
) -> str:
    """Build the body text for an email notification.

    Parameters
    ----------
    keyword : str | Iterable[str] | dict[str, str | Iterable[str]]
        Search keyword(s) that triggered the notification.
    tenders : Iterable[Tender]
        Found tenders to include in the email.

    Returns
    -------
    str
        Formatted email body.
    """
    if isinstance(keyword, dict) and any(
        not isinstance(value, str) for value in keyword.values()
    ):
        display = "; ".join(
            f"{theme}: {', '.join(str(item) for item in values)}"
            if not isinstance(values, str)
            else f"{theme}: {values}"
            for theme, values in keyword.items()
        )
    elif isinstance(keyword, dict):
        display = ", ".join([str(v) for v in keyword.values()])
    elif isinstance(keyword, str):
        display = keyword
    else:
        display = ", ".join([str(v) for v in keyword])

    lines = [
        f"New IT-Ausschreibung tenders found for keyword: {display}",
        "",
    ]

    for tender in tenders:
        lines.append(f"- {tender.title}")
        lines.append(f"  {tender.url}")
        if matched_keywords and tender.url in matched_keywords:
            matches = ", ".join(matched_keywords[tender.url])
            lines.append(f"  Matched keyword(s): {matches}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def monitor(
    keyword: str | Iterable[str] | dict[str, str | Iterable[str]],
    seen_file: str | Path,
    csv_file: str | Path | None = None,
    headless: bool = True,
) -> list[Tender]:
    """Search and monitor tenders, saving results and alerting on new ones.

    Parameters
    ----------
    keyword : str | Iterable[str] | dict[str, str | Iterable[str]]
        Search keyword(s) to use.
    seen_file : str | Path
        JSON file path for storing seen URLs.
    csv_file : str | Path | None, optional
        Optional CSV output file path.
    headless : bool, optional
        Whether to run the browser headless, by default True.

    Returns
    -------
    list[Tender]
        Newly discovered tenders not previously seen.
    """
    theme_groups = (
        {
            str(theme): [str(item) for item in values]
            for theme, values in keyword.items()
        }
        if isinstance(keyword, dict)
        and any(not isinstance(values, str) for values in keyword.values())
        else None
    )

    if theme_groups is not None:
        display = ", ".join(
            f"{theme}: {', '.join(values)}" for theme, values in theme_groups.items()
        )
    elif isinstance(keyword, dict):
        display = ", ".join([str(v) for v in keyword.values()])
    elif isinstance(keyword, str):
        display = keyword
    else:
        display = ", ".join([str(v) for v in keyword])

    print(f"Monitoring IT-Ausschreibung tenders for keyword: {display}")

    matched_keywords: dict[str, list[str]] = {}
    if theme_groups is None:
        tenders = search_tenders(keyword=keyword, headless=headless)
        bucket_name = _bucket_name_for_keyword(keyword)
        seen_urls = load_seen_urls(seen_file, keyword=bucket_name)
        new_tenders = [tender for tender in tenders if tender.url not in seen_urls]
        save_seen_urls(
            [tender.url for tender in tenders], seen_file, keyword=bucket_name
        )
    else:
        all_seen_urls = load_seen_urls(seen_file)
        tender_by_url: dict[str, Tender] = {}
        new_by_url: dict[str, Tender] = {}
        for theme, keywords in theme_groups.items():
            print(f"{THEME_COLOR}Monitoring theme: {theme}{COLOR_RESET}")
            for search_keyword in keywords:
                print(
                    f"{KEYWORD_COLOR}Monitoring keyword: "
                    f"{search_keyword}{COLOR_RESET}"
                )
            tenders_by_keyword = search_tenders_by_keyword(
                keyword=keywords, headless=headless
            )
            theme_tenders_by_url: dict[str, Tender] = {}
            for search_keyword, keyword_tenders in tenders_by_keyword.items():
                for tender in keyword_tenders:
                    theme_tenders_by_url[tender.url] = tender
                    matches = matched_keywords.setdefault(tender.url, [])
                    if search_keyword not in matches:
                        matches.append(search_keyword)
            theme_tenders = list(theme_tenders_by_url.values())
            theme_seen_urls = load_seen_urls(seen_file, keyword=theme) | all_seen_urls
            for tender in theme_tenders:
                tender_by_url[tender.url] = tender
                if tender.url not in theme_seen_urls:
                    new_by_url[tender.url] = tender
                all_seen_urls.add(tender.url)
            save_seen_urls(
                [tender.url for tender in theme_tenders], seen_file, keyword=theme
            )
        tenders = list(tender_by_url.values())
        new_tenders = list(new_by_url.values())

    if csv_file:
        save_results_csv(tenders, csv_file)

    if new_tenders:
        body = build_email_body(
            keyword,
            new_tenders,
            matched_keywords if theme_groups is not None else None,
        )
        print(f"New tender matches:\n\n{body}")

    return new_tenders
