from __future__ import annotations

import argparse
import os

from analyse.browser_search import search_tenders
from analyse.monitor import monitor
from analyse.parser import parse_keyword_arg
from analyse.tasks import install_windows_task
from analyse.storage import save_results_csv
from analyse.terminal import COLOR_RESET, KEYWORD_COLOR, THEME_COLOR


THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI": ("chatbot", "llm", "KI", "generative", "predictive"),
    "Quantum": ("quantum", "quanten", "qml", "qnn", "pqc"),
    "Cybersecurity": ("penetration", "pet", "red", "blue"),
    "Robotics": ("roboter", "drohne", "inspektion", "atex"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search and monitor IT-Ausschreibung tenders.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument(
        "--keyword",
        help="Keyword(s) to search; by default, search all configured themes.",
    )
    search_parser.add_argument("--csv-file")
    search_parser.add_argument("--headed", action="store_true")

    monitor_parser = subparsers.add_parser("monitor")
    monitor_parser.add_argument(
        "--keyword",
        help="Keyword(s) to monitor; by default, search all configured themes.",
    )
    monitor_parser.add_argument("--seen-file", default=os.getenv("SEEN_FILE", "seen.json"))
    monitor_parser.add_argument("--csv-file")
    monitor_parser.add_argument("--headed", action="store_true")

    task_parser = subparsers.add_parser("install-task")
    task_parser.add_argument("--keyword", required=True)
    task_parser.add_argument("--script-path", default=__file__)
    task_parser.add_argument("--task-name", default="IT-Ausschreibung Monitor")
    task_parser.add_argument("--python-executable", default=None)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "search":
        kw = parse_keyword_arg(args.keyword) if args.keyword is not None else THEME_KEYWORDS

        tenders = {}
        
        if isinstance(kw, dict) and any(
            not isinstance(value, str) for value in kw.values()
        ):
            unique = {}
            for theme, keywords in kw.items():
                print(f"{THEME_COLOR}Monitoring theme: {theme}{COLOR_RESET}")
                for keyword in keywords:
                    print(
                        f"{KEYWORD_COLOR}Monitoring keyword: {keyword}{COLOR_RESET}"
                    )
                for tender in search_tenders(keywords, headless=not args.headed):
                    unique[tender.url] = tender
            tenders = list(unique.values())
        else:
            tenders = search_tenders(kw, headless=not args.headed)
        for tender in tenders:
            print(f"\n{tender.title} {tender.url}")
        if args.csv_file:
            save_results_csv(tenders, args.csv_file)

    elif args.command == "monitor":
        kw = parse_keyword_arg(args.keyword) if args.keyword is not None else THEME_KEYWORDS
        new_tenders = monitor(
            keyword=kw,
            seen_file=args.seen_file,
            csv_file=args.csv_file,
            headless=not args.headed,
        )
        if new_tenders:
            print(f"{len(new_tenders)} new tender(s) found.")
        else:
            print("No new tenders found.")

    elif args.command == "install-task":
        install_windows_task(
            keyword=parse_keyword_arg(args.keyword),
            script_path=args.script_path,
            task_name=args.task_name,
            python_executable=args.python_executable,
        )
        print("Windows scheduled task installed for Monday-Friday at 07:00.")


if __name__ == "__main__":
    main()
