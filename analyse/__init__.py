from __future__ import annotations

from .browser_search import extract_tenders_from_page, search_tenders
from .cli import main, parse_args
from .mailer import send_email_alert
from .monitor import build_email_body, find_new_tenders, monitor
from .parser import parse_keyword_arg
from .storage import load_seen_urls, save_results_csv, save_seen_urls
from .tasks import install_windows_task
from .models import Tender

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
