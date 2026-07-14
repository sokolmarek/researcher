"""Crossref connector (https://api.crossref.org).

Crossref is the DOI registration agency for the scholarly literature, so it is the
authority on what a DOI *is*: it resolves a DOI to publisher-deposited metadata, and it
carries the update graph (retractions, corrections, errata, expressions of concern) that
axis (b) is built on. Together with OpenAlex it satisfies the D9 two-confirmation identity
gate for axis (a).

Operations
----------
``search``          ``/works?query.bibliographic=``
``get_by_id``       a DOI (Crossref has no other native identifier for a work)
``resolve_doi``     ``/works/<doi>``
``get_references``  the ``reference`` array deposited on the work

``get_citations`` is NOT offered. Crossref has no forward-citation endpoint (the
``is-referenced-by-count`` integer is a count, not a list), so the operation is declared
unsupported and :class:`~researcher_core.connectors.base.UnsupportedOperation` is raised
rather than faking an answer. Use OpenAlex or OpenCitations for forward edges.

The update graph (axis (b))
---------------------------
Crossref exposes two arrays, and they are NOT the same thing:

* ``update-to``  : updates THIS work makes to other works. A retraction notice carries
  ``update-to: [{DOI: <the retracted paper>, type: "retraction", ...}]``. Publishers also
  (inconsistently) deposit ``update-to`` on the retracted article itself.
* ``updated-by`` : updates OTHER works make to THIS one. This is the direction that says
  "this paper was retracted".

Both are surfaced verbatim (each entry keeping its ``type``, which is the whole point) on
``record.extra`` under :data:`UPDATE_TO_KEY` and :data:`UPDATED_BY_KEY`. ``status.py`` owns
the interpretation; this connector deliberately does NOT collapse them into
``is_retracted``, because a retraction notice carries ``type: "retraction"`` while being a
perfectly current document itself. Flattening here would mark the notice as retracted.

Politeness
----------
Keyless. Crossref has no API key. Setting ``CROSSREF_MAILTO`` moves requests into the
polite pool, which gets better and more predictable rate limits. The address is sent both
in the ``User-Agent`` (Crossref's documented mechanism) and as a ``mailto`` query
parameter, and it is injected at HTTP time only: it never enters the snapshot or cache key,
so a snapshot recorded on one machine replays on a machine with a different address, or
none at all.

Clean negative versus source error
----------------------------------
A 404 from ``/works/<doi>`` means Crossref genuinely has no such DOI: a clean negative,
returned as ``None``. A 429 (Crossref does rate-limit), a 5xx, a timeout, or a body that is
not the expected envelope is a :class:`~researcher_core.connectors.base.SourceError`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, ClassVar
from urllib.parse import quote

from ..model import CSLDate, CSLName, CSLRecord, normalize_doi
from . import register
from .base import BaseConnector, SourceError, SourceErrorKind

__all__ = [
    "MAILTO_ENV_VAR",
    "UPDATED_BY_KEY",
    "UPDATE_TO_KEY",
    "CrossrefConnector",
]

#: Environment variable holding the polite-pool contact address. Optional; never required.
MAILTO_ENV_VAR = "CROSSREF_MAILTO"

#: Stable ``record.extra`` key for the Crossref ``update-to`` array (updates this work makes
#: to other works). ``status.py`` reads this; do not rename it.
UPDATE_TO_KEY = "crossref_update_to"

#: Stable ``record.extra`` key for the Crossref ``updated-by`` array (updates other works
#: make to this one: the direction that says "this paper was retracted").
UPDATED_BY_KEY = "crossref_updated_by"

#: Crossref work type -> CSL-JSON type. Anything unlisted falls back to article-journal.
_TYPE_MAP: dict[str, str] = {
    "book": "book",
    "book-chapter": "chapter",
    "book-part": "chapter",
    "book-section": "chapter",
    "component": "article",
    "dataset": "dataset",
    "dissertation": "thesis",
    "edited-book": "book",
    "journal-article": "article-journal",
    "journal-issue": "article-journal",
    "monograph": "book",
    "peer-review": "review",
    "posted-content": "article",
    "proceedings-article": "paper-conference",
    "reference-book": "book",
    "reference-entry": "entry",
    "report": "report",
    "standard": "standard",
}

_JATS_TAG_RE = re.compile(r"<[^>]+>")


@register
class CrossrefConnector(BaseConnector):
    """Crossref REST API. Keyless, polite pool via ``CROSSREF_MAILTO``."""

    name: ClassVar[str] = "crossref"
    base_url: ClassVar[str] = "https://api.crossref.org"
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {"search", "get_by_id", "resolve_doi", "get_references"}
    )
    # Crossref asks for a courteous request rate rather than publishing a hard cap. One
    # request per 100 ms is well inside the polite pool's headroom.
    rate_limit_interval: ClassVar[float] = 0.1
    #: Crossref caps `rows` at 1000; we never ask for more than one page.
    max_rows: ClassVar[int] = 100

    def __init__(self, *, mailto: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.mailto = (mailto if mailto is not None else os.environ.get(MAILTO_ENV_VAR, "")).strip()

    # -- politeness --------------------------------------------------------

    def default_headers(self) -> dict[str, str]:
        """Add the polite-pool address to the User-Agent, per Crossref's documentation."""
        headers = super().default_headers()
        if self.mailto:
            headers["User-Agent"] = f"{headers['User-Agent']} (mailto:{self.mailto})"
        return headers

    async def _http_json(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
    ) -> Any:
        """Inject ``mailto`` at HTTP time only, so it stays out of the snapshot key.

        The snapshot and cache keys are built from the params handed to ``request_json``.
        If the contact address were one of them, a snapshot recorded with an address set
        would be unreachable to anyone whose ``CROSSREF_MAILTO`` differs or is unset. So
        the polite-pool parameter is added here, below the snapshot layer.
        """
        request_params = dict(params)
        if self.mailto:
            request_params["mailto"] = self.mailto
        return await super()._http_json(
            endpoint, request_params, method=method, headers=headers, url=url
        )

    # -- operations --------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        """Bibliographic free-text search. An empty list is a clean negative.

        ``query.bibliographic`` is plain relevance text, not an expression, so Crossref is
        the most forgiving source here and survives a truncated title unaided. It is still
        normalized, for one reason: the query must be the SAME string every source is
        asked, or the same reference would carry a different fingerprint per source. No
        escaping is applied; a backslash sent to Crossref is a character to match on.
        """
        text = self.sanitize_query(query)
        if not text:
            return []
        params: dict[str, Any] = {
            "query.bibliographic": text,
            "rows": max(1, min(int(limit), self.max_rows)),
        }
        if since is not None:
            params["filter"] = f"from-pub-date:{int(since)}-01-01"
        body = await self.request_json("works", params)
        if body is None:
            return []
        message = self._message(body, "works")
        items = message.get("items")
        if items is None:
            return []
        if not isinstance(items, list):
            raise SourceError(
                self.name,
                "Crossref /works returned a non-list `items` field.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint="works",
            )
        return [self.to_record(item) for item in items if isinstance(item, Mapping)]

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        """Crossref's only native work identifier is the DOI, so this is ``resolve_doi``."""
        return await self.resolve_doi(identifier)

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        """Fetch one work by DOI. ``None`` (including on a 404) is a clean negative."""
        body, endpoint = await self._fetch_work(doi)
        if body is None:
            return None
        return self.to_record(self._message(body, endpoint))

    async def get_references(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """The ``reference`` array Crossref carries for this work (backward edges).

        An empty list is a clean negative: either Crossref has no such DOI, or the
        publisher deposited no reference list (which is common, and is not an error).
        """
        body, endpoint = await self._fetch_work(identifier)
        if body is None:
            return []
        message = self._message(body, endpoint)
        references = message.get("reference")
        if not isinstance(references, list):
            return []
        out: list[CSLRecord] = []
        for entry in references[: max(0, int(limit))]:
            if isinstance(entry, Mapping):
                out.append(self.to_reference_record(entry))
        return out

    # -- transport helpers -------------------------------------------------

    async def _fetch_work(self, doi: str) -> tuple[Any, str]:
        """GET ``/works/<doi>``. Returns ``(body_or_None, endpoint)``.

        A blank DOI is a clean negative, not a config error: nothing was asked of Crossref.
        """
        normalized = normalize_doi(doi)
        if not normalized:
            return None, "works"
        endpoint = f"works/{quote(normalized, safe='/')}"
        return await self.request_json(endpoint), endpoint

    def _message(self, body: Any, endpoint: str) -> Mapping[str, Any]:
        """Unwrap the Crossref ``{status, message-type, message}`` envelope."""
        if not isinstance(body, Mapping):
            raise SourceError(
                self.name,
                f"Crossref /{endpoint} returned {type(body).__name__}, not a JSON object.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        message = body.get("message")
        if not isinstance(message, Mapping):
            raise SourceError(
                self.name,
                f"Crossref /{endpoint} response has no `message` object.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        return message

    # -- parsing -----------------------------------------------------------

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one Crossref work into a :class:`CSLRecord`.

        Every field is handed to :class:`CSLRecord` raw; the dataclass normalizes DOIs,
        titles, and names in ``__post_init__``. Nothing is normalized by hand here.
        """
        doi = str(raw.get("DOI") or "")
        extra: dict[str, Any] = {}

        crossref_type = str(raw.get("type") or "")
        if crossref_type:
            extra["crossref_type"] = crossref_type

        update_to = _update_entries(raw.get("update-to"))
        if update_to:
            extra[UPDATE_TO_KEY] = update_to
        updated_by = _update_entries(raw.get("updated-by"))
        if updated_by:
            extra[UPDATED_BY_KEY] = updated_by

        subtype = str(raw.get("subtype") or "")
        if subtype:
            extra["crossref_subtype"] = subtype

        return CSLRecord(
            type=_TYPE_MAP.get(crossref_type, "article-journal"),
            title=_first_string(raw.get("title")),
            author=_names(raw.get("author")),
            editor=_names(raw.get("editor")),
            issued=_issued(raw),
            container_title=_first_string(raw.get("container-title")),
            publisher=str(raw.get("publisher") or ""),
            volume=str(raw.get("volume") or ""),
            issue=str(raw.get("issue") or ""),
            page=str(raw.get("page") or raw.get("article-number") or ""),
            abstract=_strip_jats(raw.get("abstract")),
            DOI=doi,
            URL=str(raw.get("URL") or ""),
            ISSN=[str(v) for v in raw.get("ISSN") or [] if v],
            ISBN=_first_string(raw.get("ISBN")),
            language=str(raw.get("language") or ""),
            keyword=[str(v) for v in raw.get("subject") or [] if v],
            source=self.name,
            source_id=normalize_doi(doi),
            citation_count=_as_int(raw.get("is-referenced-by-count")),
            reference_count=_as_int(raw.get("reference-count")),
            # is_retracted is deliberately NOT derived here: `update-to` on a retraction
            # notice describes the paper it retracts, not the notice. status.py (axis (b))
            # reads the two arrays above and decides.
            extra=extra,
        )

    def to_reference_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one entry of a Crossref ``reference`` array.

        Deposited references are sparse and irregular: many carry only an unstructured
        string, and the ``author`` field, when present, is a bare surname. Whatever is
        there is preserved; nothing is invented to fill a gap.
        """
        unstructured = str(raw.get("unstructured") or "").strip()
        extra: dict[str, Any] = {}
        if unstructured:
            extra["unstructured"] = unstructured
        key = str(raw.get("key") or "")
        if key:
            extra["crossref_reference_key"] = key
        asserted_by = str(raw.get("doi-asserted-by") or "")
        if asserted_by:
            extra["doi_asserted_by"] = asserted_by

        title = (
            str(raw.get("article-title") or "")
            or str(raw.get("volume-title") or "")
            or str(raw.get("series-title") or "")
        )
        author_field = str(raw.get("author") or "").strip()
        return CSLRecord(
            title=title,
            author=[CSLName.parse(author_field)] if author_field else [],
            issued=CSLDate.parse(str(raw.get("year"))) if raw.get("year") else None,
            container_title=str(raw.get("journal-title") or ""),
            volume=str(raw.get("volume") or ""),
            issue=str(raw.get("issue") or ""),
            page=str(raw.get("first-page") or ""),
            DOI=str(raw.get("DOI") or ""),
            ISSN=[str(raw["ISSN"])] if raw.get("ISSN") else [],
            ISBN=str(raw.get("ISBN") or ""),
            source=self.name,
            source_id=normalize_doi(str(raw.get("DOI") or "")) or key,
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def _update_entries(value: Any) -> list[dict[str, Any]]:
    """Normalize an ``update-to`` / ``updated-by`` array, preserving every entry's type.

    Shape kept stable for ``status.py``::

        {"DOI": "10.1016/s0140-6736(20)31180-6",
         "type": "retraction",          # verbatim; also "correction", "expression_of_concern"
         "label": "Retraction",
         "source": "publisher",         # or "retraction-watch"
         "updated": "2020-06-05T00:00:00Z",
         "date_parts": [2020, 6, 5]}
    """
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        updated = entry.get("updated")
        updated_at = ""
        date_parts: list[int] = []
        if isinstance(updated, Mapping):
            updated_at = str(updated.get("date-time") or "")
            raw_parts = updated.get("date-parts")
            if isinstance(raw_parts, list) and raw_parts and isinstance(raw_parts[0], list):
                date_parts = [int(p) for p in raw_parts[0] if isinstance(p, int)]
        elif updated is not None:
            updated_at = str(updated)
        out.append(
            {
                "DOI": normalize_doi(entry.get("DOI")),
                "type": str(entry.get("type") or ""),
                "label": str(entry.get("label") or ""),
                "source": str(entry.get("source") or ""),
                "updated": updated_at,
                "date_parts": date_parts,
            }
        )
    return out


def _first_string(value: Any) -> str:
    """Crossref emits title, container-title, and ISBN as arrays. Take the first entry."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            if item:
                return str(item)
        return ""
    return str(value)


def _names(value: Any) -> list[CSLName]:
    """Crossref contributor entries: ``{given, family}`` for people, ``{name}`` for orgs."""
    if not isinstance(value, list):
        return []
    out: list[CSLName] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        family = str(entry.get("family") or "")
        given = str(entry.get("given") or "")
        literal = str(entry.get("name") or "")
        suffix = str(entry.get("suffix") or "")
        if family or given or literal:
            out.append(CSLName(family=family, given=given, suffix=suffix, literal=literal))
    return out


def _issued(raw: Mapping[str, Any]) -> CSLDate | None:
    """The publication date, preferring ``issued`` and falling back through the variants.

    ``created`` is deliberately last: it is the DOI deposit date, not the publication date.
    """
    for key in ("issued", "published", "published-print", "published-online", "created"):
        candidate = CSLDate.from_csl_json(raw.get(key))
        if candidate is not None and candidate.year is not None:
            return candidate
    return None


def _strip_jats(value: Any) -> str:
    """Crossref abstracts are JATS XML fragments. Drop the tags, keep the prose."""
    if not value:
        return ""
    text = _JATS_TAG_RE.sub(" ", str(value))
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
