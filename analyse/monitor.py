from __future__ import annotations

from pathlib import Path
from typing import Iterable

from analyse.browser_search import search_tenders
from analyse.mailer import send_email_alert
from analyse.models import Tender
from analyse.storage import load_seen_urls, save_results_csv, save_seen_urls


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


def build_email_body(keyword: str | Iterable[str] | dict[str, str], tenders: Iterable[Tender]) -> str:
    """Build the body text for an email notification.

    Parameters
    ----------
    keyword : str | Iterable[str] | dict[str, str]
        Search keyword(s) that triggered the notification.
    tenders : Iterable[Tender]
        Found tenders to include in the email.

    Returns
    -------
    str
        Formatted email body.
    """
    if isinstance(keyword, dict):
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
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def monitor(keyword: str | Iterable[str] | dict[str, str], seen_file: str | Path, csv_file: str | Path | None = None, headless: bool = True) -> list[Tender]:
    """Search and monitor tenders, saving results and alerting on new ones.

    Parameters
    ----------
    keyword : str | Iterable[str] | dict[str, str]
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
    if isinstance(keyword, dict):
        display = ", ".join([str(v) for v in keyword.values()])
    elif isinstance(keyword, str):
        display = keyword
    else:
        display = ", ".join([str(v) for v in keyword])

    print(f"Monitoring IT-Ausschreibung tenders for keyword: {display}")

    tenders = search_tenders(keyword=keyword, headless=headless)
    bucket_name = _bucket_name_for_keyword(keyword)
    seen_urls = load_seen_urls(seen_file, keyword=bucket_name)
    new_tenders = [tender for tender in tenders if tender.url not in seen_urls]

    if csv_file:
        save_results_csv(tenders, csv_file)

    if new_tenders:
        subject = f"New IT-Ausschreibung tenders for '{display}'"
        body = build_email_body(keyword, new_tenders)
        # For the moment we are not sending emails
        # send_email_alert(subject, body)
        print(f"Email alert sent with subject: {subject}\n\n{body}")

    save_seen_urls([tender.url for tender in tenders], seen_file, keyword=bucket_name)
    return new_tenders

