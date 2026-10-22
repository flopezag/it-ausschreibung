import sys
from pathlib import Path
import json
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import analyse
from analyse import Tender
from analyse import cli as analyse_cli
from analyse import browser_search
from analyse.monitor import monitor


class FakeLink:
    def __init__(self, text, href):
        self._text = text
        self._href = href

    def inner_text(self):
        return self._text

    def get_attribute(self, name):
        assert name == "href"
        return self._href


class FakeLocator:
    def __init__(self, links):
        self._links = links

    def all(self):
        return self._links


class FakePage:
    def __init__(self, links):
        self._links = links

    def locator(self, selector):
        assert selector == "a[href*='/ausschreibung/']"
        return FakeLocator(self._links)


def test_extract_tenders_filters_navigation_and_duplicates():
    page = FakePage(
        [
            FakeLink("Cookies", "#"),
            FakeLink("Ausschreibungen suchen", "/ausschreibungen"),
            FakeLink("IT Security Consultancy", "/ausschreibung/139708/it-security-consultancy"),
            FakeLink("Duplicate title", "/ausschreibung/139708/it-security-consultancy"),
            FakeLink("Second Result", "https://www.it-ausschreibung.de/ausschreibung/139709/second-result"),
            FakeLink("", "/ausschreibung/139710/no-title"),
        ]
    )

    tenders = analyse.extract_tenders_from_page(page)

    assert tenders == [
        Tender(title="Duplicate title", url="https://www.it-ausschreibung.de/ausschreibung/139708/it-security-consultancy"),
        Tender(title="Second Result", url="https://www.it-ausschreibung.de/ausschreibung/139709/second-result"),
    ]


def test_search_tenders_by_keyword_preserves_keyword_matches(monkeypatch):
    class FakeLocator:
        def __init__(self, page):
            self.page = page
            self.first = self

        def click(self, timeout=None):
            pass

        def fill(self, value):
            self.page.keyword = value

    class FakePage:
        def __init__(self):
            self.keyword = ""

        def goto(self, url, wait_until):
            pass

        def get_by_role(self, role, name):
            return FakeLocator(self)

        def locator(self, selector):
            return FakeLocator(self)

        def wait_for_load_state(self, state):
            pass

        def close(self):
            pass

    class FakeBrowser:
        def new_page(self):
            return FakePage()

        def close(self):
            pass

    class FakePlaywright:
        def __init__(self):
            self.chromium = self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def launch(self, headless):
            return FakeBrowser()

    expected = {
        "KI": [Tender("AI tender", "https://example.com/ai")],
        "atex": [Tender("Safety tender", "https://example.com/safety")],
    }
    monkeypatch.setattr(browser_search, "sync_playwright", FakePlaywright)
    monkeypatch.setattr(
        browser_search,
        "extract_tenders_from_page",
        lambda page: expected[page.keyword],
    )

    assert browser_search.search_tenders_by_keyword(["KI", "atex"]) == expected


def test_save_results_csv(tmp_path):
    output = tmp_path / "results.csv"
    analyse.save_results_csv(
        [
            Tender("One", "https://example.com/1"),
            Tender("Two", "https://example.com/2"),
        ],
        output,
    )

    assert output.read_text(encoding="utf-8").splitlines() == [
        "title,url",
        "One,https://example.com/1",
        "Two,https://example.com/2",
    ]


def test_seen_urls_roundtrip(tmp_path):
    seen_file = tmp_path / "seen.json"

    assert analyse.load_seen_urls(seen_file) == set()

    analyse.save_seen_urls(["b", "a", "a"], seen_file)

    assert json.loads(seen_file.read_text(encoding="utf-8")) == ["a", "b"]
    assert analyse.load_seen_urls(seen_file) == {"a", "b"}


def test_seen_urls_merge_existing_entries(tmp_path):
    seen_file = tmp_path / "seen.json"

    analyse.save_seen_urls(["https://example.com/old"], seen_file)
    previous_content = seen_file.read_text(encoding="utf-8")
    analyse.save_seen_urls(["https://example.com/new"], seen_file)

    assert Path(f"{seen_file}.bk").read_text(encoding="utf-8") == previous_content
    assert analyse.load_seen_urls(seen_file) == {
        "https://example.com/old",
        "https://example.com/new",
    }


def test_seen_urls_noop_save_preserves_last_changed_backup(tmp_path):
    seen_file = tmp_path / "seen.json"

    analyse.save_seen_urls(["https://example.com/old"], seen_file)
    previous_content = seen_file.read_text(encoding="utf-8")
    analyse.save_seen_urls(["https://example.com/new"], seen_file)
    updated_content = seen_file.read_text(encoding="utf-8")
    backup_file = Path(f"{seen_file}.bk")
    assert backup_file.read_text(encoding="utf-8") == previous_content

    analyse.save_seen_urls(["https://example.com/old"], seen_file)

    assert seen_file.read_text(encoding="utf-8") == updated_content
    assert backup_file.read_text(encoding="utf-8") == previous_content


def test_seen_urls_preserves_previous_keyword_batch(tmp_path):
    seen_file = tmp_path / "seen.json"

    analyse.save_seen_urls(["https://example.com/old"], seen_file, keyword="penetration")
    analyse.save_seen_urls(["https://example.com/new"], seen_file, keyword="penetration")

    assert analyse.load_seen_urls(seen_file, keyword="penetration") == {
        "https://example.com/old",
        "https://example.com/new",
    }


def test_seen_urls_supports_keyword_buckets(tmp_path):
    seen_file = tmp_path / "seen.json"

    analyse.save_seen_urls(["https://example.com/cloud"], seen_file, keyword="cloud")
    analyse.save_seen_urls(["https://example.com/security"], seen_file, keyword="security")

    assert analyse.load_seen_urls(seen_file, keyword="cloud") == {
        "https://example.com/cloud",
    }
    assert analyse.load_seen_urls(seen_file, keyword="security") == {
        "https://example.com/security",
    }
    assert analyse.load_seen_urls(seen_file) == {
        "https://example.com/cloud",
        "https://example.com/security",
    }


def test_find_new_tenders():
    tenders = [
        Tender("Old", "https://example.com/old"),
        Tender("New", "https://example.com/new"),
    ]

    assert analyse.find_new_tenders(tenders, {"https://example.com/old"}) == [
        Tender("New", "https://example.com/new")
    ]


def test_build_email_body():
    body = analyse.build_email_body(
        "penetration",
        [Tender("IT Security Consultancy", "https://example.com/tender")],
    )

    assert "penetration" in body
    assert "IT Security Consultancy" in body
    assert "https://example.com/tender" in body


def test_build_email_body_accepts_multiple_keywords():
    body = analyse.build_email_body(
        ["penetration", "it security"],
        [Tender("IT Security Consultancy", "https://example.com/tender")],
    )

    assert "penetration, it security" in body
    assert "IT Security Consultancy" in body


def test_build_email_body_lists_keywords_that_matched_each_tender():
    first = Tender("First tender", "https://example.com/first")
    second = Tender("Second tender", "https://example.com/second")

    body = analyse.build_email_body(
        {"AI": ("KI", "chatbot"), "Robotics": ("atex",)},
        [first, second],
        {
            first.url: ["KI", "chatbot"],
            second.url: ["atex"],
        },
    )

    assert "Matched keyword(s): KI, chatbot" in body
    assert "Matched keyword(s): atex" in body


def test_parse_keyword_arg_splits_comma_separated_values():
    parsed = analyse.parse_keyword_arg("penetration, it security, cloud")
    assert parsed == ["penetration", "it security", "cloud"]


def test_parse_keyword_arg_parses_json_dict():
    parsed = analyse.parse_keyword_arg('{"a":"penetration","b":"it security"}')
    assert parsed == {"a": "penetration", "b": "it security"}


def test_monitor_searches_all_theme_groups_and_deduplicates_results(
    tmp_path, monkeypatch, capsys
):
    seen_file = tmp_path / "seen.json"
    theme_groups = {
        "AI": ("chatbot", "llm"),
        "Quantum": ("qml",),
    }
    previously_seen = Tender("Previously seen", "https://example.com/seen")
    shared = Tender("Shared result", "https://example.com/shared")
    new = Tender("New result", "https://example.com/new")
    analyse.save_seen_urls([previously_seen.url], seen_file, keyword="AI")
    search_results = {
        ("chatbot", "llm"): {
            "chatbot": [previously_seen, shared],
            "llm": [shared],
        },
        ("qml",): {"qml": [shared, new]},
    }
    calls = []

    def fake_search(keyword, headless):
        calls.append((keyword, headless))
        return search_results[tuple(keyword)]

    monkeypatch.setitem(
        monitor.__globals__, "search_tenders_by_keyword", fake_search
    )

    new_tenders = monitor(theme_groups, seen_file, headless=False)

    assert calls == [(["chatbot", "llm"], False), (["qml"], False)]
    assert new_tenders == [shared, new]
    assert analyse.load_seen_urls(seen_file, keyword="AI") == {
        previously_seen.url,
        shared.url,
    }
    assert analyse.load_seen_urls(seen_file, keyword="Quantum") == {
        shared.url,
        new.url,
    }
    output = capsys.readouterr().out
    assert output.count("\033[96mMonitoring theme:") == 2
    assert output.count("\033[93mMonitoring keyword:") == 3
    assert "\033[96mMonitoring theme: AI\033[0m" in output
    assert "\033[93mMonitoring keyword: chatbot\033[0m" in output
    assert "Matched keyword(s): chatbot, llm, qml" in output
    assert "Matched keyword(s): qml" in output
    assert "Monitoring IT-Ausschreibung tenders for keyword: " \
        "AI: chatbot, llm, Quantum: qml" in output
    assert "- Shared result" in output


def test_cli_monitor_defaults_to_all_configured_theme_keywords(
    monkeypatch, capsys
):
    monkeypatch.setattr("sys.argv", ["analyse.py", "monitor"])
    called = {}

    def fake_monitor(**kwargs):
        called.update(kwargs)
        return []

    monkeypatch.setattr(analyse_cli, "monitor", fake_monitor)

    analyse_cli.main()

    assert called["keyword"] == analyse_cli.THEME_KEYWORDS
    assert called["seen_file"] == "seen.json"
    assert capsys.readouterr().out == "No new tenders found.\n"


def test_cli_search_defaults_to_each_configured_theme(
    monkeypatch, capsys
):
    monkeypatch.setattr("sys.argv", ["analyse.py", "search"])
    calls = []

    def fake_search(keywords, headless):
        calls.append((keywords, headless))
        return [Tender(keywords[0], "https://example.com/shared")]

    monkeypatch.setattr(analyse_cli, "search_tenders", fake_search)

    analyse_cli.main()

    assert calls == [
        (keywords, True)
        for keywords in analyse_cli.THEME_KEYWORDS.values()
    ]
    output = capsys.readouterr().out
    assert output.count("\033[96mMonitoring theme:") == len(
        analyse_cli.THEME_KEYWORDS
    )
    assert output.count("\033[93mMonitoring keyword:") == sum(
        len(keywords) for keywords in analyse_cli.THEME_KEYWORDS.values()
    )
    assert "\033[96mMonitoring theme: AI\033[0m" in output
    assert "\033[93mMonitoring keyword: chatbot\033[0m" in output
    assert output.count("https://example.com/shared") == 1


def test_cli_theme_keywords_cover_every_term_from_check():
    assert {
        keyword
        for theme_keywords in analyse_cli.THEME_KEYWORDS.values()
        for keyword in theme_keywords
    } == {
        "penetration",
        "chatbot",
        "llm",
        "KI",
        "roboter",
        "drohne",
        "quantum",
        "quanten",
        "generative",
        "predictive",
        "qml",
        "qnn",
        "pqc",
        "pet",
        "red",
        "blue",
        "inspektion",
        "atex",
    }


@patch("analyse.mailer.smtplib.SMTP")
def test_send_email_alert_uses_smtp(mock_smtp):
    smtp_instance = mock_smtp.return_value.__enter__.return_value

    analyse.send_email_alert(
        subject="Subject",
        body="Body",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="password",
        email_from="from@example.com",
        email_to="to@example.com",
        use_tls=True,
    )

    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("user", "password")
    smtp_instance.send_message.assert_called_once()


@patch("analyse.monitor.send_email_alert")
@patch("analyse.monitor.search_tenders")
def test_monitor_sends_email_only_for_new_tenders(mock_search, mock_send_email, tmp_path):
    seen_file = tmp_path / "seen.json"
    csv_file = tmp_path / "results.csv"

    mock_search.return_value = [
        Tender("Old", "https://example.com/old"),
        Tender("New", "https://example.com/new"),
    ]
    analyse.save_seen_urls(["https://example.com/old"], seen_file)

    new_tenders = analyse.monitor("penetration", seen_file, csv_file=csv_file)

    assert new_tenders == [Tender("New", "https://example.com/new")]
    mock_send_email.assert_called_once()
    assert "New,https://example.com/new" in csv_file.read_text(encoding="utf-8")
    assert analyse.load_seen_urls(seen_file) == {
        "https://example.com/old",
        "https://example.com/new",
    }


@patch("analyse.tasks.subprocess.run")
def test_install_windows_task_creates_weekday_7am_task(mock_run, tmp_path):
    script = tmp_path / "analyse.py"
    script.write_text("# script", encoding="utf-8")

    analyse.install_windows_task(
        keyword="penetration",
        script_path=script,
        task_name="Test Task",
        python_executable="C:\\Python312\\python.exe",
    )

    args = mock_run.call_args.args[0]
    assert "schtasks" in args
    assert "/SC" in args
    assert "WEEKLY" in args
    assert "/D" in args
    assert "MON,TUE,WED,THU,FRI" in args
    assert "/ST" in args
    assert "07:00" in args
    assert "/TR" in args
    assert "penetration" in args[args.index("/TR") + 1]
    assert mock_run.call_args.kwargs["check"] is True


@patch("analyse.tasks.subprocess.run")
def test_install_windows_task_serializes_keyword_list(mock_run, tmp_path):
    script = tmp_path / "analyse.py"
    script.write_text("# script", encoding="utf-8")

    analyse.install_windows_task(
        keyword=["penetration", "it security"],
        script_path=script,
        task_name="Test Task",
        python_executable="C:\\Python312\\python.exe",
    )

    args = mock_run.call_args.args[0]
    tr_arg = args[args.index("/TR") + 1]
    assert "penetration, it security" in tr_arg
    assert mock_run.call_args.kwargs["check"] is True
