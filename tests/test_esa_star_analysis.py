from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import analyse.esa_star_analysis as esa_star_analysis
from analyse.terminal import COLOR_RESET, KEYWORD_COLOR, THEME_COLOR
from analyse.esa_star_analysis import (
    ESAStarTender,
    ESARowSearchResult,
    ESATechnologyRow,
    TechnologyTreeNode,
    _collect_path_tenders,
    _select_country_de,
    _select_technology_node,
    attribute_tenders_to_rows,
    group_rows_by_path,
    load_seen_tenders,
    merge_tender,
    parse_tender_card,
    print_row_results,
    resolve_technology_tree_path,
    save_seen_tenders,
    save_tenders_csv,
    tender_identity,
    unique_tree_paths,
)


def _tender(
    url: str = "https://example.test/ESATenderActions/details/1",
    category: str = "AI / Data",
    tree_path: str = "1 - Root > I - Technology",
    selected_tree_path: str | None = None,
) -> ESAStarTender:
    return ESAStarTender(
        tender_action_number="5-12345",
        secondary_tender_number="1000001234",
        status="Intended",
        title="Example call",
        description="Research and development",
        announcement_date="05/11/2026",
        url=url,
        category=category,
        technology_keyword="Technology",
        technology_tree_path=tree_path,
        selected_tree_path=selected_tree_path or tree_path,
    )


def test_configuration_preserves_all_rows_and_groups_duplicate_paths():
    """@spec REQ-14"""
    grouped = group_rows_by_path(esa_star_analysis.ESA_STAR_ROWS)
    duplicates = [
        path_rows
        for path_rows in grouped.values()
        if len(path_rows) > 1
    ]

    assert len(esa_star_analysis.ESA_STAR_ROWS) == 32
    assert len(unique_tree_paths(esa_star_analysis.ESA_STAR_ROWS)) == 30
    assert {
        row.category for rows in duplicates for row in rows
    } == {
        "AI / Data",
        "Cybersecurity",
        "Software / Digital Engineering",
    }
    assert all(
        len(rows) == 2
        for rows in duplicates
    )
    assert all(
        row.tree_path_text != row.technology_keyword
        for row in esa_star_analysis.ESA_STAR_ROWS
    )

def test_configured_rows_preserve_supplied_paths_and_map_live_discrepancies():
    """@spec REQ-14"""
    expected_live_paths = {
        1: (
            "1 - On-board Data Subsystems",
            "D - Machine Learning and Artificial Intelligence for On-board Data Subsystems",
            "I - Machine Learning for On-board Data Subsystems",
        ),
        2: (
            "1 - On-board Data Subsystems",
            "D - Machine Learning and Artificial Intelligence for On-board Data Subsystems",
            "II - Characterisation and Evaluation of Machine Learning Techniques",
        ),
        8: (
            "6 - RF Subsystems, Payloads and Technologies",
            "A - Telecommunication Subsystems",
            "V - Telecom Security Techniques and Technologies",
        ),
        18: (
            "5 - Space System Control",
            "A - Control (Sub-) Systems Engineering",
            "II - Autonomy and FDIR",
        ),
        28: (
            "9 - Mission Operation and Ground Data Systems",
            "C - Ground Data Systems",
            "I - Mission Control System, Automation, Mission Planning, Simulators and Station M&C and Data Centre Architecture and Technologies",
        ),
    }

    for index, row in enumerate(esa_star_analysis.ESA_STAR_ROWS):
        assert row.selection_tree_path == expected_live_paths.get(index)


def test_resolve_technology_tree_path_uses_all_ancestors():
    """@spec REQ-14"""
    nodes = [
        TechnologyTreeNode("1 - First Root", "1", 10),
        TechnologyTreeNode("A - First Group", "10", 30),
        TechnologyTreeNode("I - Shared Name", "11", 50),
        TechnologyTreeNode("2 - Second Root", "2", 10),
        TechnologyTreeNode("B - Correct Group", "20", 30),
        TechnologyTreeNode("I - Shared Name", "21", 50),
    ]

    assert resolve_technology_tree_path(
        nodes,
        ("2 - Second Root", "B - Correct Group", "I - Shared Name"),
    ) == "21"


def test_resolve_technology_tree_path_rejects_missing_or_ambiguous_path():
    """@spec REQ-14"""
    nodes = [
        TechnologyTreeNode("1 - Root", "1", 10),
        TechnologyTreeNode("I - Technology", "11", 30),
        TechnologyTreeNode("1 - Root", "2", 10),
        TechnologyTreeNode("I - Technology", "21", 30),
    ]

    with pytest.raises(ValueError, match="matched 0 nodes"):
        resolve_technology_tree_path(
            nodes, ("2 - Missing Root", "I - Technology")
        )
    with pytest.raises(ValueError, match="matched 2 nodes"):
        resolve_technology_tree_path(
            nodes, ("1 - Root", "I - Technology")
        )


def test_parse_tender_card_maps_fields_and_normalizes_detail_url():
    """@spec REQ-14"""
    row = ESATechnologyRow(
        "Quantum",
        "Quantum Communication",
        ("17 - Optoelectronics", "E - Quantum Technologies", "II - Quantum Communication"),
    )

    assert parse_tender_card(
        [
            "5-50001",
            "1000047771",
            "Intended",
            "Quantum communication call",
            "Description text",
            "05/11/2026",
        ],
        "/ESATenderActions/details/198254",
        row,
    ) == ESAStarTender(
        tender_action_number="5-50001",
        secondary_tender_number="1000047771",
        status="Intended",
        title="Quantum communication call",
        description="Description text",
        announcement_date="05/11/2026",
        url=(
            "https://esastar-publication-ext.sso.esa.int/"
            "ESATenderActions/details/198254"
        ),
        category="Quantum",
        technology_keyword="Quantum Communication",
        technology_tree_path=(
            "17 - Optoelectronics > E - Quantum Technologies > "
            "II - Quantum Communication"
        ),
        selected_tree_path=(
            "17 - Optoelectronics > E - Quantum Technologies > "
            "II - Quantum Communication"
        ),
    )


def test_parse_tender_card_rejects_missing_identifier_or_url():
    """@spec REQ-14"""
    row = esa_star_analysis.ESA_STAR_ROWS[0]
    with pytest.raises(ValueError, match="requires six values"):
        parse_tender_card(["one"], "/details/1", row)
    with pytest.raises(ValueError, match="missing its action number"):
        parse_tender_card(["", "secondary", "Intended", "Title", "", ""], None, row)


class _FakeCheckbox:
    def __init__(self, value: str, identifier: str):
        self.value = value
        self.identifier = identifier
        self.checked = False

    def count(self) -> int:
        return 1

    def is_checked(self) -> bool:
        return self.checked

    def get_attribute(self, name: str) -> str | None:
        assert name == "id"
        return self.identifier

    def check(self) -> None:
        self.checked = True


class _FakeToggle:
    def __init__(self):
        self.expanded = False

    def click(self) -> None:
        self.expanded = not self.expanded

    def is_visible(self) -> bool:
        return True

    def get_attribute(self, name: str) -> str | None:
        assert name == "aria-expanded"
        return str(self.expanded).lower()


class _FakeSearch:
    def __init__(self):
        self.text = ""

    def fill(self, value: str) -> None:
        self.text = value


class _FakeLabel:
    def __init__(self, checkbox: _FakeCheckbox):
        self.checkbox = checkbox

    def click(self) -> None:
        self.checkbox.checked = True


class _FakeClearButton:
    def count(self) -> int:
        return 0


class _FakeDropdown:
    def __init__(self, checkbox: _FakeCheckbox):
        self.checkbox = checkbox
        self.toggle = _FakeToggle()
        self.search = _FakeSearch()

    def count(self) -> int:
        return 1

    def locator(self, selector: str):
        if selector == '.dropdown-search':
            return self.toggle
        if selector == "input.searchTxt":
            return self.search
        if selector == 'input[type="checkbox"][value="DE"]':
            return self.checkbox
        if selector.startswith("input[type=") and self.checkbox.value in selector:
            return self.checkbox
        if selector.startswith("label[for="):
            return _FakeLabel(self.checkbox)
        raise AssertionError(f"Unexpected selector: {selector}")

    def get_by_role(self, role: str, name: str):
        assert role == "button"
        assert name == "Clear selection"
        return _FakeClearButton()


class _FakeFilterLabel:
    def __init__(self, dropdown: _FakeDropdown):
        self.dropdown = dropdown

    def count(self) -> int:
        return 1

    def locator(self, selector: str):
        if selector == "xpath=..":
            return self
        if selector == "ep-multi-checkbox-dropdown":
            return self.dropdown
        raise AssertionError(f"Unexpected selector: {selector}")


class _FakeFilterPage:
    def __init__(self):
        self.country = _FakeDropdown(_FakeCheckbox("DE", "country-de"))
        self.technology = _FakeDropdown(_FakeCheckbox("454", "technology-454"))

    def get_by_text(self, text: str, exact: bool):
        assert exact
        dropdowns = {
            "Country(ies)": self.country,
            "Technology Keywords": self.technology,
        }
        return _FakeFilterLabel(dropdowns[text])


def test_filter_helpers_select_country_de_and_resolved_tree_node():
    """@spec REQ-14"""
    page = _FakeFilterPage()
    node = TechnologyTreeNode(
        "D - Machine Learning and Artificial Intelligence for On-board Data Subsystems",
        "454",
        30,
    )

    _select_country_de(page)
    _select_technology_node(page, node)

    assert page.country.checkbox.is_checked()
    assert page.country.search.text == "Germany"
    assert page.technology.checkbox.is_checked()
    assert page.technology.search.text == node.label
    assert not page.country.toggle.expanded
    assert not page.technology.toggle.expanded


class _FakeText:
    def __init__(self, text: str, attributes: dict[str, str] | None = None):
        self.text = text
        self.attributes = attributes or {}

    def inner_text(self) -> str:
        return self.text

    def get_attribute(self, name: str) -> str | None:
        return self.attributes.get(name)


class _FakeList:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def count(self) -> int:
        return len(self.values)

    def nth(self, index: int):
        return self.values[index]

    @property
    def first(self):
        return self.values[0]


class _FakeTenderCard:
    def __init__(
        self,
        action_number: str,
        secondary_number: str,
        title: str,
        href: str,
        announcement_date: str,
    ):
        self.action_number = action_number
        self.secondary_number = secondary_number
        self.title = title
        self.href = href
        self.announcement_date = announcement_date

    def locator(self, selector: str):
        if selector == 'a[href*="/ESATenderActions/details/"]':
            return _FakeList(
                [
                    _FakeText(self.action_number, {"href": self.href}),
                    _FakeText(self.secondary_number, {"href": self.href}),
                ]
            )
        if selector == ".status span":
            return _FakeText("Intended")
        if selector == "h5.description.title a":
            return _FakeText(self.title)
        if selector == ".col2 > .description":
            return _FakeText("Tender description")
        raise AssertionError(f"Unexpected selector: {selector}")

    def inner_text(self) -> str:
        return f"{self.title}\nAnnouncement Date: {self.announcement_date}"


class _FakePageForPagination:
    def __init__(self, pages):
        self.pages = pages
        self.page_index = 0
        self.next_link = _FakeNextLink(self)

    def locator(self, selector: str):
        if selector == ".card.list-element.tender-action":
            return _FakeList(self.pages[self.page_index])
        if selector == 'a[aria-label="Next"]':
            return _FakeList([self.next_link])
        if selector == ".pagination li.page-item.active a.page-link":
            return _FakeList([_FakeText(str(self.page_index + 1))])
        raise AssertionError(f"Unexpected selector: {selector}")

    def wait_for_function(
        self, expression: str, arg: int, timeout: int
    ) -> None:
        assert "active" in expression
        assert timeout == 60000
        assert self.page_index + 1 > arg


class _FakeNextLink:
    def __init__(self, page: _FakePageForPagination):
        self.page = page

    @property
    def first(self):
        return self

    def count(self) -> int:
        return 1

    def locator(self, selector: str):
        assert selector == "xpath=.."
        class _Parent:
            def get_attribute(self, name: str) -> str:
                assert name == "class"
                if self.page.page_index + 1 >= len(self.page.pages):
                    return "page-item disabled"
                return "page-item"

            def __init__(self, page):
                self.page = page

        return _Parent(self.page)

    def click(self) -> None:
        self.page.page_index += 1


def test_collect_path_tenders_traverses_pages_and_deduplicates_by_url():
    """@spec REQ-14"""
    row = esa_star_analysis.ESA_STAR_ROWS[0]
    shared = _FakeTenderCard(
        "5-12345",
        "1000001234",
        "Shared call",
        "/ESATenderActions/details/1",
        "05/11/2026",
    )
    second = _FakeTenderCard(
        "5-12346",
        "1000001235",
        "Second call",
        "/ESATenderActions/details/2",
        "06/11/2026",
    )
    page = _FakePageForPagination([[shared], [shared, second]])

    tenders = _collect_path_tenders(page, row)

    assert [tender.tender_action_number for tender in tenders] == [
        "5-12345",
        "5-12346",
    ]
    assert page.page_index == 1


def test_merge_tender_keeps_all_row_categories_and_paths():
    """@spec REQ-14"""
    tenders: dict[str, ESAStarTender] = {}
    first = _tender()
    second = _tender(
        category="Cybersecurity",
        tree_path="2 - Root > III - Technology",
    )
    merge_tender(tenders, first)
    merge_tender(tenders, second)

    merged = tenders[tender_identity(first)]
    assert len(tenders) == 1
    assert merged.category == "AI / Data; Cybersecurity"
    assert merged.technology_tree_path == (
        "1 - Root > I - Technology; 2 - Root > III - Technology"
    )
    assert merged.selected_tree_path == (
        "1 - Root > I - Technology; 2 - Root > III - Technology"
    )


def test_duplicate_path_results_are_attributed_to_each_supplied_row():
    """@spec REQ-14"""
    row_a, row_b = (
        esa_star_analysis.ESA_STAR_ROWS[5],
        esa_star_analysis.ESA_STAR_ROWS[9],
    )
    tender = _tender(tree_path=row_a.tree_path_text)

    results = attribute_tenders_to_rows([tender], [row_a, row_b])

    assert [result.row.category for result in results] == [
        "AI / Data",
        "Cybersecurity",
    ]
    assert all(
        result.tenders[0].category == result.row.category
        for result in results
    )
    assert all(
        result.tenders[0].technology_tree_path == row_a.tree_path_text
        for result in results
    )
    assert all(
        result.tenders[0].selected_tree_path
        == result.row.selection_tree_path_text
        for result in results
    )


def test_history_persists_and_backs_up_only_changed_content(tmp_path: Path):
    """@spec REQ-08, REQ-14"""
    history = tmp_path / "seen_esa_star.json"
    first = _tender()
    second = _tender("https://example.test/details/2")

    save_seen_tenders([first], history)
    first_content = history.read_text(encoding="utf-8")
    save_seen_tenders([first, second, first], history)

    backup = Path(f"{history}.bk")
    assert backup.read_text(encoding="utf-8") == first_content
    assert load_seen_tenders(history) == [first, second]
    current_content = history.read_text(encoding="utf-8")
    backup_content = backup.read_text(encoding="utf-8")
    save_seen_tenders([first, second], history)
    assert history.read_text(encoding="utf-8") == current_content
    assert backup.read_text(encoding="utf-8") == backup_content


def test_load_seen_tenders_rejects_non_list_history(tmp_path: Path):
    """@spec REQ-08, REQ-14"""
    history = tmp_path / "seen_esa_star.json"
    history.write_text(json.dumps({"invalid": True}), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a JSON list"):
        load_seen_tenders(history)


def test_csv_export_includes_tree_path_and_backs_up_existing_file(tmp_path: Path):
    """@spec REQ-14"""
    output = tmp_path / "esa_star.csv"
    output.write_text("previous CSV", encoding="utf-8")
    tender = _tender()

    save_tenders_csv([tender], output)

    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert Path(f"{output}.bk").read_text(encoding="utf-8") == "previous CSV"
    assert rows[0] == [
        "tender_action_number",
        "secondary_tender_number",
        "status",
        "title",
        "description",
        "announcement_date",
        "category",
        "technology_keyword",
        "technology_tree_path",
        "selected_tree_path",
        "url",
    ]
    assert rows[1][-3:] == [
        "1 - Root > I - Technology",
        "1 - Root > I - Technology",
        tender.url,
    ]


def test_print_row_results_colors_category_and_keyword(capsys):
    """@spec REQ-14"""
    row = ESATechnologyRow(
        "Quantum",
        "Quantum Communication",
        ("17 - Optoelectronics", "E - Quantum Technologies", "II - Quantum Communication"),
    )

    print_row_results([ESARowSearchResult(row, ())])

    output = capsys.readouterr().out
    assert f"{THEME_COLOR}[Quantum]{COLOR_RESET}" in output
    assert f"{KEYWORD_COLOR}Quantum Communication{COLOR_RESET}" in output


def test_main_reports_each_row_and_saves_independent_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """@spec REQ-08, REQ-14"""
    first_row = esa_star_analysis.ESA_STAR_ROWS[0]
    row_results = [
        ESARowSearchResult(first_row, (_tender(),)),
        ESARowSearchResult(esa_star_analysis.ESA_STAR_ROWS[1], ()),
    ]
    saved: dict[str, object] = {}
    monkeypatch.setattr(
        "sys.argv",
        [
            "esa_star_analysis",
            "--seen-file",
            str(tmp_path / "history.json"),
            "--csv-file",
            str(tmp_path / "results.csv"),
        ],
    )
    monkeypatch.setattr(esa_star_analysis, "load_seen_tenders", lambda path: [])
    monkeypatch.setattr(
        esa_star_analysis,
        "search_esa_star_tenders",
        lambda headless: row_results,
    )
    monkeypatch.setattr(
        esa_star_analysis,
        "save_seen_tenders",
        lambda tenders, path: saved.update(history=list(tenders), seen_path=path),
    )
    monkeypatch.setattr(
        esa_star_analysis,
        "save_tenders_csv",
        lambda tenders, path: saved.update(csv=list(tenders), csv_path=path),
    )

    esa_star_analysis.main()

    output = capsys.readouterr().out
    assert first_row.tree_path_text in output
    assert first_row.selection_tree_path_text in output
    assert "Results: 1" in output
    assert "No matching intended calls." in output
    assert len(saved["history"]) == 1
    assert saved["seen_path"] == str(tmp_path / "history.json")
    assert len(saved["csv"]) == 1
    assert saved["csv_path"] == str(tmp_path / "results.csv")


def test_main_does_not_save_history_when_a_path_search_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    """@spec REQ-14"""
    saves: list[str] = []
    monkeypatch.setattr("sys.argv", ["esa_star_analysis"])
    monkeypatch.setattr(esa_star_analysis, "load_seen_tenders", lambda path: [])

    def fail_search(headless: bool):
        raise RuntimeError("ESA STAR filter failed")

    monkeypatch.setattr(
        esa_star_analysis, "search_esa_star_tenders", fail_search
    )
    monkeypatch.setattr(
        esa_star_analysis,
        "save_seen_tenders",
        lambda tenders, path: saves.append("history"),
    )
    monkeypatch.setattr(
        esa_star_analysis,
        "save_tenders_csv",
        lambda tenders, path: saves.append("csv"),
    )

    with pytest.raises(RuntimeError, match="ESA STAR filter failed"):
        esa_star_analysis.main()

    assert saves == []
