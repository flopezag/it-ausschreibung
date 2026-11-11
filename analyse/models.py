from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tender:
    """Data for a single IT-Ausschreibung tender.

    @spec REQ-10

    Attributes
    ----------
    title : str
        The title of the tender.
    url : str
        The absolute URL to the tender details.
    published : str
        Publication date shown in the search result.
    deadline : str
        Submission deadline shown in the search result.
    publication_type : str
        Public or commercial tender type shown in the search result.
    publisher : str
        Public Auftraggeber address shown on the tender detail page.
    """

    title: str
    url: str
    published: str = ""
    deadline: str = ""
    publication_type: str = ""
    publisher: str = ""
