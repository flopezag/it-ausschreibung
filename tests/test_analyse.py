import sys
from pathlib import Path
import json
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import analyse
from analyse import Tender


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


def test_parse_keyword_arg_splits_comma_separated_values():
    parsed = analyse.parse_keyword_arg("penetration, it security, cloud")
    assert parsed == ["penetration", "it security", "cloud"]


def test_parse_keyword_arg_parses_json_dict():
    parsed = analyse.parse_keyword_arg('{"a":"penetration","b":"it security"}')
    assert parsed == {"a": "penetration", "b": "it security"}


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
