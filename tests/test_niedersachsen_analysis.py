# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import analyse.bw_analysis as bw_analysis
import analyse.niedersachsen_analysis as niedersachsen_analysis
from analyse.niedersachsen_analysis import (
    NiedersachsenProject,
    NiedersachsenTheme,
    THEMES,
    _extract_page_projects,
    _is_within_date_window,
    _page_numbers,
    _subtract_months,
    load_seen_projects,
    merge_project,
    parse_project_row,
    project_identity,
    save_projects_csv,
    save_seen_projects,
)


def test_theme_configuration_matches_bw_exactly():
    """@spec REQ-13"""
    assert {
        theme.name: theme.keywords for theme in THEMES
    } == {
        theme.name: theme.keywords for theme in bw_analysis.THEMES
    }


def test_parse_project_row_maps_publication_type_rule_authority_and_url():
    """@spec REQ-13"""
    assert parse_project_row(
        [
            "02.11.2026",
            "30.11.2026",
            "Beschaffung eines Eye-Trackers inkl. Analysesoftware",
            "UVgO\nAusschreibung",
            "Stiftung Universität Lüneburg",
            "",
        ],
        "Software",
        "/Satellite/public/company/projectForwarding.do?pid=136622",
        "Software",
    ) == NiedersachsenProject(
        published="02.11.2026",
        deadline="30.11.2026",
        title="Beschaffung eines Eye-Trackers inkl. Analysesoftware",
        publication_type="Ausschreibung",
        contracting_rule="UVgO",
        publisher="Stiftung Universität Lüneburg",
        keyword="Software",
        url=(
            "https://vergabe.niedersachsen.de/"
            "Satellite/public/company/projectForwarding.do?pid=136622"
        ),
        theme="Software",
    )


def test_parse_project_row_preserves_no_deadline_and_awarded_type():
    """@spec REQ-13"""
    project = parse_project_row(
        [
            "04.11.2026",
            "nv",
            "Software maintenance",
            "VgV\nVergebener Auftrag",
            "Land Niedersachsen",
        ],
        "Software",
        "/Satellite/public/company/projectForwarding.do?pid=1",
    )
    assert project is not None
    assert project.deadline == "nv"
    assert project.contracting_rule == "VgV"
    assert project.publication_type == "Vergebener Auftrag"


def test_parse_project_row_skips_incomplete_rows_and_rejects_missing_url():
    """@spec REQ-13"""
    assert parse_project_row(["", "", "  "], "Software") is None
    assert parse_project_row(["01.11.2026", "nv"], "Software") is None
    with pytest.raises(ValueError, match="has no detail URL"):
        parse_project_row(
            ["02.11.2026", "30.11.2026", "Tender", "VgV\nAusschreibung", "Agency"],
            "Software",
        )


def test_extract_page_projects_reads_table_and_detail_link():
    """@spec REQ-13"""
    class FakeCell:
        def __init__(self, value: str):
            self.value = value

        def inner_text(self) -> str:
            return self.value

    class FakeLink:
        def get_attribute(self, name: str) -> str:
            assert name == "href"
            return "/Satellite/public/company/projectForwarding.do?pid=136622"

    class FakeRow:
        def locator(self, selector: str):
            if selector == "td":
                return FakeList(
                    [
                        FakeCell("02.11.2026"),
                        FakeCell("30.11.2026"),
                        FakeCell("Eye-Tracker"),
                        FakeCell("UVgO\nAusschreibung"),
                        FakeCell("University"),
                        FakeCell(""),
                    ]
                )
            assert selector == "a[href]"
            return FakeList([FakeLink()])

    class FakeList:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class FakePage:
        def locator(self, selector: str):
            assert selector == "table.csx-new-table tbody tr"
            return FakeList([FakeRow()])

    assert _extract_page_projects(
        FakePage(), "Software", "Software"
    ) == [
        NiedersachsenProject(
            "02.11.2026",
            "30.11.2026",
            "Eye-Tracker",
            "Ausschreibung",
            "UVgO",
            "University",
            "Software",
            (
                "https://vergabe.niedersachsen.de/"
                "Satellite/public/company/projectForwarding.do?pid=136622"
            ),
            "Software",
        )
    ]


def test_publication_date_window_is_inclusive_and_rejects_bad_dates():
    """@spec REQ-13"""
    cutoff = date(2026, 8, 19)
    assert _is_within_date_window(
        NiedersachsenProject(
            "19.08.2026", "", "On cutoff", "", "", "", "", "/notice"
        ),
        cutoff,
    )
    assert not _is_within_date_window(
        NiedersachsenProject(
            "18.08.2026", "", "Before cutoff", "", "", "", "", "/notice"
        ),
        cutoff,
    )
    assert _subtract_months(date(2026, 10, 31), 2) == date(2026, 8, 31)
    with pytest.raises(ValueError, match="expected DD.MM.YYYY"):
        _is_within_date_window(
            NiedersachsenProject(
                "unknown", "", "Bad date", "", "", "", "", "/notice"
            ),
            cutoff,
        )


def test_page_numbers_parse_total_and_reject_unexpected_text():
    """@spec REQ-13"""
    class FakeLocator:
        def __init__(self, text: str):
            self.text = text

        def inner_text(self) -> str:
            return self.text

    class FakePage:
        def __init__(self, text: str):
            self.text = text

        def locator(self, selector: str) -> FakeLocator:
            assert selector == ".browsePagesText"
            return FakeLocator(self.text)

    assert _page_numbers(
        FakePage("Seite: 2 von 3 - Gesamteinträge: 45")
    ) == (2, 3)
    with pytest.raises(ValueError, match="Cannot read Niedersachsen"):
        _page_numbers(FakePage("pagination changed"))


def test_merge_project_deduplicates_by_url_and_combines_keywords_and_themes():
    """@spec REQ-13"""
    projects: dict[str, NiedersachsenProject] = {}
    first = NiedersachsenProject(
        "02.11.2026",
        "30.11.2026",
        "IT tender",
        "Ausschreibung",
        "UVgO",
        "Agency",
        "Software; Software",
        "https://example.de/notice/1",
        "Software; Software",
    )
    second = NiedersachsenProject(
        "02.11.2026",
        "30.11.2026",
        "Different title",
        "Ausschreibung",
        "UVgO",
        "Agency",
        "SBOM",
        "https://example.de/notice/1",
        "Cybersecurity",
    )

    merge_project(projects, first)
    merge_project(projects, second)

    assert len(projects) == 1
    merged = projects[project_identity(first)]
    assert merged.title == first.title
    assert merged.keyword == "Software; SBOM"
    assert merged.theme == "Software; Cybersecurity"


def test_history_persists_and_backs_up_only_changed_content(tmp_path: Path):
    """@spec REQ-08, REQ-13"""
    history = tmp_path / "seen_niedersachsen.json"
    first = NiedersachsenProject(
        "02.11.2026",
        "30.11.2026",
        "First",
        "Ausschreibung",
        "UVgO",
        "Agency",
        "Software",
        "https://example.de/1",
        "Software",
    )
    second = NiedersachsenProject(
        "01.11.2026",
        "nv",
        "Second",
        "Ausschreibung",
        "VgV",
        "Agency",
        "SBOM",
        "https://example.de/2",
        "Software",
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
    """@spec REQ-08, REQ-13"""
    history = tmp_path / "seen_niedersachsen.json"
    history.write_text(json.dumps({"invalid": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="Expected a JSON list"):
        load_seen_projects(history)


def test_save_projects_csv_writes_portal_fields_and_backup(tmp_path: Path):
    """@spec REQ-13"""
    output = tmp_path / "niedersachsen_results.csv"
    output.write_text("previous CSV", encoding="utf-8")
    save_projects_csv(
        [
            NiedersachsenProject(
                "02.11.2026",
                "30.11.2026",
                "Eye-Tracker",
                "Ausschreibung",
                "UVgO",
                "Stiftung Universität Lüneburg",
                "Software",
                "https://example.de/notice/1",
                "Software",
            )
        ],
        output,
    )

    assert Path(f"{output}.bk").read_text(encoding="utf-8") == "previous CSV"
    assert output.read_text(encoding="utf-8").splitlines() == [
        "published,deadline,title,publication_type,contracting_rule,publisher,"
        "theme,keyword,url",
        "02.11.2026,30.11.2026,Eye-Tracker,Ausschreibung,UVgO,"
        "Stiftung Universität Lüneburg,Software,Software,"
        "https://example.de/notice/1",
    ]


def test_search_filters_active_type_paginates_and_merges_seen_and_new(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """@spec REQ-13"""
    class FakeLocator:
        def __init__(self, page, selector: str):
            self.page = page
            self.selector = selector

        def evaluate(self, expression: str) -> None:
            assert self.selector == "#alle2"
            assert "checked = false" in expression
            self.page.all_publications_unchecked = True

        def check(self) -> None:
            assert self.selector == "#selectedPublicationTypesTender"
            self.page.active_tender_checked = True

        def fill(self, value: str) -> None:
            assert self.selector == "#searchText"
            self.page.keyword = value

        def click(self) -> None:
            if "searchExtended" in self.selector:
                self.page.current_page = 1
            elif self.selector == '.browseForward[title="nächste Seite"]':
                self.page.current_page += 1
            else:
                raise AssertionError(f"Unexpected click selector: {self.selector}")

        def count(self) -> int:
            return int(
                self.selector == '.browseForward[title="nächste Seite"]'
                and self.page.current_page < self.page.total_pages
            )

        def inner_text(self) -> str:
            assert self.selector == ".browsePagesText"
            return (
                f"Seite: {self.page.current_page} von "
                f"{self.page.total_pages} - Gesamteinträge: 3"
            )

    class FakePage:
        def __init__(self):
            self.current_page = 0
            self.total_pages = 2
            self.keyword = ""
            self.visited: list[str] = []
            self.all_publications_unchecked = False
            self.active_tender_checked = False

        def goto(self, url: str, wait_until: str) -> None:
            assert url == niedersachsen_analysis.NIEDERSACHSEN_SEARCH_URL
            assert wait_until == "domcontentloaded"
            self.visited.append(url)
            self.current_page = 0

        def locator(self, selector: str) -> FakeLocator:
            return FakeLocator(self, selector)

        def wait_for_load_state(self, state: str, timeout: int) -> None:
            assert state == "domcontentloaded"
            assert timeout == 60000

        def wait_for_function(
            self, expression: str, arg: int, timeout: int
        ) -> None:
            assert "browsePagesText" in expression
            assert arg == self.current_page
            assert timeout == 60000

    class FakeBrowser:
        def __init__(self):
            self.page = FakePage()

        def new_page(self):
            return self.page

        def close(self) -> None:
            pass

    class FakePlaywright:
        def __init__(self):
            self.chromium = self
            self.browser = FakeBrowser()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def launch(self, headless: bool):
            assert headless
            return self.browser

    fake_playwright = FakePlaywright()
    monkeypatch.setattr(
        niedersachsen_analysis,
        "sync_playwright",
        lambda: fake_playwright,
    )
    seen = NiedersachsenProject(
        "02.11.2026",
        "30.11.2026",
        "Seen tender",
        "Ausschreibung",
        "UVgO",
        "Agency",
        "Datenanalyse",
        "https://example.de/seen",
        "AI",
    )
    fresh = NiedersachsenProject(
        "02.11.2026",
        "30.11.2026",
        "Fresh tender",
        "Ausschreibung",
        "UVgO",
        "Agency",
        "Datenanalyse",
        "https://example.de/fresh",
        "AI",
    )
    second_keyword_match = NiedersachsenProject(
        "02.11.2026",
        "30.11.2026",
        "Fresh tender",
        "Ausschreibung",
        "UVgO",
        "Agency",
        "SBOM",
        "https://example.de/fresh",
        "Software",
    )

    def extract_projects(page, keyword, theme):
        projects = {
            ("Datenanalyse", 1): [seen, fresh],
            ("Datenanalyse", 2): [],
            ("SBOM", 1): [second_keyword_match],
            ("SBOM", 2): [],
        }
        return projects[(keyword, page.current_page)]

    monkeypatch.setattr(
        niedersachsen_analysis,
        "_extract_page_projects",
        extract_projects,
    )
    results = niedersachsen_analysis.search_niedersachsen_projects(
        themes=(NiedersachsenTheme("AI", ("Datenanalyse", "SBOM")),),
        seen_keys={project_identity(seen)},
        published_since=date(2026, 8, 19),
    )

    assert fake_playwright.browser.page.all_publications_unchecked
    assert fake_playwright.browser.page.active_tender_checked
    assert len(fake_playwright.browser.page.visited) == 2
    assert [project.url for project in results] == [
        seen.url,
        fresh.url,
    ]
    assert results[1].keyword == "Datenanalyse; SBOM"
    output = capsys.readouterr().out
    assert "Fresh tender" in output
    assert "Seen tender" not in output


def test_main_uses_independent_history_and_reports_new_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """@spec REQ-08, REQ-13"""
    existing = NiedersachsenProject(
        "02.11.2026",
        "",
        "Existing",
        "Ausschreibung",
        "UVgO",
        "",
        "",
        "https://example.de/old",
    )
    fresh = NiedersachsenProject(
        "02.11.2026",
        "",
        "Fresh",
        "Ausschreibung",
        "UVgO",
        "",
        "",
        "https://example.de/new",
    )
    history_paths = []
    monkeypatch.setattr("sys.argv", ["analyse.niedersachsen_analysis"])
    monkeypatch.setattr(
        niedersachsen_analysis,
        "load_seen_projects",
        lambda path: history_paths.append(path) or [existing],
    )
    monkeypatch.setattr(
        niedersachsen_analysis,
        "search_niedersachsen_projects",
        lambda **kwargs: [fresh],
    )
    monkeypatch.setattr(
        niedersachsen_analysis,
        "save_seen_projects",
        lambda projects, path: None,
    )

    niedersachsen_analysis.main()

    assert history_paths == ["seen_niedersachsen.json"]
    assert capsys.readouterr().out == (
        "History contains 2 projects total; 1 new project this run.\n"
    )
