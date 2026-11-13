# =============================================================================
# Ausschreibungen Monitor — Monitor public procurement portals for IT-related tenders.
# Copyright attribution and application license have not been specified.
# Built with dbv-specs-ops · https://github.com/davidbuenov/dbv-specs-ops
# =============================================================================
"""Search ESA STAR calls by supplied and resolved tree paths. @spec REQ-08, REQ-14"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence, cast
from urllib.parse import urljoin

from analyse.terminal import COLOR_RESET, KEYWORD_COLOR, THEME_COLOR

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Allows parsing and CSV tests without Playwright installed.
    sync_playwright = None


ESA_STAR_BASE_URL = "https://esastar-publication-ext.sso.esa.int"
ESA_STAR_SEARCH_URL = (
    f"{ESA_STAR_BASE_URL}/ESATenderActions/filter/cfp_intended"
)
RESULTS_HEADING_PATTERN = re.compile(r"Results:\s*\d+\s+Items Found")


@dataclass(frozen=True, slots=True)
class ESATechnologyRow:
    category: str
    technology_keyword: str
    tree_path: tuple[str, ...]
    selection_tree_path: tuple[str, ...] | None = None

    @property
    def tree_path_text(self) -> str:
        return " > ".join(self.tree_path)

    @property
    def selection_tree_path_text(self) -> str:
        path = self.selection_tree_path or self.tree_path
        return " > ".join(path)


@dataclass(frozen=True, slots=True)
class TechnologyTreeNode:
    label: str
    value: str
    indentation: int


@dataclass(frozen=True, slots=True)
class ESAStarTender:
    tender_action_number: str
    secondary_tender_number: str
    status: str
    title: str
    description: str
    announcement_date: str
    url: str
    category: str
    technology_keyword: str
    technology_tree_path: str
    selected_tree_path: str


@dataclass(frozen=True, slots=True)
class ESARowSearchResult:
    row: ESATechnologyRow
    tenders: tuple[ESAStarTender, ...]


def _technology_row(
    category: str,
    keyword: str,
    *tree_path: str,
    selection_tree_path: tuple[str, ...] | None = None,
) -> ESATechnologyRow:
    return ESATechnologyRow(
        category, keyword, tree_path, selection_tree_path
    )


ESA_STAR_ROWS = (
    _technology_row(
        "AI / Data",
        "Machine Learning and Artificial Intelligence for On-board Data Subsystems",
        "1 - On-board Data Subsystems",
        "D - Machine Learning and Artificial Intelligence for On-board Data Subsystems",
    ),
    _technology_row(
        "AI / Data",
        "Machine Learning for On-board Data Subsystems",
        "1 - On-board Data Subsystems",
        "I - Machine Learning for On-board Data Subsystems",
        selection_tree_path=(
            "1 - On-board Data Subsystems",
            "D - Machine Learning and Artificial Intelligence for On-board Data Subsystems",
            "I - Machine Learning for On-board Data Subsystems",
        ),
    ),
    _technology_row(
        "AI / Data",
        "Characterisation and Evaluation of Machine Learning Techniques",
        "1 - On-board Data Subsystems",
        "II - Characterisation and Evaluation of Machine Learning Techniques",
        selection_tree_path=(
            "1 - On-board Data Subsystems",
            "D - Machine Learning and Artificial Intelligence for On-board Data Subsystems",
            "II - Characterisation and Evaluation of Machine Learning Techniques",
        ),
    ),
    _technology_row(
        "AI / Data",
        "Software Autonomy and Artificial Intelligence",
        "2 - Space System Software",
        "A - Software Technologies",
        "I - Software Autonomy and Artificial Intelligence",
    ),
    _technology_row(
        "AI / Data",
        "Ground Data Analytical Processing",
        "2 - Space System Software",
        "D - Ground Data Processing",
        "II - Ground Data Analytical Processing",
    ),
    _technology_row(
        "AI / Data",
        "Technologies for Data Security, Openness and Privacy",
        "2 - Space System Software",
        "D - Ground Data Processing",
        "III - Technologies for Data Security, Openness and Privacy",
    ),
    _technology_row(
        "Quantum",
        "Quantum Information Processing and Simulations",
        "17 - Optoelectronics",
        "E - Quantum Technologies",
        "III - Quantum Information Processing and Simulations",
    ),
    _technology_row(
        "Quantum",
        "Quantum Communication",
        "17 - Optoelectronics",
        "E - Quantum Technologies",
        "II - Quantum Communication",
    ),
    _technology_row(
        "Cybersecurity",
        "Telecom Security Techniques and Technologies",
        "6 - RF Subsystems, Payloads and Technologies",
        "A - Telecommunications Subsystems",
        "V - Telecom Security Techniques and Technologies",
        selection_tree_path=(
            "6 - RF Subsystems, Payloads and Technologies",
            "A - Telecommunication Subsystems",
            "V - Telecom Security Techniques and Technologies",
        ),
    ),
    _technology_row(
        "Cybersecurity",
        "Technologies for Data Security, Openness and Privacy",
        "2 - Space System Software",
        "D - Ground Data Processing",
        "III - Technologies for Data Security, Openness and Privacy",
    ),
    _technology_row(
        "Cybersecurity",
        "Software Security Process Assurance",
        "25 - Quality, Dependability and Safety",
        "B - Software Quality",
        "III - Software Security Process Assurance",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Planetary Robotic Exploration",
        "13 - Automation, Telepresence & Robotics",
        "A - Robotic Applications and Concepts",
        "I - Planetary Robotic Exploration",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Orbital Robotic Systems",
        "13 - Automation, Telepresence & Robotics",
        "A - Robotic Applications and Concepts",
        "II - Orbital Robotic Systems",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Manipulation Robotic Subsystems",
        "13 - Automation, Telepresence & Robotics",
        "B - Automation & Robotics Systems and Subsystems",
        "I - Manipulation Robotic Subsystems",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Mobility Robotic Systems",
        "13 - Automation, Telepresence & Robotics",
        "B - Automation & Robotics Systems and Subsystems",
        "II - Mobility Robotic Systems",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Perception for Robots",
        "13 - Automation, Telepresence & Robotics",
        "C - Automation & Robotics Components and Technologies",
        "I - Perception for Robots",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Control, Autonomy and Intelligence",
        "13 - Automation, Telepresence & Robotics",
        "C - Automation & Robotics Components and Technologies",
        "II - Control, Autonomy and Intelligence",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Motion and Actuation of Robots",
        "13 - Automation, Telepresence & Robotics",
        "C - Automation & Robotics Components and Technologies",
        "III - Motion and Actuation of Robots",
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Autonomy and FDIR",
        "5 - Space System Control",
        "A - Control (Sub-)Systems Engineering",
        "II - Autonomy and FDIR",
        selection_tree_path=(
            "5 - Space System Control",
            "A - Control (Sub-) Systems Engineering",
            "II - Autonomy and FDIR",
        ),
    ),
    _technology_row(
        "Robotics / Autonomous",
        "Advanced Control, Estimation & Optimisation",
        "5 - Space System Control",
        "C - Control Techniques and Tools",
        "II - Advanced Control, Estimation & Optimisation",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Methods and Tools for On-board Software Engineering Processes",
        "2 - Space System Software",
        "B - Space Segment Software",
        "I - Methods and Tools for On-board Software Engineering Processes",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Software Management Process",
        "2 - Space System Software",
        "B - Space Segment Software",
        "II - Software Management Process",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Software Architectures",
        "2 - Space System Software",
        "B - Space Segment Software",
        "III - Software Architectures",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Ground Segment Software",
        "2 - Space System Software",
        "C - Ground Segment Software",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Requirement Engineering",
        "8 - System Design & Verification",
        "A - Mission and System Specification",
        "II - Requirement Engineering",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "System Design and Simulation",
        "8 - System Design & Verification",
        "C - System Analysis and Design",
        "I - System Design and Simulation",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Distributed and Decentralised Operations",
        "9 - Mission Operation and Ground Data Systems",
        "B - Mission Operations",
        "I - Distributed and Decentralised Operations",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Automation, Autonomy and Mission Planning Concepts",
        "9 - Mission Operation and Ground Data Systems",
        "B - Mission Operations",
        "II - Automation, Autonomy and Mission Planning Concepts",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Mission Control System, Automation, Mission Planning, Simulators and Station M&C and Data Centre Architecture and Technologies",
        "9 - Mission Operation and Ground Data Systems",
        "C - Ground Data Systems",
        "II - Mission Control System, Automation, Mission Planning, Simulators and Station M&C and Data Centre Architecture and Technologies",
        selection_tree_path=(
            "9 - Mission Operation and Ground Data Systems",
            "C - Ground Data Systems",
            "I - Mission Control System, Automation, Mission Planning, Simulators and Station M&C and Data Centre Architecture and Technologies",
        ),
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Software Process Quality Techniques",
        "25 - Quality, Dependability and Safety",
        "B - Software Quality",
        "I - Software Process Quality Techniques",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Software Product Quality Techniques",
        "25 - Quality, Dependability and Safety",
        "B - Software Quality",
        "II - Software Product Quality Techniques",
    ),
    _technology_row(
        "Software / Digital Engineering",
        "Software Security Process Assurance",
        "25 - Quality, Dependability and Safety",
        "B - Software Quality",
        "III - Software Security Process Assurance",
    ),
)


def unique_tree_paths(
    rows: Iterable[ESATechnologyRow],
) -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for row in rows:
        path = row.selection_tree_path or row.tree_path
        if path not in paths:
            paths.append(path)
    result = tuple(paths)
    return result


def group_rows_by_path(
    rows: Iterable[ESATechnologyRow],
) -> dict[tuple[str, ...], tuple[ESATechnologyRow, ...]]:
    grouped: dict[tuple[str, ...], list[ESATechnologyRow]] = {}
    for row in rows:
        path = row.selection_tree_path or row.tree_path
        grouped.setdefault(path, []).append(row)
    result = {path: tuple(path_rows) for path, path_rows in grouped.items()}
    return result


def resolve_technology_tree_path(
    nodes: Iterable[TechnologyTreeNode],
    path: tuple[str, ...],
) -> str:
    """Return one checkbox value only when the complete parent path matches."""
    if not path:
        raise ValueError("An ESA Technology Tree path cannot be empty.")

    parents: list[tuple[int, str]] = []
    matches: list[str] = []
    for node in nodes:
        while parents and parents[-1][0] >= node.indentation:
            parents.pop()
        current_path = tuple(label for _, label in parents) + (node.label,)
        if current_path == path:
            matches.append(node.value)
        parents.append((node.indentation, node.label))

    if len(matches) != 1:
        raise ValueError(
            f"ESA Technology Tree path {' > '.join(path)!r} "
            f"matched {len(matches)} nodes; expected exactly one."
        )
    result = matches[0]
    return result


def parse_tender_card(
    values: Sequence[str],
    href: str | None,
    row: ESATechnologyRow,
) -> ESAStarTender:
    """Parse listing-card fields for one category/path row. @spec REQ-14"""
    if len(values) < 6:
        raise ValueError(
            "ESA STAR tender card requires six values: action number, "
            "secondary number, status, title, description, and announcement date."
        )

    tender_action_number = values[0].strip()
    secondary_tender_number = values[1].strip()
    status = values[2].strip()
    title = values[3].strip()
    description = values[4].strip()
    announcement_date = values[5].strip()
    if not tender_action_number or not title or not href:
        raise ValueError(
            f"ESA STAR tender card {title or tender_action_number!r} "
            "is missing its action number, title, or detail URL."
        )

    tender = ESAStarTender(
        tender_action_number=tender_action_number,
        secondary_tender_number=secondary_tender_number,
        status=status,
        title=title,
        description=description,
        announcement_date=announcement_date,
        url=urljoin(ESA_STAR_BASE_URL, href),
        category=row.category,
        technology_keyword=row.technology_keyword,
        technology_tree_path=row.tree_path_text,
        selected_tree_path=row.selection_tree_path_text,
    )
    return tender


def _filter_dropdown(page: Any, label: str) -> Any:
    label_locator = page.get_by_text(label, exact=True)
    if label_locator.count() != 1:
        raise ValueError(f"ESA STAR filter {label!r} was not uniquely found.")
    dropdown = label_locator.locator("xpath=..").locator(
        "ep-multi-checkbox-dropdown"
    )
    if dropdown.count() != 1:
        raise ValueError(f"ESA STAR filter {label!r} has no unique dropdown.")
    return dropdown


def _read_technology_tree_nodes(page: Any) -> list[TechnologyTreeNode]:
    dropdown = _filter_dropdown(page, "Technology Keywords")
    raw_nodes = cast(
        list[dict[str, str]],
        dropdown.locator(".single-line").evaluate_all(
            "(rows) => rows.map((row) => ({"
            "label: row.querySelector('label.custom-control-label')?.innerText.trim() || '',"
            "value: row.querySelector('input[type=checkbox]')?.value || '',"
            "indentation: row.style.paddingLeft || ''"
            "}))"
        ),
    )
    nodes: list[TechnologyTreeNode] = []
    for item in raw_nodes:
        indentation_match = re.fullmatch(r"(\d+)px", item["indentation"])
        if not item["label"] or not item["value"] or indentation_match is None:
            raise ValueError(
                "ESA STAR Technology Keywords tree contains an incomplete node."
            )
        nodes.append(
            TechnologyTreeNode(
                label=item["label"],
                value=item["value"],
                indentation=int(indentation_match.group(1)),
            )
        )
    return nodes


def _ensure_filter_panel_open(page: Any) -> None:
    country_dropdown = _filter_dropdown(page, "Country(ies)")
    if not country_dropdown.locator(".dropdown-search").is_visible():
        page.get_by_role(
            "heading", name=re.compile(r"^Filters")
        ).click()
        country_dropdown.locator(".dropdown-search").wait_for(
            state="visible", timeout=10000
        )


def _select_country_de(page: Any) -> None:
    dropdown = _filter_dropdown(page, "Country(ies)")
    checkbox = dropdown.locator('input[type="checkbox"][value="DE"]')
    if checkbox.count() != 1:
        raise ValueError("ESA STAR Country filter does not contain Germany (DE).")

    if not checkbox.is_checked():
        dropdown.locator(".dropdown-search").click()
        dropdown.locator("input.searchTxt").fill("Germany")
        checkbox_id = checkbox.get_attribute("id")
        if not checkbox_id:
            raise ValueError("ESA STAR Country DE checkbox has no identifier.")
        dropdown.locator(f'label[for="{checkbox_id}"]').click()
    if not checkbox.is_checked():
        raise ValueError("ESA STAR Country DE filter could not be selected.")
    if dropdown.locator(".dropdown-search").get_attribute("aria-expanded") == "true":
        dropdown.locator(".dropdown-search").click()


def _select_technology_node(page: Any, node: TechnologyTreeNode) -> None:
    dropdown = _filter_dropdown(page, "Technology Keywords")
    toggle = dropdown.locator(".dropdown-search")
    toggle.click()
    clear_button = dropdown.get_by_role("button", name="Clear selection")
    if clear_button.count() and clear_button.is_visible():
        clear_button.click()

    dropdown.locator("input.searchTxt").fill(node.label)
    checkbox = dropdown.locator(
        f'input[type="checkbox"][value="{node.value}"]'
    )
    if checkbox.count() != 1:
        raise ValueError(
            f"ESA STAR Technology Tree node {node.label!r} "
            "could not be uniquely selected."
        )
    checkbox_id = checkbox.get_attribute("id")
    if not checkbox_id:
        raise ValueError(
            f"ESA STAR Technology Tree node {node.label!r} has no identifier."
        )
    dropdown.locator(f'label[for="{checkbox_id}"]').click()
    if not checkbox.is_checked():
        raise ValueError(
            f"ESA STAR Technology Tree node {node.label!r} was not selected."
        )
    toggle.click()


def _wait_for_results(page: Any) -> None:
    page.get_by_role("heading", name=RESULTS_HEADING_PATTERN).wait_for(
        state="visible", timeout=60000
    )


def _extract_page_tenders(
    page: Any,
    row: ESATechnologyRow,
) -> list[ESAStarTender]:
    tenders: dict[str, ESAStarTender] = {}
    cards = page.locator(".card.list-element.tender-action").all()
    for card in cards:
        links = card.locator('a[href*="/ESATenderActions/details/"]')
        if links.count() < 2:
            raise ValueError("ESA STAR tender card has incomplete detail links.")

        action_number = links.nth(0).inner_text().strip()
        secondary_number = links.nth(1).inner_text().strip()
        status = card.locator(".status span").inner_text().strip()
        title = card.locator("h5.description.title a").inner_text().strip()
        description = card.locator(".col2 > .description").inner_text().strip()
        card_text = card.inner_text()
        date_match = re.search(
            r"Announcement Date:\s*(\d{2}/\d{2}/\d{4})",
            card_text,
            flags=re.IGNORECASE,
        )
        announcement_date = date_match.group(1) if date_match else ""
        href = links.nth(0).get_attribute("href")
        tender = parse_tender_card(
            [
                action_number,
                secondary_number,
                status,
                title,
                description,
                announcement_date,
            ],
            href,
            row,
        )
        merge_tender(tenders, tender)
    result = list(tenders.values())
    return result


def _current_page_number(page: Any) -> int:
    active_page = page.locator(
        ".pagination li.page-item.active a.page-link"
    ).first
    text = active_page.inner_text().strip()
    match = re.search(r"\d+", text)
    if match is None:
        raise ValueError(f"Cannot read ESA STAR current page number: {text!r}")
    result = int(match.group())
    return result


def _has_next_page(page: Any) -> bool:
    next_links = page.locator('a[aria-label="Next"]')
    has_next = False
    if next_links.count():
        parent_class = next_links.first.locator("xpath=..").get_attribute(
            "class"
        ) or ""
        has_next = "disabled" not in parent_class.split()
    return has_next


def _collect_path_tenders(
    page: Any,
    row: ESATechnologyRow,
) -> tuple[ESAStarTender, ...]:
    unique: dict[str, ESAStarTender] = {}
    while True:
        for tender in _extract_page_tenders(page, row):
            merge_tender(unique, tender)

        if not _has_next_page(page):
            break
        current_page = _current_page_number(page)
        next_link = page.locator('a[aria-label="Next"]').first
        next_link.click()
        page.wait_for_function(
            "(previous) => {"
            "const active = document.querySelector("
            "'.pagination li.page-item.active a.page-link');"
            "return active && Number.parseInt(active.innerText, 10) > previous;"
            "}",
            arg=current_page,
            timeout=60000,
        )

    result = tuple(unique.values())
    return result


def _search_one_path(
    page: Any,
    row: ESATechnologyRow,
    node: TechnologyTreeNode,
) -> tuple[ESAStarTender, ...]:
    _select_technology_node(page, node)
    page.get_by_role("button", name="Apply").click()
    _wait_for_results(page)
    result = _collect_path_tenders(page, row)
    return result


def attribute_tenders_to_rows(
    tenders: Iterable[ESAStarTender],
    rows: Iterable[ESATechnologyRow],
) -> list[ESARowSearchResult]:
    path_tenders = tuple(tenders)
    row_results: list[ESARowSearchResult] = []
    for row in rows:
        row_tenders = tuple(
            replace(
                tender,
                category=row.category,
                technology_keyword=row.technology_keyword,
                technology_tree_path=row.tree_path_text,
                selected_tree_path=row.selection_tree_path_text,
            )
            for tender in path_tenders
        )
        row_results.append(
            ESARowSearchResult(row=row, tenders=row_tenders)
        )
    result = row_results
    return result


def search_esa_star_tenders(
    rows: Iterable[ESATechnologyRow] = ESA_STAR_ROWS,
    headless: bool = True,
) -> list[ESARowSearchResult]:
    """Search each full tree path and report results per supplied row. @spec REQ-14"""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && "
            "python -m playwright install"
        )

    row_list = tuple(rows)
    if not row_list:
        return []

    grouped_rows = group_rows_by_path(row_list)
    row_results: list[ESARowSearchResult] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(
                ESA_STAR_SEARCH_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            _wait_for_results(page)
            _ensure_filter_panel_open(page)
            _select_country_de(page)
            nodes = _read_technology_tree_nodes(page)
            resolved_nodes = {
                path: resolve_technology_tree_path(nodes, path)
                for path in grouped_rows
            }

            for path, path_rows in grouped_rows.items():
                representative = path_rows[0]
                node_value = resolved_nodes[path]
                node = next(
                    item
                    for item in nodes
                    if item.value == node_value
                )
                path_tenders = _search_one_path(page, representative, node)
                row_results.extend(
                    attribute_tenders_to_rows(path_tenders, path_rows)
                )
        finally:
            browser.close()

    result = row_results
    return result


def tender_identity(tender: ESAStarTender) -> str:
    identity = tender.url
    return identity


def _merge_metadata(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for item in value.split("; "):
            item = item.strip()
            if item and item not in merged:
                merged.append(item)
    result = "; ".join(merged)
    return result


def merge_tender(
    tenders: dict[str, ESAStarTender],
    tender: ESAStarTender,
) -> None:
    key = tender_identity(tender)
    existing = tenders.get(key)
    if existing is None:
        tenders[key] = replace(
            tender,
            category=_merge_metadata(tender.category),
            technology_keyword=_merge_metadata(tender.technology_keyword),
            technology_tree_path=_merge_metadata(
                tender.technology_tree_path
            ),
            selected_tree_path=_merge_metadata(tender.selected_tree_path),
        )
    else:
        tenders[key] = replace(
            existing,
            category=_merge_metadata(existing.category, tender.category),
            technology_keyword=_merge_metadata(
                existing.technology_keyword,
                tender.technology_keyword,
            ),
            technology_tree_path=_merge_metadata(
                existing.technology_tree_path,
                tender.technology_tree_path,
            ),
            selected_tree_path=_merge_metadata(
                existing.selected_tree_path,
                tender.selected_tree_path,
            ),
        )


def print_row_results(row_results: Iterable[ESARowSearchResult]) -> None:
    for row_result in row_results:
        row = row_result.row
        print(
            f"\n{THEME_COLOR}[{row.category}]{COLOR_RESET} "
            f"{KEYWORD_COLOR}{row.technology_keyword}{COLOR_RESET}\n"
            f"  ESA Technology Tree path: {row.tree_path_text}\n"
            f"  Selected live ESA path: {row.selection_tree_path_text}\n"
            f"  Results: {len(row_result.tenders)}"
        )
        if not row_result.tenders:
            print("  No matching intended calls.")
        for tender in row_result.tenders:
            print(
                f"  - {tender.tender_action_number} | {tender.status} | "
                f"{tender.announcement_date} | {tender.title}"
            )
            print(f"    {tender.url}")


def load_seen_tenders(seen_file: str | Path) -> list[ESAStarTender]:
    """Load this portal's independent JSON history. @spec REQ-08, REQ-14"""
    path = Path(seen_file)
    tenders: list[ESAStarTender] = []
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if content.strip():
            payload: Any = json.loads(content)
            if not isinstance(payload, list):
                raise ValueError(f"Expected a JSON list in {path}")
            for raw_item in cast(list[object], payload):
                if not isinstance(raw_item, dict):
                    raise ValueError(f"Expected ESA STAR tender objects in {path}")
                item = cast(dict[str, Any], raw_item)
                tenders.append(
                    ESAStarTender(
                        tender_action_number=str(
                            item.get("tender_action_number", "")
                        ),
                        secondary_tender_number=str(
                            item.get("secondary_tender_number", "")
                        ),
                        status=str(item.get("status", "")),
                        title=str(item.get("title", "")),
                        description=str(item.get("description", "")),
                        announcement_date=str(
                            item.get("announcement_date", "")
                        ),
                        url=str(item.get("url", "")),
                        category=str(item.get("category", "")),
                        technology_keyword=str(
                            item.get("technology_keyword", "")
                        ),
                        technology_tree_path=str(
                            item.get("technology_tree_path", "")
                        ),
                        selected_tree_path=str(
                            item.get(
                                "selected_tree_path",
                                item.get("technology_tree_path", ""),
                            )
                        ),
                    )
                )
    return tenders


def backup_existing_file(file_path: str | Path) -> None:
    path = Path(file_path)
    if path.exists():
        shutil.copy2(path, Path(f"{path}.bk"))


def save_seen_tenders(
    tenders: Iterable[ESAStarTender],
    seen_file: str | Path,
) -> None:
    """Persist this portal's independent JSON history. @spec REQ-08, REQ-14"""
    path = Path(seen_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    unique: dict[str, ESAStarTender] = {}
    for tender in tenders:
        merge_tender(unique, tender)

    content = json.dumps(
        [asdict(tender) for tender in unique.values()],
        indent=2,
        ensure_ascii=False,
    )
    if path.exists():
        previous_content = path.read_text(encoding="utf-8")
        if previous_content != content:
            backup_existing_file(path)
            path.write_text(content, encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def save_tenders_csv(
    tenders: Iterable[ESAStarTender],
    output_file: str | Path,
) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    backup_existing_file(output_path)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
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
        )
        for tender in tenders:
            writer.writerow(
                [
                    tender.tender_action_number,
                    tender.secondary_tender_number,
                    tender.status,
                    tender.title,
                    tender.description,
                    tender.announcement_date,
                    tender.category,
                    tender.technology_keyword,
                    tender.technology_tree_path,
                    tender.selected_tree_path,
                    tender.url,
                ]
            )


def main() -> None:
    """Run ESA STAR search with independent history and optional CSV. @spec REQ-14"""
    parser = argparse.ArgumentParser(
        description=(
            "Search ESA STAR intended calls for Germany and selected "
            "ESA Technology Tree paths."
        )
    )
    parser.add_argument(
        "--headed", action="store_true", help="Show the browser while searching."
    )
    parser.add_argument("--seen-file", default="output/seen_esa_star.json")
    parser.add_argument(
        "--csv-file",
        help="Optionally export the accumulated ESA STAR history as CSV.",
    )
    args = parser.parse_args()

    seen_tenders = load_seen_tenders(args.seen_file)
    seen_keys = {tender_identity(tender) for tender in seen_tenders}
    row_results = search_esa_star_tenders(headless=not args.headed)
    print_row_results(row_results)

    current: dict[str, ESAStarTender] = {}
    for row_result in row_results:
        for tender in row_result.tenders:
            merge_tender(current, tender)

    saved: dict[str, ESAStarTender] = {}
    for tender in [*seen_tenders, *current.values()]:
        merge_tender(saved, tender)
    save_seen_tenders(saved.values(), args.seen_file)

    if args.csv_file:
        save_tenders_csv(saved.values(), args.csv_file)

    new_count = sum(
        tender_identity(tender) not in seen_keys
        for tender in current.values()
    )
    print(
        f"History contains {len(saved)} tenders total; "
        f"{new_count} new tenders this run."
    )


if __name__ == "__main__":
    main()
