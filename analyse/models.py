from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tender:
    """Data for a single IT-Ausschreibung tender.

    Attributes
    ----------
    title : str
        The title of the tender.
    url : str
        The absolute URL to the tender details.
    """

    title: str
    url: str
