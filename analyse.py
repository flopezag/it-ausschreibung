"""
Minimal IT-Ausschreibung monitor.

Functionalities:
1. Search tenders by keyword using Playwright.
2. Save/search-compare results to detect new tenders.
3. Send email alerts for new tenders.
4. Install a Windows Task Scheduler job to run every working day at 07:00.

Usage examples:

    python analyse.py search --keyword penetration
    python analyse.py monitor --keyword penetration
    python analyse.py install-task --keyword penetration --script-path "C:\\path\\to\\analyse.py"

Required packages:

    pip install playwright
    python -m playwright install

For tests:

    pip install pytest
    pytest

Email configuration is read from environment variables:

    SMTP_HOST
    SMTP_PORT
    SMTP_USER
    SMTP_PASSWORD
    EMAIL_FROM
    EMAIL_TO

Optional:

    SMTP_USE_TLS=true
    SEEN_FILE=seen_it-ausschreibung.json
"""

from __future__ import annotations

from analyse.cli import main, parse_args
from analyse.browser_search import extract_tenders_from_page, search_tenders
from analyse.mailer import send_email_alert
from analyse.models import Tender
from analyse.monitor import build_email_body, find_new_tenders, monitor
from analyse.parser import parse_keyword_arg
from analyse.storage import load_seen_urls, save_results_csv, save_seen_urls
from analyse.tasks import install_windows_task

__all__ = [
    "Tender",
    "extract_tenders_from_page",
    "search_tenders",
    "save_results_csv",
    "load_seen_urls",
    "save_seen_urls",
    "find_new_tenders",
    "build_email_body",
    "send_email_alert",
    "monitor",
    "install_windows_task",
    "parse_keyword_arg",
    "main",
    "parse_args",
]

if __name__ == "__main__":
    main()
