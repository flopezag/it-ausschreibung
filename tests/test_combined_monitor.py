from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from analyse import brandenburg_analysis, bw_analysis, dtvp_analysis, giz_analysis
from analyse import cli as analyse_cli
from analyse import combined_monitor
from analyse.models import Tender


def _history_paths(tmp_path: Path) -> dict[str, str]:
    return {
        source: str(tmp_path / f"{index}.json")
        for index, source in enumerate(combined_monitor.HISTORY_FILES)
    }


def test_deduplicate_notices_requires_all_reference_fields():
    first = combined_monitor.CombinedNotice(
        "IT-Ausschreibung",
        "06.11.2026",
        "",
        "Multi-LLM platform",
        "",
        "20355 Hamburg",
        "AI",
        "llm",
        "https://Example.com/tender/",
    )
    duplicate = combined_monitor.CombinedNotice(
        "DTVP",
        "2026-11-06",
        "07.12.2026",
        " multi-llm   PLATFORM ",
        "Public",
        "20355   Hamburg",
        "Software",
        "large language model",
        "https://example.com/tender",
    )
    variants = [
        replace(first, title="Different title"),
        replace(first, published="07.11.2026"),
        replace(first, client="20356 Hamburg"),
        replace(first, url="https://example.com/other"),
    ]

    merged = combined_monitor.deduplicate_notices(
        [first, duplicate, *variants]
    )

    assert len(merged) == 5
    assert merged[0].source == "IT-Ausschreibung; DTVP"
    assert merged[0].theme == "AI; Software"
    assert merged[0].keyword == "llm; large language model"


def test_monitor_all_exports_unique_results_and_keeps_source_histories(
    tmp_path, monkeypatch, capsys
):
    """@spec REQ-10 Run all sources and export unique current-run results."""
    monkeypatch.setattr(
        combined_monitor, "HISTORY_FILES", _history_paths(tmp_path)
    )
    tender = Tender(
        "Multi-LLM platform",
        "https://example.com/tender",
        published="06.11.2026",
        deadline="07.12.2026",
        publication_type="Öffentliche Ausschreibung",
        publisher="20355 Hamburg",
    )
    def search_it_ausschreibung(keywords, headless):
        print("unified portal's duplicate result")
        return {"llm": [tender]}

    monkeypatch.setattr(
        combined_monitor, "search_tenders_by_keyword", search_it_ausschreibung
    )
    monkeypatch.setattr(
        dtvp_analysis,
        "search_dtvp_announcements",
        lambda headless, seen_keys: [
            dtvp_analysis.DtvpAnnouncement(
                "2026-11-06",
                "07.12.2026",
                "Multi-LLM platform",
                "Öffentliche Ausschreibung",
                "20355 Hamburg",
                "large language model",
                "https://example.com/tender",
                "Software",
            )
        ],
    )
    monkeypatch.setattr(
        brandenburg_analysis,
        "search_brandenburg_projects",
        lambda headless, seen_keys: [
            brandenburg_analysis.BrandenburgProject(
                "06.11.2026",
                "07.12.2026",
                "Multi-LLM platform",
                "Öffentliche Ausschreibung",
                "20355 Hamburg",
                "Sprachmodell",
                "https://example.com/tender",
                "AI",
            )
        ],
    )
    monkeypatch.setattr(
        bw_analysis, "search_bw_projects", lambda headless, seen_keys: []
    )
    monkeypatch.setattr(
        giz_analysis, "search_giz_announcements", lambda headless, seen_keys: []
    )

    output = tmp_path / "combined.csv"
    assert combined_monitor.run_combined_monitor(
        headless=False,
        csv_file=output,
        keyword_groups={"AI": ("llm",)},
    ) == 0

    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert list(rows[0]) == list(combined_monitor.CSV_COLUMNS)
    assert len(rows) == 1
    assert rows[0]["source"] == "IT-Ausschreibung; DTVP; Brandenburg"
    assert rows[0]["published"] == "06.11.2026"
    assert rows[0]["client"] == "20355 Hamburg"
    assert rows[0]["url"] == "https://example.com/tender"
    printed = capsys.readouterr().out
    assert "Baden-Württemberg: OK; 0 current match(es)." in printed
    assert "unified portal's duplicate result" not in printed
    assert printed.count("Multi-LLM platform") == 1
    assert (
        "[IT-Ausschreibung; DTVP; Brandenburg | themes: AI, Software | "
        "keywords: llm, large language model, Sprachmodell]"
    ) in printed
    assert Path(_history_paths(tmp_path)["DTVP"]).exists()
    assert Path(_history_paths(tmp_path)["Brandenburg"]).exists()
    assert Path(_history_paths(tmp_path)["Baden-Württemberg"]).exists()
    assert Path(_history_paths(tmp_path)["GIZ"]).exists()

    previous_csv = output.read_text(encoding="utf-8")
    assert combined_monitor.run_combined_monitor(
        headless=False,
        csv_file=output,
        keyword_groups={"AI": ("llm",)},
    ) == 0
    assert Path(f"{output}.bk").read_text(encoding="utf-8") == previous_csv


def test_monitor_all_continues_after_failure_without_replacing_failed_history(
    tmp_path, monkeypatch, capsys
):
    """@spec REQ-10 Continue later sources without changing failed history."""
    history_files = _history_paths(tmp_path)
    monkeypatch.setattr(combined_monitor, "HISTORY_FILES", history_files)
    history_path = Path(history_files["DTVP"])
    old_history = [
        asdict(
            dtvp_analysis.DtvpAnnouncement(
                "01.11.2026",
                "30.11.2026",
                "Saved result",
                "Public",
                "Client",
                "AI",
                "https://example.com/saved",
                "AI",
            )
        )
    ]
    history_path.write_text(json.dumps(old_history), encoding="utf-8")
    old_content = history_path.read_text(encoding="utf-8")
    later_sources: list[str] = []

    monkeypatch.setattr(
        combined_monitor,
        "search_tenders_by_keyword",
        lambda keywords, headless: {},
    )
    monkeypatch.setattr(
        dtvp_analysis,
        "search_dtvp_announcements",
        lambda headless, seen_keys: (_ for _ in ()).throw(
            RuntimeError("DTVP unavailable")
        ),
    )
    monkeypatch.setattr(
        brandenburg_analysis,
        "search_brandenburg_projects",
        lambda headless, seen_keys: later_sources.append("Brandenburg") or [],
    )
    monkeypatch.setattr(
        bw_analysis,
        "search_bw_projects",
        lambda headless, seen_keys: later_sources.append("Baden-Württemberg") or [],
    )
    monkeypatch.setattr(
        giz_analysis,
        "search_giz_announcements",
        lambda headless, seen_keys: later_sources.append("GIZ") or [],
    )

    status = combined_monitor.run_combined_monitor(
        keyword_groups={"AI": ("llm",)}
    )

    assert status == 1
    assert later_sources == ["Brandenburg", "Baden-Württemberg", "GIZ"]
    assert history_path.read_text(encoding="utf-8") == old_content
    output = capsys.readouterr().out
    assert "DTVP: FAILED (RuntimeError: DTVP unavailable)" in output
    assert "GIZ: OK; 0 current match(es)." in output


def test_monitor_all_cli_passes_options_and_returns_failure_status(
    monkeypatch,
):
    """@spec REQ-10 Expose monitor-all options and failures through the CLI."""
    monkeypatch.setattr(
        "sys.argv",
        ["analyse.py", "monitor-all", "--csv-file", "combined.csv", "--headed"],
    )
    calls = {}

    def run_combined_monitor(**kwargs):
        calls.update(kwargs)
        return 1

    monkeypatch.setattr(
        combined_monitor, "run_combined_monitor", run_combined_monitor
    )

    with pytest.raises(SystemExit) as error:
        analyse_cli.main()

    assert error.value.code == 1
    assert calls == {
        "headless": False,
        "csv_file": "combined.csv",
        "keyword_groups": analyse_cli.THEME_KEYWORDS,
    }


def test_monitor_all_reports_csv_export_failure(tmp_path, monkeypatch, capsys):
    """@spec REQ-10 Report an unwritable combined CSV and fail the command."""
    monkeypatch.setattr(
        combined_monitor, "HISTORY_FILES", _history_paths(tmp_path)
    )
    monkeypatch.setattr(
        combined_monitor, "search_tenders_by_keyword", lambda keywords, headless: {}
    )
    monkeypatch.setattr(
        dtvp_analysis, "search_dtvp_announcements", lambda headless, seen_keys: []
    )
    monkeypatch.setattr(
        brandenburg_analysis,
        "search_brandenburg_projects",
        lambda headless, seen_keys: [],
    )
    monkeypatch.setattr(
        bw_analysis, "search_bw_projects", lambda headless, seen_keys: []
    )
    monkeypatch.setattr(
        giz_analysis, "search_giz_announcements", lambda headless, seen_keys: []
    )
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("block export", encoding="utf-8")

    status = combined_monitor.run_combined_monitor(
        csv_file=parent_file / "combined.csv",
        keyword_groups={},
    )

    assert status == 1
    assert "Combined CSV export failed: FileExistsError" in capsys.readouterr().out
