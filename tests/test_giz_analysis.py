import json
from datetime import date
from pathlib import Path

import pytest

import analyse.giz_analysis as giz_analysis
from analyse.giz_analysis import (
    GIZAnnouncement,
    GIZTheme,
    THEMES,
    _is_within_date_window,
    _subtract_months,
    announcement_identity,
    load_seen_announcements,
    merge_announcement,
    parse_announcement_row,
    save_announcements_csv,
    save_seen_announcements,
)


def test_theme_configuration_contains_requested_keywords():
    assert {theme.name: theme.keywords for theme in THEMES} == {
        "AI": (
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
        "Cybersecurity": (
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
        "Software/data": (
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
    }


def test_parse_announcement_row_extracts_listing_data_and_url():
    assert parse_announcement_row(
        [
            "22.10.2026",
            "12.11.2026",
            "IT and strategic advisory services",
            "UVgO Ausschreibung",
            "Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH",
        ],
        "digital platform",
        "/Satellite/public/company/projectForwarding.do?pid=53330",
        "Software/data",
    ) == GIZAnnouncement(
        published="22.10.2026",
        deadline="12.11.2026",
        title="IT and strategic advisory services",
        publication_type="UVgO Ausschreibung",
        publisher="Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH",
        keyword="digital platform",
        url=(
            "https://ausschreibungen.giz.de/"
            "Satellite/public/company/projectForwarding.do?pid=53330"
        ),
        theme="Software/data",
    )


def test_parse_announcement_row_skips_empty_or_non_result_rows():
    assert parse_announcement_row(["", "", "   ", "", ""], "AI") is None
    assert parse_announcement_row(["only", "two"], "AI") is None


def test_publication_date_window_is_inclusive_and_reports_bad_dates():
    cutoff = date(2026, 8, 1)
    on_cutoff = GIZAnnouncement("01.08.2026", "", "On cutoff", "", "", "AI")
    before_cutoff = GIZAnnouncement("31.07.2026", "", "Too old", "", "", "AI")
    invalid = GIZAnnouncement("unknown", "", "Bad date", "", "", "AI")

    assert _is_within_date_window(on_cutoff, cutoff)
    assert not _is_within_date_window(before_cutoff, cutoff)
    with pytest.raises(ValueError, match="expected DD.MM.YYYY"):
        _is_within_date_window(invalid, cutoff)
    assert _subtract_months(date(2026, 10, 31), 2) == date(2026, 8, 31)


def test_merge_announcement_deduplicates_and_combines_search_metadata():
    announcements: dict[str, GIZAnnouncement] = {}
    first = GIZAnnouncement(
        "22.10.2026",
        "12.11.2026",
        "WIDU platform",
        "Ausschreibung",
        "GIZ",
        "digital platform",
        "https://giz.de/project/1",
        "Software/data",
    )
    repeated = GIZAnnouncement(
        "22.10.2026",
        "12.11.2026",
        "WIDU platform",
        "Ausschreibung",
        "GIZ",
        "data platform",
        "https://giz.de/project/1",
        "AI",
    )

    merge_announcement(announcements, first)
    merge_announcement(announcements, repeated)
    merge_announcement(announcements, first)

    merged = announcements[announcement_identity(first)]
    assert len(announcements) == 1
    assert merged.keyword == "digital platform; data platform"
    assert merged.theme == "Software/data; AI"


def test_search_uses_themes_filters_seen_old_results_and_walks_pages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    class FakeLocator:
        def __init__(self, page, kind):
            self.page = page
            self.kind = kind
            self.first = self

        def fill(self, value):
            self.page.current_keyword = value
            self.page.keywords.append(value)

        def click(self):
            if self.kind == "button":
                self.page.current_page = 1
            elif self.kind == "link":
                self.page.current_page += 1

        def wait_for(self, state, timeout):
            pass

        def inner_text(self):
            return f"Seite: {self.page.current_page} von 2"

    class FakePage:
        def __init__(self):
            self.keywords = []
            self.current_keyword = ""
            self.current_page = 1

        def goto(self, url, wait_until):
            assert url == giz_analysis.GIZ_SEARCH_URL
            assert wait_until == "domcontentloaded"

        def locator(self, selector):
            return FakeLocator(self, selector)

        def get_by_role(self, role, name):
            return FakeLocator(self, role)

        def wait_for_function(self, script, **kwargs):
            pass

    class FakeBrowser:
        def __init__(self):
            self.page = FakePage()

        def new_page(self):
            return self.page

        def close(self):
            pass

    class FakePlaywright:
        def __init__(self):
            self.chromium = self
            self.browser = FakeBrowser()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def launch(self, headless):
            assert headless
            return self.browser

    recent = GIZAnnouncement(
        "01.08.2026", "", "Recent", "Ausschreibung", "GIZ", "alpha",
        "https://giz.de/recent", "AI"
    )
    old = GIZAnnouncement(
        "31.07.2026", "", "Old", "Ausschreibung", "GIZ", "alpha",
        "https://giz.de/old", "AI"
    )
    previously_seen = GIZAnnouncement(
        "03.08.2026", "", "Seen", "Ausschreibung", "GIZ", "alpha",
        "https://giz.de/seen", "AI"
    )
    second_page = GIZAnnouncement(
        "04.08.2026", "", "Second page", "Ausschreibung", "GIZ", "alpha",
        "https://giz.de/second", "AI"
    )
    fake_playwright = FakePlaywright()
    monkeypatch.setattr(giz_analysis, "sync_playwright", lambda: fake_playwright)
    monkeypatch.setattr(
        giz_analysis,
        "_extract_page_announcements",
        lambda page, keyword, theme: (
            [recent, old, previously_seen]
            if page.current_page == 1
            else [second_page]
        ),
    )

    found = giz_analysis.search_giz_announcements(
        themes=(GIZTheme("AI", ("alpha", "beta")),),
        published_since=date(2026, 8, 1),
        seen_keys={announcement_identity(previously_seen)},
    )

    assert [item.title for item in found] == ["Recent", "Seen", "Second page"]
    assert fake_playwright.browser.page.keywords == ["alpha", "beta"]
    output = capsys.readouterr().out
    assert "Old" not in output
    assert "Seen" not in output
    assert "Recent" in output
    assert "Second page" in output
    assert "Monitoring GIZ theme: AI" in output


def test_seen_announcements_persist_and_backup_changed_history(tmp_path: Path):
    seen_file = tmp_path / "seen_giz.json"
    first = GIZAnnouncement(
        "22.10.2026",
        "12.11.2026",
        "WIDU platform",
        "Ausschreibung",
        "GIZ",
        "digital platform",
        "https://giz.de/project/1",
        "Software/data",
    )
    second = GIZAnnouncement(
        "21.10.2026",
        "09.11.2026",
        "Computing system",
        "Ausschreibung",
        "GIZ",
        "information system",
        "https://giz.de/project/2",
        "Software/data",
    )

    assert load_seen_announcements(seen_file) == []
    save_seen_announcements([first], seen_file)
    previous = seen_file.read_text(encoding="utf-8")
    save_seen_announcements([first, second, first], seen_file)

    assert Path(f"{seen_file}.bk").read_text(encoding="utf-8") == previous
    assert load_seen_announcements(seen_file) == [first, second]
    assert json.loads(seen_file.read_text(encoding="utf-8"))[0]["url"] == first.url


def test_save_announcements_csv_creates_backup_and_exports_fields(tmp_path: Path):
    output = tmp_path / "giz_results.csv"
    output.write_text("previous CSV", encoding="utf-8")
    save_announcements_csv(
        [
            GIZAnnouncement(
                "22.10.2026",
                "12.11.2026",
                "WIDU platform",
                "Ausschreibung",
                "GIZ",
                "digital platform",
                "https://giz.de/project/1",
                "Software/data",
            )
        ],
        output,
    )

    assert Path(f"{output}.bk").read_text(encoding="utf-8") == "previous CSV"
    assert output.read_text(encoding="utf-8").splitlines() == [
        "published,deadline,title,publication_type,publisher,theme,keyword,url",
        "22.10.2026,12.11.2026,WIDU platform,Ausschreibung,GIZ,Software/data,"
        "digital platform,https://giz.de/project/1",
    ]


def test_main_passes_custom_publication_cutoff(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    cutoffs = []
    monkeypatch.setattr(
        "sys.argv",
        [
            "analyse.giz_analysis",
            "--published-since",
            "2026-08-01",
            "--seen-file",
            str(tmp_path / "seen.json"),
        ],
    )
    monkeypatch.setattr(giz_analysis, "load_seen_announcements", lambda path: [])
    monkeypatch.setattr(giz_analysis, "save_seen_announcements", lambda items, path: None)
    monkeypatch.setattr(
        giz_analysis,
        "search_giz_announcements",
        lambda **kwargs: cutoffs.append(kwargs["published_since"]) or [],
    )

    giz_analysis.main()

    assert cutoffs == [date(2026, 8, 1)]
