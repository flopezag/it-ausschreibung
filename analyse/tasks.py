from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable


def install_windows_task(
    keyword: str | Iterable[str] | dict[str, str],
    script_path: str | Path,
    task_name: str = "IT-Ausschreibung Monitor",
    python_executable: str | Path | None = None,
) -> None:
    """Create/update a Windows Task Scheduler job.

    Parameters
    ----------
    keyword : str | Iterable[str] | dict[str, str]
        Search keyword(s) to embed in the scheduled command.
    script_path : str | Path
        Path to the Python script to run.
    task_name : str, optional
        Scheduled task name, by default "IT-Ausschreibung Monitor".
    python_executable : str | Path | None, optional
        Python executable to use, by default "python".
    """
    python_executable = str(python_executable or "python")
    script_path = str(Path(script_path).resolve())

    if isinstance(keyword, dict):
        kw_str = json.dumps(keyword)
    elif isinstance(keyword, str):
        kw_str = keyword
    else:
        kw_str = ", ".join([str(v) for v in keyword])

    command = (
        f'"{python_executable}" "{script_path}" monitor '
        f'--keyword "{kw_str}" '
        f'--seen-file "%USERPROFILE%\\seen_it-ausschreibung.json" '
        f'--csv-file "%USERPROFILE%\\it-ausschreibung-results.csv"'
    )

    subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            task_name,
            "/SC",
            "WEEKLY",
            "/D",
            "MON,TUE,WED,THU,FRI",
            "/ST",
            "07:00",
            "/TR",
            command,
            "/F",
        ],
        check=True,
    )
