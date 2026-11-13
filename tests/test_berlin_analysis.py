# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

import analyse.berlin_analysis as berlin_analysis
import analyse.brandenburg_analysis as brandenburg_analysis
from analyse.berlin_analysis import (
    BerlinProject,
    BerlinTheme,
    THEMES,
    _extract_page_projects,
    _is_within_date_window,
    _next_page_start,
    _search_url,
    _subtract_months,
    load_seen_projects,
    merge_project,
    parse_project_card,
    project_identity,
    save_projects_csv,
    save_seen_projects,
)


def test_theme_configuration_matches_brandenburg_exactly():
    """@spec REQ-12"""
    assert {
        theme.name: theme.keywords for theme in THEMES
    } == {
        theme.name: theme.keywords for theme in brandenburg_analysis.THEMES
    }


def test_search_url_encodes_keyword_and_start_offset():
    """@spec REQ-12"""
    assert _search_url("Künstliche Intelligenz", 10) == (
        "https://www.berlin.de/vergabeplattform/veroeffentlichungen/"
        "bekanntmachungen/?search=K%C3%BCnstliche+Intelligenz&start=10"
    )


def test_parse_project_card_maps_berlin_listing_fields():
    """@spec REQ-12"""
    assert parse_project_card(
        "IT-Sicherheitsberatung",
        "Online seit: 13.11.2026",
        {
            "Verfahrensart": "Offenes Verfahren (VgV)",
            "Ausführungsort": "10785 Berlin",
            "Ablauf Angebotsfrist": "16.12.2026, 13:30 Uhr",
        },
        "https://meinauftrag.rib.de/public/tender/123",
        "NIS2",
        "Cybersecurity",
    ) == BerlinProject(
        published="13.11.2026",
        deadline="16.12.2026, 13:30 Uhr",
        title="IT-Sicherheitsberatung",
        procedure="Offenes Verfahren (VgV)",
        location="10785 Berlin",
        keyword="NIS2",
        url="https://meinauftrag.rib.de/public/tender/123",
        theme="Cybersecurity",
    )


def test_parse_project_card_handles_participation_deadline_and_relative_url():
    """@spec REQ-12"""
    project = parse_project_card(
        "Security tender",
        "Online seit: 13.11.2026",
        {"Ablauf der Teilnahmefrist": "14.12.2026, 13:00 Uhr"},
        "/public/tender/456",
        "NIS2",
    )
    assert project is not None
    assert project.deadline == "14.12.2026, 13:00 Uhr"
    assert project.url == "https://www.berlin.de/public/tender/456"


def test_parse_project_card_skips_empty_title_and_rejects_missing_fields():
    """@spec REQ-12"""
    assert parse_project_card("", "", {}, None, "NIS2") is None
    with pytest.raises(ValueError, match="expected 'Online seit"):
        parse_project_card("Security tender", "Online seit: unknown", {}, "/detail", "NIS2")
    with pytest.raises(ValueError, match="has no details URL"):
        parse_project_card(
            "Security tender", "Online seit: 13.11.2026", {}, None, "NIS2"
        )


def test_extract_page_projects_reads_card_content_and_detail_link():
    """@spec REQ-12"""
    class FakeElement:
        def __init__(self, value):
            self.value = value

        def inner_text(self):
            return self.value

    class FakeDetailsButton:
        def get_attribute(self, name):
            assert name == "data-href"
            return "https://meinauftrag.rib.de/public/tender/123"

    class FakeCard:
        def locator(self, selector):
            values = {
                "h3.title": FakeElement("IT-Sicherheitsberatung"),
                ".card__footer .left": FakeElement("Online seit: 13.11.2026"),
                "dl.list--horizontal dt": FakeList(
                    [FakeElement("Verfahrensart"), FakeElement("Ausführungsort")]
                ),
                "dl.list--horizontal dd": FakeList(
                    [FakeElement("Offenes Verfahren"), FakeElement("Berlin")]
                ),
                "button[data-href]": FakeDetailsButton(),
            }
            return values[selector]

    class FakeList:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class FakePage:
        def locator(self, selector):
            assert selector == "ol.search-results article[data-offer]"
            return FakeList([FakeCard()])

    assert _extract_page_projects(FakePage(), "NIS2", "Cybersecurity") == [
        BerlinProject(
            "13.11.2026",
            "",
            "IT-Sicherheitsberatung",
            "Offenes Verfahren",
            "Berlin",
            "NIS2",
            "https://meinauftrag.rib.de/public/tender/123",
            "Cybersecurity",
        )
    ]


def test_pagination_reads_next_start_and_rejects_malformed_link():
    """@spec REQ-12"""
    class FakeLink:
        def __init__(self, href):
            self.href = href

        def count(self):
            return int(self.href is not None)

        def get_attribute(self, name):
            assert name == "href"
            return self.href

    class FakePage:
        def __init__(self, href):
            self.href = href

        def locator(self, selector):
            assert selector == (
                'nav.pagination a[title="Eine Seite weiter blättern"]'
            )
            return FakeLink(self.href)

    assert _next_page_start(FakePage("/bekanntmachungen/?start=10")) == 10
    assert _next_page_start(FakePage(None)) is None
    with pytest.raises(ValueError, match="Cannot read Berlin pagination"):
        _next_page_start(FakePage("/bekanntmachungen/?page=2"))


def test_publication_date_window_is_inclusive_and_rejects_bad_dates():
    """@spec REQ-12"""
    cutoff = date(2026, 8, 19)
    assert _is_within_date_window(
        BerlinProject("19.08.2026", "", "On cutoff", "", "", "", "/notice"),
        cutoff,
    )
    assert not _is_within_date_window(
        BerlinProject("18.08.2026", "", "Before cutoff", "", "", "", "/notice"),
        cutoff,
    )
    assert _subtract_months(date(2026, 10, 31), 2) == date(2026, 8, 31)
    with pytest.raises(ValueError, match="expected DD.MM.YYYY"):
        _is_within_date_window(
            BerlinProject("unknown", "", "Bad date", "", "", "", "/notice"),
            cutoff,
        )


def test_merge_project_deduplicates_by_url_and_combines_keywords_and_themes():
    """@spec REQ-12"""
    projects: dict[str, BerlinProject] = {}
    first = BerlinProject(
        "13.11.2026",
        "16.12.2026",
        "Security tender",
        "Open procedure",
        "Berlin",
        "NIS2; NIS2",
        "https://example.de/notice/1",
        "Cybersecurity; Cybersecurity",
    )
    second = BerlinProject(
        "13.11.2026",
        "16.12.2026",
        "Different title",
        "Open procedure",
        "Berlin",
        "SIEM",
        "https://example.de/notice/1",
        "Software",
    )

    merge_project(projects, first)
    merge_project(projects, second)

    assert len(projects) == 1
    merged = projects[project_identity(first)]
    assert merged.title == first.title
    assert merged.keyword == "NIS2; SIEM"
    assert merged.theme == "Cybersecurity; Software"


def test_history_persists_and_backs_up_only_changed_content(tmp_path: Path):
    """@spec REQ-08, REQ-12"""
    history = tmp_path / "seen_berlin.json"
    first = BerlinProject(
        "13.11.2026",
        "16.12.2026",
        "First",
        "Open procedure",
        "Berlin",
        "NIS2",
        "https://example.de/1",
        "Cybersecurity",
    )
    second = BerlinProject(
        "12.11.2026",
        "",
        "Second",
        "Open procedure",
        "Berlin",
        "SIEM",
        "https://example.de/2",
        "Cybersecurity",
    )

    save_seen_projects([first], history)
    first_content = history.read_text(encoding="utf-8")
    save_seen_projects([first, second, first], history)
    backup = Path(f"{history}.bk")
    assert backup.read_text(encoding="utf-8") == first_content
    assert load_seen_projects(history) == [first, second]

    backup_content = backup.read_text(encoding="utf-8")
    current_content = history.read_text(encoding="utf-8")
    save_seen_projects([first, second], history)
    assert history.read_text(encoding="utf-8") == current_content
    assert backup.read_text(encoding="utf-8") == backup_content


def test_load_seen_projects_rejects_non_list_json(tmp_path: Path):
    """@spec REQ-08, REQ-12"""
    history = tmp_path / "seen_berlin.json"
    history.write_text(json.dumps({"invalid": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="Expected a JSON list"):
        load_seen_projects(history)


def test_save_projects_csv_writes_portal_fields_and_backup(tmp_path: Path):
    """@spec REQ-12"""
    output = tmp_path / "berlin_results.csv"
    output.write_text("previous CSV", encoding="utf-8")
    save_projects_csv(
        [
            BerlinProject(
                "13.11.2026",
                "16.12.2026, 13:30 Uhr",
                "IT-Sicherheitsberatung",
                "Offenes Verfahren",
                "10785 Berlin",
                "NIS2",
                "https://example.de/notice/1",
                "Cybersecurity",
            )
        ],
        output,
    )

    assert Path(f"{output}.bk").read_text(encoding="utf-8") == "previous CSV"
    assert output.read_text(encoding="utf-8").splitlines() == [
        "published,deadline,title,procedure,location,theme,keyword,url",
        "13.11.2026,\"16.12.2026, 13:30 Uhr\",IT-Sicherheitsberatung,"
        "Offenes Verfahren,10785 Berlin,Cybersecurity,NIS2,"
        "https://example.de/notice/1",
    ]


def test_search_paginates_filters_seen_and_merges_keyword_matches(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """@spec REQ-12"""
    class FakeLocator:
        def __init__(self, page, href):
            self.page = page
            self.href = href

        def count(self):
            return int(self.page.start == 0)

        def get_attribute(self, name):
            assert name == "href"
            return self.href

    class FakePage:
        def __init__(self):
            self.start = 0
            self.visited = []

        def goto(self, url, wait_until):
            assert wait_until == "domcontentloaded"
            self.visited.append(url)
            self.start = int(url.split("start=")[-1])

        def locator(self, selector):
            assert selector == (
                'nav.pagination a[title="Eine Seite weiter blättern"]'
            )
            href = "/veroeffentlichungen/bekanntmachungen/?start=10"
            return FakeLocator(self, href)

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

    fake_playwright = FakePlaywright()
    monkeypatch.setattr(
        berlin_analysis,
        "sync_playwright",
        lambda: fake_playwright,
    )
    existing = BerlinProject(
        "13.11.2026",
        "",
        "Previously seen",
        "",
        "Berlin",
        "Datenanalyse",
        "https://example.de/seen",
        "AI",
    )
    fresh = BerlinProject(
        "13.11.2026",
        "",
        "Fresh project",
        "",
        "Berlin",
        "Datenanalyse",
        "https://example.de/fresh",
        "AI",
    )
    second_match = replace(fresh, keyword="Sprachmodell")

    def extract_projects(page, keyword, theme):
        projects_by_keyword = {
            "Datenanalyse": (
                [existing, fresh] if page.start == 0 else [],
            ),
            "Sprachmodell": (
                [second_match] if page.start == 0 else [],
            ),
        }
        return projects_by_keyword[keyword][0]

    monkeypatch.setattr(
        berlin_analysis,
        "_extract_page_projects",
        extract_projects,
    )
    results = berlin_analysis.search_berlin_projects(
        themes=(BerlinTheme("AI", ("Datenanalyse", "Sprachmodell")),),
        seen_keys={project_identity(existing)},
        published_since=date(2026, 8, 19),
    )

    assert [project.url for project in results] == [
        existing.url,
        fresh.url,
    ]
    assert results[1].keyword == "Datenanalyse; Sprachmodell"
    assert fake_playwright.browser.page.visited == [
        _search_url("Datenanalyse", 0),
        _search_url("Datenanalyse", 10),
        _search_url("Sprachmodell", 0),
        _search_url("Sprachmodell", 10),
    ]
    output = capsys.readouterr().out
    assert "Fresh project" in output
    assert "Previously seen" not in output


def test_main_uses_independent_default_history_and_reports_new_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """@spec REQ-08, REQ-12"""
    existing = BerlinProject(
        "13.11.2026", "", "Existing", "", "", "", "https://example.de/old"
    )
    fresh = BerlinProject(
        "13.11.2026", "", "Fresh", "", "", "", "https://example.de/new"
    )
    history_paths = []
    monkeypatch.setattr("sys.argv", ["analyse.berlin_analysis"])
    monkeypatch.setattr(
        berlin_analysis,
        "load_seen_projects",
        lambda path: history_paths.append(path) or [existing],
    )
    monkeypatch.setattr(
        berlin_analysis, "search_berlin_projects", lambda **kwargs: [fresh]
    )
    monkeypatch.setattr(
        berlin_analysis,
        "save_seen_projects",
        lambda projects, path: None,
    )

    berlin_analysis.main()

    assert history_paths == ["output/seen_berlin.json"]
    assert capsys.readouterr().out == (
        "History contains 2 projects total; 1 new project this run.\n"
    )
