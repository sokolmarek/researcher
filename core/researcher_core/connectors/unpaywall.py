"""Unpaywall connector: axis (d) accessibility.

Unpaywall (https://unpaywall.org) answers exactly one question, and this connector exists
to ask it: **given a DOI, is there a legal open-access copy, and where?** It is not a search
index and it has no citation graph, so :meth:`search`, :meth:`get_citations`, and
:meth:`get_references` are declared unsupported rather than faked.

Axis (d) verdict vocabulary
---------------------------

The three outcomes below map one-to-one onto the axis (d) vocabulary, and the mapping is the
whole point of this connector, so it is made explicit in :class:`Accessibility` rather than
left for a caller to infer from a nullable return value:

* ``full-text``     - Unpaywall knows the DOI and reports a ``best_oa_location``. A copy can
  be fetched, so passage-level checks (axis (c)) are possible.
* ``abstract-only`` - Unpaywall knows the DOI but reports no OA location. The work exists;
  only metadata and (elsewhere) an abstract are reachable. An ``insufficient-passage``
  result downstream is expected degradation here, not a defect.
* ``unavailable``   - Unpaywall does not know the DOI at all (HTTP 404). This is a CLEAN
  NEGATIVE: the query succeeded and there was genuinely no match.

Clean negative versus source error
----------------------------------

A 404 from the lookup endpoint is a clean negative and is returned as ``None`` /
``unavailable``. A timeout, a 429, or a 5xx is a :class:`~.base.SourceError`, never a
negative: Unpaywall being down must never contribute evidence that a real DOI is fabricated.
The base class already draws that line (404 and 410 parse to ``None``; 429 and 5xx retry and
then raise), so this module simply does not blur it.

Configuration
-------------

The API requires an ``email`` query parameter. It comes from ``UNPAYWALL_EMAIL``, falling
back to :data:`DEFAULT_EMAIL`. There is no API key, and none is ever required.

The email is deliberately kept OUT of the snapshot and cache key: it is a politeness
parameter that does not change the response, and keying on it would mean a contributor with
a different ``UNPAYWALL_EMAIL`` could not replay the recorded snapshots. So the request URL
is built with the email inline and the snapshot key is ``(unpaywall, "v2/<doi>", {})``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar
from urllib.parse import quote, urlencode

from ..model import (
    CSLDate,
    CSLName,
    CSLRecord,
    OALocation,
    is_valid_doi,
    normalize_author,
    normalize_doi,
)
from . import register
from .base import BaseConnector, UnsupportedOperation

__all__ = [
    "ABSTRACT_ONLY",
    "DEFAULT_EMAIL",
    "FULL_TEXT",
    "UNAVAILABLE",
    "Accessibility",
    "UnpaywallConnector",
]

#: Used when ``UNPAYWALL_EMAIL`` is unset. Unpaywall asks for a contact address, not a key:
#: it is rate-limit bookkeeping, so a documented default keeps the connector keyless.
DEFAULT_EMAIL = "mareksokol98@gmail.com"

#: Axis (d) verdicts. These strings are the vocabulary the verdict layer consumes.
FULL_TEXT = "full-text"
ABSTRACT_ONLY = "abstract-only"
UNAVAILABLE = "unavailable"

# Unpaywall "genre" (a Crossref work type) to a CSL-JSON type.
_GENRE_TO_CSL_TYPE: dict[str, str] = {
    "journal-article": "article-journal",
    "proceedings-article": "paper-conference",
    "book-chapter": "chapter",
    "book": "book",
    "monograph": "book",
    "reference-book": "book",
    "posted-content": "article",
    "dissertation": "thesis",
    "dataset": "dataset",
    "report": "report",
    "component": "article",
    "other": "article",
}


@dataclass(frozen=True)
class Accessibility:
    """The axis (d) answer for one DOI: what evidence depth is even possible.

    Distinguishes the three cases a nullable :class:`OALocation` alone cannot:

    * ``known=True,  location is not None`` -> :data:`FULL_TEXT`
    * ``known=True,  location is None``     -> :data:`ABSTRACT_ONLY`
    * ``known=False, location is None``     -> :data:`UNAVAILABLE` (clean negative)
    """

    doi: str
    verdict: str
    known: bool
    is_oa: bool = False
    oa_status: str = ""
    location: OALocation | None = None
    record: CSLRecord | None = None

    @property
    def is_full_text(self) -> bool:
        return self.verdict == FULL_TEXT

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "verdict": self.verdict,
            "known": self.known,
            "is_oa": self.is_oa,
            "oa_status": self.oa_status,
            "location": self.location.to_json_dict() if self.location else None,
        }


@register
class UnpaywallConnector(BaseConnector):
    """Resolve the best open-access location for a DOI.

    Supported: :meth:`resolve_doi`, :meth:`get_by_id` (a DOI is Unpaywall's only identifier),
    :meth:`get_oa_pdf`, and the richer :meth:`get_accessibility`.

    Unsupported, honestly: :meth:`search` (Unpaywall has no free-text work search endpoint),
    :meth:`get_citations` and :meth:`get_references` (it holds no citation graph).
    """

    name: ClassVar[str] = "unpaywall"
    base_url: ClassVar[str] = "https://api.unpaywall.org"
    capabilities: ClassVar[frozenset[str]] = frozenset({"get_by_id", "resolve_doi", "get_oa_pdf"})
    #: Unpaywall permits 100k calls/day. 10 requests/second is well inside that and polite.
    rate_limit_interval: ClassVar[float] = 0.1

    def __init__(self, *, email: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.email = (email or os.environ.get("UNPAYWALL_EMAIL") or DEFAULT_EMAIL).strip()

    # -- requests ----------------------------------------------------------

    def _endpoint(self, doi: str) -> str:
        """The snapshot and cache key for a DOI lookup. Email-free, so replay is portable."""
        return f"v2/{doi}"

    def _request_url(self, doi: str) -> str:
        """The live URL, with the politeness email inline (and out of the snapshot key)."""
        path = quote(doi, safe="/")
        query = urlencode({"email": self.email})
        return f"{self.base_url}/v2/{path}?{query}"

    async def _fetch(self, doi: str) -> Mapping[str, Any] | None:
        """One DOI lookup. ``None`` is a clean negative (HTTP 404: DOI unknown to Unpaywall).

        Raises :class:`~.base.SourceError` on timeout, rate limit, 5xx, or an unparseable body.
        """
        normalized = normalize_doi(doi)
        if not is_valid_doi(normalized):
            # Nothing shaped like a DOI can be in Unpaywall, so this is a clean negative and
            # not worth a network call. It is emphatically not a source error: no source failed.
            return None
        body = await self.request_json(
            self._endpoint(normalized),
            None,
            url=self._request_url(normalized),
        )
        if not isinstance(body, Mapping):
            return None
        # Unpaywall answers a malformed request with a JSON error envelope rather than a 4xx.
        # That is still a clean negative: the service worked, the DOI is not resolvable.
        if body.get("error"):
            return None
        return body

    # -- the contract ------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        """Unsupported. Unpaywall indexes OA status by DOI; it is not a literature search API."""
        raise UnsupportedOperation(self.name, "search")

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        """Unpaywall's only identifier is a DOI, so this is :meth:`resolve_doi`."""
        return await self.resolve_doi(identifier)

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        """The Unpaywall record for a DOI, or ``None`` when the DOI is unknown to Unpaywall.

        ``None`` is a clean negative. Note that Unpaywall's coverage is Crossref-derived, so a
        clean negative here means "not in Crossref", not "does not exist": DataCite DOIs are
        legitimately absent. Callers must weigh it as one source among several.
        """
        body = await self._fetch(doi)
        if body is None:
            return None
        return self.to_record(body)

    async def get_oa_pdf(self, doi: str) -> OALocation | None:
        """The best OA location for a DOI, or ``None`` when there is no OA copy.

        ``None`` covers two distinct states on purpose, because the base contract's return
        type does: the DOI is known but closed (``abstract-only``), and the DOI is unknown
        (``unavailable``). Call :meth:`get_accessibility` when the difference matters, which
        for the axis (d) verdict it does.
        """
        return (await self.get_accessibility(doi)).location

    # -- axis (d) ----------------------------------------------------------

    async def get_accessibility(self, doi: str) -> Accessibility:
        """The full axis (d) answer: ``full-text``, ``abstract-only``, or ``unavailable``.

        Never returns ``None`` and never conflates the three states. A source outage still
        raises :class:`~.base.SourceError`: no verdict at all is the honest answer when the
        source did not answer.
        """
        normalized = normalize_doi(doi)
        body = await self._fetch(normalized)
        if body is None:
            return Accessibility(doi=normalized, verdict=UNAVAILABLE, known=False)

        record = self.to_record(body)
        location = self.to_oa_location(body.get("best_oa_location"))
        return Accessibility(
            doi=record.DOI or normalized,
            verdict=FULL_TEXT if location else ABSTRACT_ONLY,
            known=True,
            is_oa=bool(body.get("is_oa")),
            oa_status=str(body.get("oa_status") or ""),
            location=location,
            record=record,
        )

    # -- parsing -----------------------------------------------------------

    def to_oa_location(self, raw: Any) -> OALocation | None:
        """Build an :class:`OALocation` from an Unpaywall ``best_oa_location`` object.

        ``None`` in, ``None`` out: no OA location was reported. Unpaywall often knows an OA
        landing page without a direct PDF link (``url_for_pdf`` is null), which is still
        full text, so the landing URL is kept and ``content_type`` drops to ``html`` so the
        right extractor runs downstream.
        """
        if not isinstance(raw, Mapping):
            return None
        pdf_url = str(raw.get("url_for_pdf") or "")
        url = pdf_url or str(raw.get("url") or raw.get("url_for_landing_page") or "")
        if not url:
            return None
        return OALocation(
            url=url,
            content_type="pdf" if pdf_url else "html",
            source=self.name,
            version=str(raw.get("version") or ""),
            license=str(raw.get("license") or ""),
            host_type=str(raw.get("host_type") or ""),
            is_oa=True,
        )

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one Unpaywall payload into a :class:`CSLRecord`.

        Unpaywall carries thin bibliographic metadata (no volume, issue, pages, or abstract),
        which is fine: this connector is an accessibility source, not an identity source.
        """
        best = raw.get("best_oa_location")
        location = self.to_oa_location(best)

        extra: dict[str, Any] = {}
        oa_status = str(raw.get("oa_status") or "")
        if oa_status:
            extra["oa_status"] = oa_status
        if location is not None:
            extra["oa_host_type"] = location.host_type
            extra["oa_version"] = location.version
            if location.license:
                extra["oa_license"] = location.license
        if raw.get("has_repository_copy") is not None:
            extra["has_repository_copy"] = bool(raw.get("has_repository_copy"))
        if raw.get("journal_is_in_doaj") is not None:
            extra["journal_is_in_doaj"] = bool(raw.get("journal_is_in_doaj"))
        oa_locations = raw.get("oa_locations")
        if isinstance(oa_locations, list):
            extra["oa_location_count"] = len(oa_locations)

        doi = normalize_doi(raw.get("doi"))
        return CSLRecord(
            type=_GENRE_TO_CSL_TYPE.get(str(raw.get("genre") or ""), "article-journal"),
            title=str(raw.get("title") or ""),
            author=_authors(raw.get("z_authors")),
            issued=_issued(raw),
            container_title=str(raw.get("journal_name") or ""),
            publisher=str(raw.get("publisher") or ""),
            DOI=doi,
            URL=str(raw.get("doi_url") or ""),
            ISSN=_issns(raw.get("journal_issns")),
            source=self.name,
            source_id=doi,
            is_oa=bool(raw.get("is_oa")),
            oa_url=location.url if location else "",
            extra=extra,
        )


def _authors(raw: Any) -> list[CSLName]:
    """Unpaywall ``z_authors`` to CSL names.

    Two shapes are in the wild and both are handled, because the snapshot set contains the
    second and older records contain the first:

    * Crossref-shaped: ``{"family": "Piwowar", "given": "Heather"}``.
    * OpenAlex-shaped (what the API returns today): ``{"raw_author_name": "Heather Piwowar"}``,
      a single display string, which :func:`~researcher_core.model.parse_name` splits.

    Anything else with a ``name`` key is treated as an organization and kept as a literal.
    """
    if not isinstance(raw, list):
        return []
    names: list[CSLName] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        family = str(entry.get("family") or "")
        given = str(entry.get("given") or "")
        if family or given:
            name = CSLName(family=family, given=given, suffix=str(entry.get("suffix") or ""))
        else:
            display = str(entry.get("raw_author_name") or entry.get("name") or "")
            if not display:
                continue
            name = normalize_author(display)
        if not name.is_empty():
            names.append(name)
    return names


def _issued(raw: Mapping[str, Any]) -> CSLDate | None:
    """``published_date`` (``YYYY-MM-DD``) when present, else the bare ``year``."""
    published = raw.get("published_date")
    if published:
        parsed = CSLDate.parse(str(published))
        if parsed is not None and parsed.year is not None:
            return parsed
    year = raw.get("year")
    if year in (None, ""):
        return None
    try:
        return CSLDate(year=int(year))
    except (TypeError, ValueError):
        return None


def _issns(raw: Any) -> list[str]:
    """``journal_issns`` is a comma-separated string, not a list."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if str(v).strip()]
    return [part.strip() for part in str(raw).split(",") if part.strip()]
