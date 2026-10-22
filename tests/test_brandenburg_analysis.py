import json
from datetime import date
from pathlib import Path

import pytest

import analyse.brandenburg_analysis as brandenburg_analysis
from analyse.brandenburg_analysis import (
    BrandenburgProject,
    BrandenburgTheme,
    THEMES,
    _is_within_date_window,
    _subtract_months,
    load_seen_projects,
    merge_project,
    parse_project_row,
    save_projects_csv,
    save_seen_projects,
)


def test_theme_configuration_contains_requested_keywords():
    assert {
        theme.name: theme.keywords
        for theme in THEMES
    } == {
        "AI": ("Datenanalyse", "Entscheidungsunterstützung", "Sprachmodell"),
        "Quantum": (
            "Quantensoftware",
            "Quantenkommunikation",
            "Post-Quanten-Kryptographie",
        ),
        "Cybersecurity": ("NIS2", "KRITIS", "SIEM", "Identitätsmanagement"),
        "Robotics": ("Autonome Navigation", "Cobot", "Missionsplanung"),
        "Software": (
            "ECM",
            "CMS",
            "SBOM",
            "Identitätsmanagement",
            "Digitale Identität",
        ),
        "Cross-domain": (
            "Forschungsprojekt",
            "Demonstrator",
            "Prototyp",
            "Machbarkeitsstudie",
            "Reallabor",
        ),
    }


def test_parse_project_row_extracts_listing_data_and_url():
    assert parse_project_row(
        [
            "19.10.2026",
            "09.11.2026",
            "Lieferung eines Utility Task Vehicle",
            "UVgO Ausschreibung",
            "Landkreis Potsdam-Mittelmark",
        ],
        "Datenanalyse",
        "/VMPCenter/public/company/projectForwarding.do?pid=275692",
        "AI",
    ) == BrandenburgProject(
        published="19.10.2026",
        deadline="09.11.2026",
        title="Lieferung eines Utility Task Vehicle",
        publication_type="UVgO Ausschreibung",
        publisher="Landkreis Potsdam-Mittelmark",
        keyword="Datenanalyse",
        url=(
            "https://vergabemarktplatz.brandenburg.de/"
            "VMPCenter/public/company/projectForwarding.do?pid=275692"
        ),
        theme="AI",
    )


def test_parse_project_row_skips_empty_or_non_result_rows():
    assert parse_project_row(["", "", "   ", "", ""], "Cobot") is None
    assert parse_project_row(["only", "two"], "Cobot") is None


def test_merge_project_deduplicates_url_and_metadata():
    projects: dict[str, BrandenburgProject] = {}
    first = BrandenburgProject(
        "19.10.2026",
        "09.11.2026",
        "AI procurement",
        "Tender",
        "City",
        "Datenanalyse; Datenanalyse",
        "https://example.de/project/1",
        "AI; AI",
    )
    second = BrandenburgProject(
        "19.10.2026",
        "09.11.2026",
        "Different title",
        "Tender",
        "City",
        "Sprachmodell",
        "https://example.de/project/1",
        "AI",
    )

    merge_project(projects, first)
    merge_project(projects, second)

    assert len(projects) == 1
    merged = projects["https://example.de/project/1"]
    assert merged.title == first.title
    assert merged.keyword == "Datenanalyse; Sprachmodell"
    assert merged.theme == "AI"


def test_publication_date_window_uses_calendar_months_and_rejects_bad_dates():
    assert _subtract_months(date(2026, 10, 31), 2) == date(2026, 8, 31)
    assert _is_within_date_window(
        BrandenburgProject("19.08.2026", "", "On cutoff", "", "", ""),
        date(2026, 8, 19),
    )
    assert not _is_within_date_window(
        BrandenburgProject("18.08.2026", "", "Before cutoff", "", "", ""),
        date(2026, 8, 19),
    )
    with pytest.raises(ValueError, match="expected DD.MM.YYYY"):
        _is_within_date_window(
            BrandenburgProject("unknown", "", "Bad date", "", "", ""),
            date(2026, 8, 19),
        )


def test_seen_projects_persist_and_back_up_changed_file(tmp_path: Path):
    seen_file = tmp_path / "seen_brandenburg.json"
    backup_file = Path(f"{seen_file}.bk")
    first = BrandenburgProject(
        "19.10.2026",
        "09.11.2026",
        "AI procurement",
        "Tender",
        "City",
        "Datenanalyse",
        "https://example.de/project/1",
        "AI",
    )
    second = BrandenburgProject(
        "18.10.2026",
        "10.11.2026",
        "Quantum procurement",
        "Tender",
        "City",
        "Quantensoftware",
        "https://example.de/project/2",
        "Quantum",
    )

    save_seen_projects([first], seen_file)
    previous = seen_file.read_text(encoding="utf-8")
    save_seen_projects([first, second, first], seen_file)

    assert backup_file.read_text(encoding="utf-8") == previous
    assert load_seen_projects(seen_file) == [first, second]
    assert json.loads(seen_file.read_text(encoding="utf-8"))[0]["url"] == first.url


def test_seen_projects_noop_save_does_not_replace_backup(tmp_path: Path):
    seen_file = tmp_path / "seen_brandenburg.json"
    first = BrandenburgProject("19.10.2026", "", "One", "", "", "ECM")
    second = BrandenburgProject("18.10.2026", "", "Two", "", "", "SBOM")

    save_seen_projects([first], seen_file)
    save_seen_projects([first, second], seen_file)
    backup_file = Path(f"{seen_file}.bk")
    original_backup = backup_file.read_text(encoding="utf-8")
    current = seen_file.read_text(encoding="utf-8")

    save_seen_projects([first, second], seen_file)

    assert seen_file.read_text(encoding="utf-8") == current
    assert backup_file.read_text(encoding="utf-8") == original_backup


def test_save_projects_csv_creates_backup(tmp_path: Path):
    output = tmp_path / "brandenburg_results.csv"
    backup = Path(f"{output}.bk")
    output.write_text("previous CSV", encoding="utf-8")

    save_projects_csv(
        [
            BrandenburgProject(
                "19.10.2026",
                "09.11.2026",
                "AI procurement",
                "Tender",
                "City",
                "Datenanalyse",
                "https://example.de/project/1",
                "AI",
            )
        ],
        output,
    )

    assert backup.read_text(encoding="utf-8") == "previous CSV"
    assert output.read_text(encoding="utf-8").splitlines() == [
        "published,deadline,title,publication_type,publisher,theme,keyword,url",
        "19.10.2026,09.11.2026,AI procurement,Tender,City,AI,Datenanalyse,"
        "https://example.de/project/1",
    ]


def test_search_brandenburg_projects_filters_seen_and_old_results(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    class FakeLocator:
        def __init__(self, page, kind):
            self.page = page
            self.kind = kind
            self.first = self

        def fill(self, value):
            self.page.keywords.append(value)

        def click(self):
            pass

        def wait_for(self, state, timeout):
            if self.kind == "Bitte warten":
                self.page.loading_states.append(state)

        def inner_text(self):
            return "Seite: 1 von 1 - Gesamteinträge: 3"

    class FakePage:
        def __init__(self):
            self.keywords = []
            self.loading_states = []

        def goto(self, url, wait_until):
            assert url == brandenburg_analysis.BRANDENBURG_SEARCH_URL
            assert wait_until == "domcontentloaded"

        def get_by_role(self, role, name):
            return FakeLocator(self, name)

        def get_by_text(self, pattern, exact=False):
            return FakeLocator(
                self, pattern if isinstance(pattern, str) else "pagination"
            )

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
        brandenburg_analysis, "sync_playwright", lambda: fake_playwright
    )
    seen = BrandenburgProject(
        "19.10.2026",
        "",
        "Previously seen",
        "Tender",
        "City",
        "Datenanalyse",
        "https://example.de/seen",
        "AI",
    )
    old = BrandenburgProject(
        "01.08.2026",
        "",
        "Old project",
        "Tender",
        "City",
        "Datenanalyse",
        "https://example.de/old",
        "AI",
    )
    fresh = BrandenburgProject(
        "19.10.2026",
        "",
        "Fresh project",
        "Tender",
        "City",
        "Datenanalyse",
        "https://example.de/fresh",
        "AI",
    )
    monkeypatch.setattr(
        brandenburg_analysis,
        "_extract_page_projects",
        lambda page, keyword, theme: [seen, old, fresh],
    )

    found = brandenburg_analysis.search_brandenburg_projects(
        themes=(BrandenburgTheme("AI", ("Datenanalyse",)),),
        seen_keys={brandenburg_analysis.project_identity(seen)},
        published_since=date(2026, 8, 19),
    )

    assert found == [seen, fresh]
    assert fake_playwright.browser.page.keywords == ["Datenanalyse"]
    assert fake_playwright.browser.page.loading_states == ["hidden", "visible", "hidden"]
    output = capsys.readouterr().out
    assert "Fresh project" in output
    assert "Previously seen" not in output
    assert "Old project" not in output


def test_main_summary_distinguishes_history_total_from_new_projects(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    existing = [
        BrandenburgProject(
            "19.10.2026", "", f"Existing {index}", "", "", "", f"https://example.de/{index}"
        )
        for index in range(2)
    ]
    new = BrandenburgProject(
        "20.10.2026", "", "New project", "", "", "", "https://example.de/new"
    )
    monkeypatch.setattr("sys.argv", ["analyse.brandenburg_analysis"])
    monkeypatch.setattr(brandenburg_analysis, "load_seen_projects", lambda path: existing)
    monkeypatch.setattr(
        brandenburg_analysis,
        "search_brandenburg_projects",
        lambda **kwargs: [new],
    )
    monkeypatch.setattr(brandenburg_analysis, "save_seen_projects", lambda projects, path: None)

    brandenburg_analysis.main()

    assert capsys.readouterr().out == (
        "History contains 3 projects total; 1 new project this run.\n"
    )
