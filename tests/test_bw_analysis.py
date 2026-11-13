# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import analyse.brandenburg_analysis as brandenburg_analysis
import analyse.bw_analysis as bw_analysis
from analyse.bw_analysis import (
    BWProject,
    BWTheme,
    THEMES,
    _extract_page_projects,
    _is_within_date_window,
    _project_detail_url,
    _search_url,
    _subtract_months,
    load_seen_projects,
    merge_project,
    parse_project_row,
    project_identity,
    save_projects_csv,
    save_seen_projects,
)


def test_theme_configuration_matches_brandenburg_exactly():
    """@spec REQ-11"""
    assert {
        theme.name: theme.keywords
        for theme in THEMES
    } == {
        theme.name: theme.keywords
        for theme in brandenburg_analysis.THEMES
    }


def test_search_url_targets_current_tenders_and_encodes_keyword():
    """@spec REQ-11"""
    assert _search_url("Post-Quanten-Kryptographie") == (
        "https://vergabe.landbw.de/NetServer/PublicationSearchControllerServlet"
        "?function=Search&Category=InvitationToTender"
        "&Searchkey=Post-Quanten-Kryptographie"
    )


def test_project_detail_url_uses_row_identifier_and_category():
    """@spec REQ-11"""
    assert _project_detail_url("notice-123", "InvitationToTender") == (
        "https://vergabe.landbw.de/NetServer/PublicationControllerServlet"
        "?function=Detail&TOID=notice-123&Category=InvitationToTender"
    )
    assert _project_detail_url(None, "InvitationToTender") is None


def test_parse_project_row_maps_all_portal_columns():
    """@spec REQ-11"""
    assert parse_project_row(
        [
            "10.11.2026",
            "IT-Sicherheitsberatung (BW-1)",
            "Ministerium für Beispiel",
            "Offenes Verfahren",
            "UVgO/VgV",
            "16.12.2026 10:00",
        ],
        "NIS2",
        "/NetServer/PublicationControllerServlet?function=Detail&TOID=1",
        "Cybersecurity",
    ) == BWProject(
        published="10.11.2026",
        deadline="16.12.2026 10:00",
        title="IT-Sicherheitsberatung (BW-1)",
        publication_type="Offenes Verfahren",
        publisher="Ministerium für Beispiel",
        keyword="NIS2",
        url=(
            "https://vergabe.landbw.de/NetServer/"
            "PublicationControllerServlet?function=Detail&TOID=1"
        ),
        theme="Cybersecurity",
        legal_framework="UVgO/VgV",
    )


def test_parse_project_row_skips_incomplete_or_empty_rows():
    """@spec REQ-11"""
    assert parse_project_row(["10.11.2026", "   "], "NIS2") is None
    assert parse_project_row(["10.11.2026", "title"], "NIS2") is None


def test_extract_page_projects_reads_visible_rows_and_detail_identifiers():
    """@spec REQ-11"""
    class FakeCell:
        def __init__(self, value):
            self.value = value

        def inner_text(self):
            return self.value

    class FakeRow:
        def locator(self, selector):
            assert selector == "td"
            return self

        def all(self):
            return [
                FakeCell("10.11.2026"),
                FakeCell("IT-Sicherheitsberatung"),
                FakeCell("Ministerium"),
                FakeCell("Offenes Verfahren"),
                FakeCell("UVgO/VgV"),
                FakeCell("16.12.2026 10:00"),
            ]

        def get_attribute(self, name):
            values = {
                "data-oid": "notice-123",
                "data-category": "InvitationToTender",
            }
            return values[name]

    class FakeRows:
        def all(self):
            return [FakeRow()]

    class FakePage:
        def locator(self, selector):
            assert selector == (
                "#pagePublicationSearchResult "
                "table.tableHorizontalHeader tbody tr"
            )
            return FakeRows()

    assert _extract_page_projects(
        FakePage(), "NIS2", "Cybersecurity"
    ) == [
        BWProject(
            published="10.11.2026",
            deadline="16.12.2026 10:00",
            title="IT-Sicherheitsberatung",
            publication_type="Offenes Verfahren",
            publisher="Ministerium",
            keyword="NIS2",
            url=(
                "https://vergabe.landbw.de/NetServer/"
                "PublicationControllerServlet?function=Detail&TOID=notice-123"
                "&Category=InvitationToTender"
            ),
            theme="Cybersecurity",
            legal_framework="UVgO/VgV",
        )
    ]


def test_publication_date_window_is_inclusive_and_rejects_bad_dates():
    """@spec REQ-11"""
    cutoff = date(2026, 8, 19)
    assert _is_within_date_window(
        BWProject("19.08.2026", "", "On cutoff", "", "", ""),
        cutoff,
    )
    assert not _is_within_date_window(
        BWProject("18.08.2026", "", "Before cutoff", "", "", ""),
        cutoff,
    )
    assert _subtract_months(date(2026, 10, 31), 2) == date(2026, 8, 31)
    with pytest.raises(ValueError, match="expected DD.MM.YYYY"):
        _is_within_date_window(
            BWProject("unknown", "", "Bad date", "", "", ""),
            cutoff,
        )


def test_merge_project_deduplicates_and_combines_keywords_and_themes():
    """@spec REQ-11"""
    projects: dict[str, BWProject] = {}
    first = BWProject(
        "10.11.2026",
        "16.12.2026",
        "Security tender",
        "Open procedure",
        "BW",
        "NIS2; NIS2",
        "https://example.de/notice/1",
        "Cybersecurity; Cybersecurity",
        "UVgO/VgV",
    )
    second = BWProject(
        "10.11.2026",
        "16.12.2026",
        "Different title",
        "Open procedure",
        "BW",
        "SIEM",
        "https://example.de/notice/1",
        "Software",
        "UVgO/VgV",
    )

    merge_project(projects, first)
    merge_project(projects, second)

    assert len(projects) == 1
    merged = projects[project_identity(first)]
    assert merged.title == first.title
    assert merged.keyword == "NIS2; SIEM"
    assert merged.theme == "Cybersecurity; Software"
    assert merged.legal_framework == "UVgO/VgV"


def test_seen_projects_persist_and_back_up_changed_file(tmp_path: Path):
    """@spec REQ-08, REQ-11"""
    seen_file = tmp_path / "seen_bw.json"
    first = BWProject(
        "10.11.2026",
        "16.12.2026",
        "First",
        "Open procedure",
        "BW",
        "NIS2",
        "https://example.de/notice/1",
        "Cybersecurity",
        "UVgO/VgV",
    )
    second = BWProject(
        "09.11.2026",
        "",
        "Second",
        "Open procedure",
        "BW",
        "SIEM",
        "https://example.de/notice/2",
        "Cybersecurity",
        "VOB",
    )

    save_seen_projects([first], seen_file)
    previous = seen_file.read_text(encoding="utf-8")
    save_seen_projects([first, second, first], seen_file)

    assert Path(f"{seen_file}.bk").read_text(encoding="utf-8") == previous
    assert load_seen_projects(seen_file) == [first, second]


def test_seen_projects_noop_save_preserves_existing_backup(tmp_path: Path):
    """@spec REQ-08, REQ-11"""
    seen_file = tmp_path / "seen_bw.json"
    first = BWProject("10.11.2026", "", "First", "", "", "NIS2")
    second = BWProject("09.11.2026", "", "Second", "", "", "SIEM")
    save_seen_projects([first], seen_file)
    save_seen_projects([first, second], seen_file)
    backup = Path(f"{seen_file}.bk")
    original_backup = backup.read_text(encoding="utf-8")
    current = seen_file.read_text(encoding="utf-8")

    save_seen_projects([first, second], seen_file)

    assert seen_file.read_text(encoding="utf-8") == current
    assert backup.read_text(encoding="utf-8") == original_backup


def test_save_projects_csv_writes_portal_fields_and_backup(tmp_path: Path):
    """@spec REQ-11"""
    output = tmp_path / "bw_results.csv"
    output.write_text("previous CSV", encoding="utf-8")

    save_projects_csv(
        [
            BWProject(
                "10.11.2026",
                "16.12.2026 10:00",
                "IT-Sicherheitsberatung",
                "Offenes Verfahren",
                "Ministerium",
                "NIS2",
                "https://example.de/notice/1",
                "Cybersecurity",
                "UVgO/VgV",
            )
        ],
        output,
    )

    assert Path(f"{output}.bk").read_text(encoding="utf-8") == "previous CSV"
    assert output.read_text(encoding="utf-8").splitlines() == [
        "published,deadline,title,publication_type,legal_framework,publisher,"
        "theme,keyword,url",
        "10.11.2026,16.12.2026 10:00,IT-Sicherheitsberatung,Offenes Verfahren,"
        "UVgO/VgV,Ministerium,Cybersecurity,NIS2,"
        "https://example.de/notice/1",
    ]


def test_search_paginates_filters_seen_and_old_projects_and_merges_metadata(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """@spec REQ-11"""
    class FakeLocator:
        def __init__(self, page, kind):
            self.page = page
            self.kind = kind

        def count(self):
            return int(self.page.page_number == 0)

        def click(self):
            self.page.page_number += 1

        def wait_for(self, state, timeout):
            assert state == "visible"
            assert timeout == 60000

    class FakePage:
        def __init__(self):
            self.page_number = 0
            self.search_urls = []

        def goto(self, url, wait_until):
            assert wait_until == "domcontentloaded"
            self.search_urls.append(url)
            self.page_number = 0

        def get_by_role(self, role, name):
            return FakeLocator(self, name)

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
        bw_analysis,
        "sync_playwright",
        lambda: fake_playwright,
    )
    previously_seen = BWProject(
        "10.11.2026",
        "",
        "Previously seen",
        "",
        "BW",
        "Datenanalyse",
        "https://example.de/seen",
        "AI",
    )
    too_old = BWProject(
        "01.08.2026",
        "",
        "Old project",
        "",
        "BW",
        "Datenanalyse",
        "https://example.de/old",
        "AI",
    )
    fresh = BWProject(
        "10.11.2026",
        "",
        "Fresh project",
        "",
        "BW",
        "Datenanalyse",
        "https://example.de/fresh",
        "AI",
    )
    second_keyword_match = BWProject(
        "10.11.2026",
        "",
        "Fresh project",
        "",
        "BW",
        "Sprachmodell",
        "https://example.de/fresh",
        "AI",
    )
    extra = BWProject(
        "09.11.2026",
        "",
        "Second fresh project",
        "",
        "BW",
        "Sprachmodell",
        "https://example.de/extra",
        "AI",
    )

    def extract_projects(page, keyword, theme):
        projects_by_keyword = {
            "Datenanalyse": (
                [previously_seen, too_old, fresh],
                [fresh],
            ),
            "Sprachmodell": (
                [second_keyword_match, extra],
                [],
            ),
        }
        return projects_by_keyword[keyword][page.page_number]

    monkeypatch.setattr(
        bw_analysis,
        "_extract_page_projects",
        extract_projects,
    )

    found = bw_analysis.search_bw_projects(
        themes=(BWTheme("AI", ("Datenanalyse", "Sprachmodell")),),
        seen_keys={project_identity(previously_seen)},
        published_since=date(2026, 8, 19),
    )

    assert [project.url for project in found] == [
        previously_seen.url,
        fresh.url,
        extra.url,
    ]
    assert found[1].keyword == "Datenanalyse; Sprachmodell"
    assert fake_playwright.browser.page.search_urls == [
        _search_url("Datenanalyse"),
        _search_url("Sprachmodell"),
    ]
    output = capsys.readouterr().out
    assert "Fresh project" in output
    assert "Previously seen" not in output
    assert "Old project" not in output


def test_main_summary_distinguishes_history_total_from_new_projects(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """@spec REQ-11"""
    existing = [
        BWProject(
            "10.11.2026",
            "",
            f"Existing {index}",
            "",
            "",
            "",
            f"https://example.de/{index}",
        )
        for index in range(2)
    ]
    new = BWProject(
        "10.11.2026",
        "",
        "New project",
        "",
        "",
        "",
        "https://example.de/new",
    )
    monkeypatch.setattr("sys.argv", ["analyse.bw_analysis"])
    monkeypatch.setattr(bw_analysis, "load_seen_projects", lambda path: existing)
    monkeypatch.setattr(bw_analysis, "search_bw_projects", lambda **kwargs: [new])
    monkeypatch.setattr(
        bw_analysis,
        "save_seen_projects",
        lambda projects, path: None,
    )

    bw_analysis.main()

    assert capsys.readouterr().out == (
        "History contains 3 projects total; 1 new project this run.\n"
    )


def test_main_uses_its_own_default_history_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """@spec REQ-08, REQ-11"""
    history_paths = []
    monkeypatch.setattr("sys.argv", ["analyse.bw_analysis"])
    monkeypatch.setattr(
        bw_analysis,
        "load_seen_projects",
        lambda path: history_paths.append(path) or [],
    )
    monkeypatch.setattr(bw_analysis, "search_bw_projects", lambda **kwargs: [])
    monkeypatch.setattr(
        bw_analysis,
        "save_seen_projects",
        lambda projects, path: None,
    )

    bw_analysis.main()

    assert history_paths == ["output/seen_bw.json"]
    assert capsys.readouterr().out == (
        "History contains 0 projects total; 0 new projects this run.\n"
    )
