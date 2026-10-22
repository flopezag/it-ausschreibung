import sys
import json
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyse.dtvp_analysis as dtvp_analysis
from analyse.dtvp_analysis import (
    DtvpAnnouncement,
    DtvpTheme,
    THEMES,
    announcement_identity,
    build_cpv_payload,
    _is_within_date_window,
    _subtract_months,
    load_seen_announcements,
    merge_announcement,
    parse_announcement_row,
    print_keyword_results,
    save_announcements_csv,
    save_seen_announcements,
)


def test_subtract_months_uses_calendar_months_and_clamps_end_of_month():
    assert _subtract_months(date(2026, 10, 2), 2) == date(2026, 8, 2)
    assert _subtract_months(date(2026, 10, 31), 2) == date(2026, 8, 31)
    assert _subtract_months(date(2026, 5, 31), 3) == date(2026, 2, 28)


def test_publication_date_window_includes_cutoff_and_rejects_older_notices():
    cutoff = date(2026, 8, 2)
    on_cutoff = DtvpAnnouncement(
        "02.08.2026", "", "On cutoff", "Tender", "City", "SIEM"
    )
    older = DtvpAnnouncement("01.08.2026", "", "Older", "Tender", "City", "SIEM")
    reported_old_result = DtvpAnnouncement(
        "12.11.2025", "", "SMILE24 AI tender", "Tender", "City", "Künstliche Intelligenz"
    )

    assert _is_within_date_window(on_cutoff, cutoff)
    assert not _is_within_date_window(older, cutoff)
    assert not _is_within_date_window(reported_old_result, cutoff)


def test_publication_date_window_reports_unexpected_date_format():
    announcement = DtvpAnnouncement("unknown", "", "Bad date", "Tender", "City", "SIEM")

    with pytest.raises(ValueError, match="expected DD.MM.YYYY"):
        _is_within_date_window(announcement, date(2026, 8, 2))


def test_build_cpv_payload_uses_dtvp_code_and_name_fields():
    assert build_cpv_payload([("72000000-5", "IT services")]) == [
        {"code": "72000000-5", "name": "IT services"}
    ]


def test_theme_configuration_contains_requested_keywords_and_cpv_codes():
    assert {
        theme.name: (theme.keywords, theme.cpv_codes)
        for theme in THEMES
    } == {
        "AI": (
            (
                "Künstliche Intelligenz",
                "Maschinelles Lernen",
                "Generative KI",
                "Large Language Model",
                "Computer Vision",
            ),
            ("48000000-8", "72000000-5", "73000000-2"),
        ),
        "Quantum": (
            ("Quantencomputing", "Quantencomputer", "Quantenalgorithmus", "Quantensoftware"),
            ("30000000-9", "38000000-5", "48000000-8", "72000000-5", "73000000-2"),
        ),
        "Cybersecurity": (
            (
                "IT-Sicherheit",
                "Informationssicherheit",
                "ISMS",
                "BSI IT-Grundschutz",
                "Penetrationstest",
                "SIEM",
                "CRA",
            ),
            ("48000000-8", "72000000-5", "32000000-3"),
        ),
        "Robotics": (
            (
                "Robotik",
                "Robotersystem",
                "Inspektionsroboter",
                "Autonomer mobiler Roboter",
                "Drohne",
            ),
            (
                "42000000-6",
                "38000000-5",
                "48000000-8",
                "72000000-5",
                "73000000-2",
                "34000000-7",
                "35000000-4",
                "32000000-3",
            ),
        ),
        "Software": (
            (
                "Dokumentenmanagementsystem",
                "E-Akte",
                "DevSecOps",
                "SBOM",
                "Testautomatisierung",
                "Digitale Identität",
            ),
            ("48000000-8", "72000000-5"),
        ),
    }


def test_search_uses_theme_cpv_and_filters_by_publication_date(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    class FakeLocator:
        def __init__(self, page, selector):
            self.page = page
            self.selector = selector
            self.first = self

        def click(self, timeout=None):
            if self.selector == "button":
                raise RuntimeError("No cookie dialog")

        def evaluate(self, script, value):
            self.page.cpv_payloads.append(json.loads(value))

        def fill(self, value):
            self.page.keywords.append(value)

        def inner_text(self):
            return "Seite: 1 von 1"

        def all(self):
            return []

        def wait_for(self, state, timeout):
            pass

    class FakePage:
        def __init__(self):
            self.keywords = []
            self.cpv_payloads = []

        def goto(self, url, wait_until):
            pass

        def get_by_role(self, role, name):
            return FakeLocator(self, role)

        def locator(self, selector):
            return FakeLocator(self, selector)

        def close(self):
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
            return self.browser

    fake_playwright = FakePlaywright()
    monkeypatch.setattr(dtvp_analysis, "sync_playwright", lambda: fake_playwright)
    recent = DtvpAnnouncement(
        "02.08.2026",
        "",
        "Recent announcement",
        "Tender",
        "City",
        "Künstliche Intelligenz",
        "https://dtvp.de/recent",
        "AI",
    )
    old = DtvpAnnouncement(
        "01.08.2026",
        "",
        "Old announcement",
        "Tender",
        "City",
        "Künstliche Intelligenz",
        "https://dtvp.de/old",
        "AI",
    )
    fresh = DtvpAnnouncement(
        "03.08.2026",
        "",
        "New announcement",
        "Tender",
        "City",
        "Künstliche Intelligenz",
        "https://dtvp.de/new",
        "AI",
    )
    monkeypatch.setattr(
        dtvp_analysis,
        "_extract_page_announcements",
        lambda page, keyword, theme: [recent, old, fresh],
    )
    themes = (
        DtvpTheme("AI", ("Künstliche Intelligenz",), ("48000000-8",)),
        DtvpTheme("Robotics", ("Drohne",), ("42000000-6", "35000000-4")),
    )

    assert dtvp_analysis.search_dtvp_announcements(
        themes=themes,
        published_since=date(2026, 8, 2),
        seen_keys={announcement_identity(recent)},
    ) == [recent, fresh]
    assert fake_playwright.browser.page.keywords == ["Künstliche Intelligenz", "Drohne"]
    assert fake_playwright.browser.page.cpv_payloads == [
        [{"code": "48000000-8", "name": "Software package and information systems"}],
        [
            {"code": "42000000-6", "name": "Industrial machinery"},
            {
                "code": "35000000-4",
                "name": "Security, fire-fighting, police and defence equipment",
            },
        ],
    ]
    output = capsys.readouterr().out
    assert "Recent announcement" not in output
    assert "Old announcement" not in output
    assert "New announcement" in output
    assert f"{dtvp_analysis.THEME_COLOR}Monitoring DTVP theme: AI{dtvp_analysis.COLOR_RESET}" in output
    assert (
        f"{dtvp_analysis.THEME_COLOR}Monitoring DTVP theme: Robotics"
        f"{dtvp_analysis.COLOR_RESET}"
    ) in output
    assert (
        f"{dtvp_analysis.KEYWORD_COLOR}Monitoring DTVP keyword: Künstliche Intelligenz"
        f"{dtvp_analysis.COLOR_RESET}"
    ) in output
    assert (
        f"{dtvp_analysis.KEYWORD_COLOR}Monitoring DTVP keyword: Drohne"
        f"{dtvp_analysis.COLOR_RESET}"
    ) in output
    assert "Timing DTVP keyword 'Künstliche Intelligenz':" in output
    assert "Timing DTVP keyword 'Drohne':" in output
    assert "1 page(s)" in output
    assert "DTVP search completed in " in output
    assert output.count(dtvp_analysis.THEME_COLOR) == 2
    assert output.count(dtvp_analysis.KEYWORD_COLOR) == 2
    assert output.index("Timing DTVP keyword 'Künstliche Intelligenz':") < output.index(
        f"{dtvp_analysis.THEME_COLOR}Monitoring DTVP theme: Robotics"
    )
    assert output.index("Timing DTVP keyword 'Drohne':") < output.index(
        "DTVP search completed in "
    )


def test_parse_announcement_row_extracts_listing_data_and_url():
    announcement = parse_announcement_row(
        ["30.09.2026", "15.10.2026", "IT security services", "Ausschreibung", "City"],
        "penetration",
        "/announcements/123",
        "Cybersecurity",
    )

    assert announcement == DtvpAnnouncement(
        published="30.09.2026",
        deadline="15.10.2026",
        title="IT security services",
        publication_type="Ausschreibung",
        publisher="City",
        keyword="penetration",
        url="https://www.dtvp.de/announcements/123",
        theme="Cybersecurity",
    )


def test_parse_announcement_row_skips_empty_or_non_result_rows():
    assert parse_announcement_row(["", "", "   ", "", ""], "cloud") is None
    assert parse_announcement_row(["only", "two"], "cloud") is None


def test_merge_announcement_deduplicates_url_and_collects_metadata():
    announcements: dict[str, DtvpAnnouncement] = {}
    first = DtvpAnnouncement(
        "24.06.2026",
        "nv",
        "Updated announcement title",
        "Tender",
        "City",
        "Penetrationstest",
        "https://dtvp.de/project/1",
        "Cybersecurity",
    )
    second = DtvpAnnouncement(
        "24.06.2026",
        "nv",
        "2FA application",
        "Tender",
        "City",
        "Robotik",
        "https://dtvp.de/project/1",
        "Robotics",
    )

    merge_announcement(announcements, first)
    merge_announcement(announcements, second)
    merge_announcement(announcements, first)

    merged = announcements[announcement_identity(first)]
    assert len(announcements) == 1
    assert merged.title == first.title
    assert merged.keyword == "Penetrationstest; Robotik"
    assert merged.theme == "Cybersecurity; Robotics"


def test_print_keyword_results_for_empty_search(capsys: pytest.CaptureFixture[str]):
    print_keyword_results("chatbot", [])

    assert capsys.readouterr().out == "No new ausschreibung found.\n\n\n"


def test_print_keyword_results_includes_header_list_url_and_blank_line(
    capsys: pytest.CaptureFixture[str],
):
    announcement = DtvpAnnouncement(
        "24.06.2026", "nv", "2FA application", "Tender", "City", "penetration", "https://dtvp.de/project/1"
    )

    print_keyword_results("penetration", [announcement])

    assert capsys.readouterr().out == (
        "New DTVP ausschreibung found for keyword: penetration\n"
        "- 2FA application | 24.06.2026 | City\n"
        "  Description: https://dtvp.de/project/1\n\n\n"
    )


def test_save_announcements_csv(tmp_path: Path):
    output = tmp_path / "results.csv"
    backup = Path(f"{output}.bk")
    output.write_text("previous CSV", encoding="utf-8")
    save_announcements_csv(
        [
            DtvpAnnouncement(
                "30.09.2026", "15.10.2026", "IT security", "Tender", "City", "SIEM", theme="Cybersecurity"
            )
        ],
        output,
    )

    assert backup.read_text(encoding="utf-8") == "previous CSV"
    assert output.read_text(encoding="utf-8").splitlines() == [
        "published,deadline,title,publication_type,publisher,theme,keyword,url",
        "30.09.2026,15.10.2026,IT security,Tender,City,Cybersecurity,SIEM,",
    ]


def test_seen_announcements_persist_json_and_backup_previous_file(tmp_path: Path):
    seen_file = tmp_path / "seen_dtvp.json"
    backup = Path(f"{seen_file}.bk")
    first = DtvpAnnouncement(
        "24.06.2026",
        "nv",
        "Jährliche Überprüfung",
        "Tender",
        "City",
        "penetration",
        "https://dtvp.de/1",
        "Cybersecurity",
    )
    second = DtvpAnnouncement(
        "25.06.2026",
        "nv",
        "Second",
        "Tender",
        "City",
        "chatbot",
        "https://dtvp.de/2",
        "AI",
    )

    assert load_seen_announcements(seen_file) == []
    save_seen_announcements([first], seen_file)
    previous_content = seen_file.read_text(encoding="utf-8")
    save_seen_announcements([first, second, first], seen_file)

    assert backup.read_text(encoding="utf-8") == previous_content
    assert load_seen_announcements(seen_file) == [first, second]
    saved_text = seen_file.read_text(encoding="utf-8")
    assert "Jährliche Überprüfung" in saved_text
    assert r"\u00e4" not in saved_text
    assert json.loads(saved_text)[0]["url"] == first.url


def test_save_seen_announcements_deduplicates_same_url_with_different_titles(
    tmp_path: Path,
):
    seen_file = tmp_path / "seen_dtvp.json"
    original = DtvpAnnouncement(
        "24.06.2026",
        "nv",
        "Original title",
        "Tender",
        "City",
        "Quantencomputer",
        "https://dtvp.de/same-project",
        "Quantum",
    )
    repeated = DtvpAnnouncement(
        "24.06.2026",
        "nv",
        "Different listing title",
        "Tender",
        "City",
        "Quantensoftware",
        "https://dtvp.de/same-project",
        "Quantum",
    )

    save_seen_announcements([original, repeated], seen_file)

    saved = load_seen_announcements(seen_file)
    assert len(saved) == 1
    assert saved[0].title == "Original title"
    assert saved[0].keyword == "Quantencomputer; Quantensoftware"


def test_save_seen_announcements_cleans_duplicate_metadata(tmp_path: Path):
    seen_file = tmp_path / "seen_dtvp.json"
    announcement = DtvpAnnouncement(
        "24.06.2026",
        "nv",
        "AI software project",
        "Tender",
        "City",
        "Künstliche Intelligenz; Digitale Identität; Künstliche Intelligenz",
        "https://dtvp.de/duplicate-metadata",
        "AI; Software; AI; Software",
    )

    save_seen_announcements([announcement], seen_file)

    saved = load_seen_announcements(seen_file)
    assert len(saved) == 1
    assert saved[0].keyword == "Künstliche Intelligenz; Digitale Identität"
    assert saved[0].theme == "AI; Software"


@pytest.mark.parametrize("content", ["", " \n\t"])
def test_load_seen_announcements_treats_empty_file_as_empty_history(
    tmp_path: Path, content: str
):
    seen_file = tmp_path / "seen_dtvp.json"
    seen_file.write_text(content, encoding="utf-8")

    assert load_seen_announcements(seen_file) == []


def test_load_seen_announcements_still_rejects_invalid_json(tmp_path: Path):
    seen_file = tmp_path / "seen_dtvp.json"
    seen_file.write_text("{invalid", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_seen_announcements(seen_file)


def test_announcement_identity_prefers_url():
    announcement = DtvpAnnouncement("24.06.2026", "nv", "Title", "Tender", "City", "KI", "https://dtvp.de/1")

    assert announcement_identity(announcement) == "https://dtvp.de/1"


def test_main_summary_distinguishes_history_total_from_new_announcements(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    existing = [
        DtvpAnnouncement(
            "24.06.2026", "", f"Existing {index}", "", "", "", f"https://dtvp.de/{index}"
        )
        for index in range(2)
    ]
    new = DtvpAnnouncement(
        "25.06.2026", "", "New announcement", "", "", "", "https://dtvp.de/new"
    )
    monkeypatch.setattr("sys.argv", ["analyse.dtvp_analysis"])
    monkeypatch.setattr(dtvp_analysis, "load_seen_announcements", lambda path: existing)
    monkeypatch.setattr(
        dtvp_analysis,
        "search_dtvp_announcements",
        lambda **kwargs: [new],
    )
    monkeypatch.setattr(
        dtvp_analysis, "save_seen_announcements", lambda announcements, path: None
    )

    dtvp_analysis.main()

    assert capsys.readouterr().out == (
        "History contains 3 announcements total; 1 new announcement this run.\n"
    )