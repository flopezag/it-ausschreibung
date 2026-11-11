from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urljoin
from typing import Iterable

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Allows unit tests for non-browser logic without Playwright installed.
    sync_playwright = None

from analyse.models import Tender

BASE_URL = "https://www.it-ausschreibung.de"
SEARCH_URL = f"{BASE_URL}/ausschreibungen"
PUBLISHED_DATE_PATTERN = re.compile(
    r"(?:Öffentliche|Gewerbliche)\s+Ausschreibung\s+vom\s+(\d{2}\.\d{2}\.\d{4})"
)
DEADLINE_PATTERN = re.compile(r"Angebotsfrist:\s*(\d{2}\.\d{2}\.\d{4})")
PUBLICATION_TYPE_PATTERN = re.compile(
    r"(Öffentliche|Gewerbliche)\s+Ausschreibung"
)


def parse_tender_summary(summary: str) -> tuple[str, str, str]:
    """Extract publication date, deadline, and type from a result summary. @spec REQ-10"""
    published_match = PUBLISHED_DATE_PATTERN.search(summary)
    deadline_match = DEADLINE_PATTERN.search(summary)
    type_match = PUBLICATION_TYPE_PATTERN.search(summary)
    return (
        published_match.group(1) if published_match else "",
        deadline_match.group(1) if deadline_match else "",
        f"{type_match.group(1)} Ausschreibung" if type_match else "",
    )


def enrich_tenders_with_client_address(
    browser, tenders: Iterable[Tender]
) -> list[Tender]:
    """Read the publicly displayed Auftraggeber address from each detail page. @spec REQ-10"""
    detail_page = browser.new_page()
    enriched: list[Tender] = []
    try:
        for tender in tenders:
            detail_page.goto(tender.url, wait_until="domcontentloaded")
            addresses = detail_page.locator("section.card-ita address").all()
            address = " ".join(addresses[0].inner_text().split()) if addresses else ""
            if not address:
                print(
                    "Warning: public Auftraggeber address unavailable for "
                    f"{tender.title}: {tender.url}"
                )
            enriched.append(replace(tender, publisher=address))
    finally:
        detail_page.close()
    return enriched


def extract_tenders_from_page(page, base_url: str = BASE_URL) -> list[Tender]:
    """Extract tender links from the current Playwright page.

    @spec REQ-01, REQ-10

    Only links matching /ausschreibung/<id>/<slug> are accepted.
    Duplicates are removed by URL.

    Parameters
    ----------
    page : object
        Playwright page object to inspect.
    base_url : str, optional
        Base URL used to resolve relative links, by default BASE_URL.

    Returns
    -------
    list[Tender]
        Unique tenders with publication metadata extracted from the page.
    """
    unique: dict[str, Tender] = {}

    for link in page.locator("a[href*='/ausschreibung/']").all():
        title = link.inner_text().strip()
        href = link.get_attribute("href")

        if not title or not href:
            continue

        url = urljoin(base_url, href)

        path = url.replace(base_url, "")
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[0] == "ausschreibung" and parts[1].isdigit():
            summary = link.locator("xpath=../following-sibling::p[1]").inner_text()
            published, deadline, publication_type = parse_tender_summary(summary)
            unique[url] = Tender(
                title=title,
                url=url,
                published=published,
                deadline=deadline,
                publication_type=publication_type,
            )

    return list(unique.values())


def _normalize_keywords(keyword: str | Iterable[str] | dict[str, str]) -> list[str]:
    if isinstance(keyword, dict):
        return [value for value in keyword.values() if isinstance(value, str) and value]
    if isinstance(keyword, str):
        return [keyword] if keyword else []
    return [value for value in keyword if isinstance(value, str) and value]


def search_tenders_by_keyword(
    keyword: str | Iterable[str] | dict[str, str], headless: bool = True
) -> dict[str, list[Tender]]:
    """Search tenders, preserving matches and public client addresses."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install"
        )

    keywords = _normalize_keywords(keyword)
    if not keywords:
        return {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            results: dict[str, list[Tender]] = {}
            for kw in keywords:
                page = browser.new_page()
                page.goto(SEARCH_URL, wait_until="domcontentloaded")

                for button_name in ("Reject all", "Ablehnen", "Save + Exit"):
                    try:
                        page.get_by_role("button", name=button_name).first.click(timeout=1500)
                        break
                    except Exception:
                        pass

                page.locator("input[type='text']").first.fill(kw)
                page.get_by_role("button", name="Suche").first.click()
                page.wait_for_load_state("networkidle")
                results[kw] = extract_tenders_from_page(page)
                page.close()

            unique_by_url: dict[str, Tender] = {}
            for keyword_tenders in results.values():
                for tender in keyword_tenders:
                    unique_by_url[tender.url] = tender
            enriched = enrich_tenders_with_client_address(
                browser, unique_by_url.values()
            )
            enriched_by_url = {tender.url: tender for tender in enriched}
            results = {
                keyword: [
                    enriched_by_url[tender.url] for tender in keyword_tenders
                ]
                for keyword, keyword_tenders in results.items()
            }
        finally:
            browser.close()
    return results


def search_tenders(
    keyword: str | Iterable[str] | dict[str, str], headless: bool = True
) -> list[Tender]:
    """Search tenders on it-ausschreibung.de and deduplicate URLs."""
    results_by_keyword = search_tenders_by_keyword(keyword, headless=headless)
    unique: dict[str, Tender] = {}
    for tenders in results_by_keyword.values():
        for tender in tenders:
            unique[tender.url] = tender
    return list(unique.values())
