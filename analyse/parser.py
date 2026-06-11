from __future__ import annotations

import json


def parse_keyword_arg(value: str) -> str | list[str] | dict[str, str]:
    """Parse the CLI `--keyword` argument.

    Parameters
    ----------
    value : str
        Raw keyword string passed on the command line.

    Returns
    -------
    str | list[str] | dict[str, str]
        Parsed keyword data structure: dict for JSON, list for comma-separated values, or raw string.
    """
    if not isinstance(value, str):
        return value

    s = value.strip()
    if not s:
        return s

    if s[0] == "{":
        try:
            data = json.loads(s)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass

    if "," in s:
        parts = [part.strip() for part in s.split(",") if part.strip()]
        return parts

    return value
