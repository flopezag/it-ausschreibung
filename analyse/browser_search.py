from __future__ import annotations

from urllib.parse import urljoin
from typing import Iterable

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Allows unit tests for non-browser logic without Playwright installed.
    sync_playwright = None

from analyse.models import Tender

BASE_URL = "https://www.it-ausschreibung.de"
SEARCH_URL = f"{BASE_URL}/ausschreibungen"


def extract_tenders_from_page(page, base_url: str = BASE_URL) -> list[Tender]:
    """Extract tender links from the current Playwright page.

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
        Unique tenders extracted from the page.
    """
    unique: dict[str, str] = {}

    for link in page.locator("a[href*='/ausschreibung/']").all():
        title = link.inner_text().strip()
        href = link.get_attribute("href")

        if not title or not href:
            continue

        url = urljoin(base_url, href)

        path = url.replace(base_url, "")
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[0] == "ausschreibung" and parts[1].isdigit():
            unique[url] = title

    return [Tender(title=title, url=url) for url, title in unique.items()]


def search_tenders(keyword: str | Iterable[str] | dict[str, str], headless: bool = True) -> list[Tender]:
    """Search tenders on it-ausschreibung.de.

    Parameters
    ----------
    keyword : str | Iterable[str] | dict[str, str]
        Keyword or keywords to search for.
    headless : bool, optional
        Whether to run the browser in headless mode, by default True.

    Returns
    -------
    list[Tender]
        Tenders matching the search criteria.
    """
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install"
        )

    if isinstance(keyword, dict):
        keywords = [str(v) for v in keyword.values() if isinstance(v, str) and v]
    elif isinstance(keyword, str):
        keywords = [keyword]
    else:
        keywords = [str(v) for v in keyword if isinstance(v, str) and v]

    if not keywords:
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        unique: dict[str, str] = {}

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

            for tender in extract_tenders_from_page(page):
                unique[tender.url] = tender.title

            page.close()

        browser.close()
    return [Tender(title=title, url=url) for url, title in unique.items()]
