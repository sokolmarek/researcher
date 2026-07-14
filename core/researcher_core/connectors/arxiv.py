"""arXiv connector (http://export.arxiv.org/api/query).

The one connector whose API speaks Atom XML rather than JSON, so it overrides
:meth:`BaseConnector.parse_response` and turns the feed into a plain JSON-serializable
dict before anything else sees it. That matters: the parsed body is exactly what the
snapshot layer stores and hashes, so it must be JSON-safe. Parsing uses the stdlib
``xml.etree``; no new runtime dependency.

What arXiv can and cannot answer, stated honestly (constraint 8):

* ``search``     - full arXiv corpus, ``search_query=``.
* ``get_by_id``  - ``id_list=``, old-style (``math/0309136``), new-style (``2005.13249``),
  with or without a version suffix (``v1``).
* ``get_oa_pdf`` - arXiv always exposes a free PDF, so a resolvable arXiv identifier is
  always an OA hit. This is what makes arXiv a reliable axis (d) source.
* ``resolve_doi`` - **only for arXiv-issued DOIs** (``10.48550/arXiv.<id>``), which encode
  the arXiv identifier and so can be resolved exactly. The arXiv API has NO DOI index
  (a search for a publisher DOI string returns zero results, verified against the live
  API), so for any other DOI this connector raises :class:`UnsupportedOperation` rather
  than returning ``None``. That distinction is load-bearing under D9: ``None`` is a clean
  negative and counts as evidence toward the refusal-grade ``unresolvable`` verdict, and
  arXiv not indexing publisher DOIs is emphatically not evidence that a paper does not
  exist. ``UnsupportedOperation`` tells the caller to skip arXiv for that DOI, recording
  no outcome at all.

Clean negative versus source error, as this connector draws the line:

* HTTP 200 with ``totalResults 0``     -> clean negative (``[]`` / ``None``).
* HTTP 400 with an Atom error entry on an ``id_list`` lookup ("incorrect id format")
  -> clean negative: the API answered, and that string is not an arXiv identifier.
* HTTP 429 / 5xx / timeout / network   -> :class:`SourceError` (handled in the base class).
* An error entry on a ``search_query`` we built ourselves -> :class:`SourceError`
  (``BAD_RESPONSE``): arXiv rejected our query, so we obtained no clean answer about the
  corpus and must never report that as "nothing matched".

arXiv rate-limits aggressively and asks for roughly one request every three seconds, so
:attr:`rate_limit_interval` is 3.0. Keyless: arXiv has no API key and no polite-pool
parameter; the only politeness lever is a descriptive User-Agent, and an optional contact
email (``ARXIV_MAILTO`` or ``RESEARCHER_CORE_MAILTO``) is folded into it when set.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any, ClassVar

import httpx

from ..model import (
    CSLDate,
    CSLRecord,
    OALocation,
    is_valid_doi,
    normalize_authors,
    normalize_doi,
)
from . import register
from .base import BaseConnector, SourceError, SourceErrorKind, UnsupportedOperation

__all__ = [
    "ARXIV_DOI_PREFIX",
    "ArxivConnector",
    "parse_arxiv_id",
    "split_arxiv_version",
]

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"

#: arXiv's own DOI prefix. These DOIs embed the arXiv identifier, so they resolve exactly.
ARXIV_DOI_PREFIX = "10.48550/arxiv."

# New style: 2005.13249, 2005.13249v3 (4-digit YYMM, 4 or 5 digit sequence).
_NEW_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$")
# Old style: math/0309136, hep-th/9901001, math.RT/0309136, cond-mat.stat-mech/0703470v2.
# The archive may carry a subject class, which is itself hyphenated and of any length.
_OLD_ID_RE = re.compile(r"^[a-z][a-z-]*(?:\.[a-zA-Z][a-zA-Z-]*)?/\d{7}(?:v\d+)?$")
_VERSION_RE = re.compile(r"^(?P<base>.+?)(?P<version>v\d+)$")

# Resolver prefixes stripped case-insensitively, WITHOUT lowercasing the remainder: an
# old-style arXiv id can carry an uppercase subject class (math.RT/0309136).
_RESOLVER_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi.org/",
    "dx.doi.org/",
    "doi:",
)
_ARXIV_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf)/(?P<id>.+?)(?:\.pdf)?$",
    re.IGNORECASE,
)

# The arXiv search grammar's field prefixes. A query that already uses one is passed
# through verbatim; a bare phrase is wrapped in all:"..." so it means what a user expects.
_FIELD_PREFIX_RE = re.compile(r"\b(?:all|ti|au|abs|co|jr|cat|rn|id):", re.IGNORECASE)


def split_arxiv_version(identifier: str) -> tuple[str, str]:
    """Split ``"2005.13249v3"`` into ``("2005.13249", "v3")``. No suffix gives ``("...", "")``."""
    match = _VERSION_RE.match(identifier.strip())
    if not match:
        return identifier.strip(), ""
    return match.group("base"), match.group("version")


def parse_arxiv_id(value: str | None) -> str:
    """Coerce anything that names an arXiv paper into a bare arXiv identifier.

    Accepts a raw id (``2005.13249``, ``math/0309136``, either with a ``v2`` suffix), an
    ``arXiv:``-prefixed id, an arxiv.org abs/pdf URL, and an arXiv-issued DOI
    (``10.48550/arXiv.2005.13249``, with or without a resolver prefix). Returns ``""`` when
    the input names no arXiv paper, which is how the callers detect "not ours".
    """
    if not value:
        return ""
    text = str(value).strip().strip("<>\"'").strip()
    if not text:
        return ""

    lowered = text.lower()
    for prefix in _RESOLVER_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip()
            lowered = text.lower()
            break

    if lowered.startswith(ARXIV_DOI_PREFIX):
        text = text[len(ARXIV_DOI_PREFIX) :].strip()
        lowered = text.lower()

    url_match = _ARXIV_URL_RE.match(text)
    if url_match:
        text = url_match.group("id").strip()
        lowered = text.lower()

    if lowered.startswith("arxiv:"):
        text = text[len("arxiv:") :].strip()
        lowered = text.lower()

    if _NEW_ID_RE.match(text) or _OLD_ID_RE.match(text):
        return text
    return ""


@register
class ArxivConnector(BaseConnector):
    """arXiv's Atom API: preprint search, id lookup, and a guaranteed OA PDF."""

    name: ClassVar[str] = "arxiv"
    base_url: ClassVar[str] = "http://export.arxiv.org/api"
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {"search", "get_by_id", "resolve_doi", "get_oa_pdf"}
    )
    #: arXiv asks callers to leave roughly three seconds between requests.
    rate_limit_interval: ClassVar[float] = 3.0

    ENDPOINT: ClassVar[str] = "query"
    #: Hard ceiling arXiv documents for a single page.
    MAX_RESULTS: ClassVar[int] = 100

    # -- transport ---------------------------------------------------------

    def default_headers(self) -> dict[str, str]:
        """Atom, not JSON. An optional contact email rides along in the User-Agent."""
        agent = self.user_agent
        email = _contact_email()
        if email and "mailto:" not in agent:
            agent = f"{agent} (mailto:{email})"
        headers = {"User-Agent": agent, "Accept": "application/atom+xml"}
        headers.update(self.extra_headers)
        return headers

    def parse_response(self, response: httpx.Response, endpoint: str) -> Any:
        """Turn the Atom feed into a JSON-serializable dict (this is what gets snapshotted)."""
        if response.status_code in (404, 410):
            return None
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise SourceError(
                self.name,
                f"{response.request.url} returned a body that is not valid XML: {exc}",
                kind=SourceErrorKind.BAD_RESPONSE,
                status_code=response.status_code,
                endpoint=endpoint,
            ) from exc

        body = _feed_to_dict(root)
        if response.status_code >= 400 and not body.get("error"):
            # A 4xx we cannot explain from the payload. No clean answer was obtained.
            raise SourceError(
                self.name,
                f"{response.request.url} returned HTTP {response.status_code}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                status_code=response.status_code,
                endpoint=endpoint,
            )
        return body

    # -- operations --------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        """Free-text search over the arXiv corpus. An empty list is a clean negative.

        arXiv wraps a bare phrase in ``all:"..."``, so its own quoting is the thing a stray
        character breaks: a trailing backslash escapes arXiv's closing quote and the whole
        expression becomes unterminated. :meth:`~BaseConnector.sanitize_query` removes it
        before ``_build_search_query`` ever sees it.
        """
        text = self.sanitize_query(query)
        if not text:
            return []
        capped = max(1, min(int(limit), self.MAX_RESULTS))
        body = await self.request_json(
            self.ENDPOINT,
            {
                "search_query": _build_search_query(text, since),
                "start": 0,
                "max_results": capped,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )
        if not body:
            return []
        self._raise_on_error(body, "search")
        entries = body.get("entries") or []
        return [self.to_record(entry) for entry in entries[:capped]]

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        """Look one arXiv identifier up via ``id_list``. ``None`` is a clean negative.

        Accepts a bare id, an ``arXiv:`` prefix, an arxiv.org URL, or an arXiv-issued DOI.
        A DOI that is NOT arXiv's raises :class:`UnsupportedOperation`: arXiv has no DOI
        index, so it must not manufacture a clean negative for a paper it simply cannot
        look up (D9).
        """
        raw = (identifier or "").strip()
        if not raw:
            return None
        if is_valid_doi(raw) and not normalize_doi(raw).startswith(ARXIV_DOI_PREFIX):
            raise UnsupportedOperation(self.name, "get_by_id(non-arXiv DOI)")

        lookup = parse_arxiv_id(raw) or _strip_to_id_candidate(raw)
        body = await self.request_json(self.ENDPOINT, {"id_list": lookup})
        if not body:
            return None
        if body.get("error"):
            # "incorrect id format for <x>": arXiv answered, and that string names no
            # arXiv paper. A clean negative, not an outage.
            return None
        entries = body.get("entries") or []
        if not entries:
            return None
        return self.to_record(entries[0])

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        """Resolve an arXiv-issued DOI (``10.48550/arXiv.<id>``). ``None`` is a clean negative.

        Raises :class:`UnsupportedOperation` for any other DOI. See the module docstring:
        the arXiv API has no DOI index, and a fake clean negative here would be evidence
        toward a refusal-grade "likely fabricated" verdict.
        """
        arxiv_id = parse_arxiv_id(doi)
        if not arxiv_id:
            raise UnsupportedOperation(self.name, "resolve_doi(non-arXiv DOI)")
        return await self.get_by_id(arxiv_id)

    async def get_oa_pdf(self, doi: str) -> OALocation | None:
        """The free arXiv PDF for an arXiv identifier or arXiv-issued DOI.

        Every arXiv paper has a free PDF, so a resolvable identifier is always an OA hit.
        ``None`` means the identifier resolved to nothing. Any non-arXiv DOI raises
        :class:`UnsupportedOperation` (arXiv cannot map a publisher DOI to a preprint).
        """
        arxiv_id = parse_arxiv_id(doi)
        if not arxiv_id:
            raise UnsupportedOperation(self.name, "get_oa_pdf(non-arXiv DOI)")
        record = await self.get_by_id(arxiv_id)
        if record is None or not record.oa_url:
            return None
        return OALocation(
            url=record.oa_url,
            content_type="pdf",
            source=self.name,
            version="submittedVersion",
            host_type="repository",
            is_oa=True,
        )

    # -- parsing -----------------------------------------------------------

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one parsed Atom entry into a :class:`CSLRecord`."""
        versioned = _id_from_entry(raw)
        bare, version = split_arxiv_version(versioned)
        journal_ref = str(raw.get("journal_ref") or "")
        doi = str(raw.get("doi") or "")
        pdf_url = _pdf_url(raw, versioned)
        abs_url = _abs_url(raw, versioned)

        extra: dict[str, Any] = {}
        if versioned and versioned != bare:
            extra["arxiv_id_versioned"] = versioned
        if raw.get("primary_category"):
            extra["arxiv_primary_category"] = str(raw["primary_category"])
        if raw.get("comment"):
            extra["arxiv_comment"] = str(raw["comment"])
        if journal_ref:
            extra["arxiv_journal_ref"] = journal_ref

        return CSLRecord(
            # A preprint is "article"; once arXiv reports a DOI or a journal-ref, the work
            # has been published, so it becomes "article-journal". Real entries carry either
            # one without the other (2304.06427 has a DOI and no journal-ref).
            type="article-journal" if (journal_ref or doi) else "article",
            title=str(raw.get("title") or ""),
            # arXiv gives free-form "Given Family" strings; the model's own name parser
            # splits them (it knows about particles and suffixes). Never split by hand.
            author=normalize_authors(raw.get("authors") or []),
            issued=CSLDate.parse(str(raw.get("published") or "")),
            container_title=journal_ref,
            version=version,
            abstract=str(raw.get("summary") or ""),
            DOI=doi,
            URL=abs_url,
            keyword=[str(c) for c in raw.get("categories") or []],
            source=self.name,
            source_id=versioned,
            arxiv_id=bare,
            is_oa=True if pdf_url else None,
            oa_url=pdf_url,
            extra=extra,
        )

    # -- internals ---------------------------------------------------------

    def _raise_on_error(self, body: Mapping[str, Any], operation: str) -> None:
        """An error feed on a query WE built is a source error, never a clean negative."""
        error = body.get("error")
        if not error:
            return
        raise SourceError(
            self.name,
            f"arXiv rejected the {operation} request: {error.get('summary') or error}",
            kind=SourceErrorKind.BAD_RESPONSE,
            status_code=400,
            endpoint=self.ENDPOINT,
        )


# ---------------------------------------------------------------------------
# Atom -> dict
# ---------------------------------------------------------------------------


def _feed_to_dict(root: ET.Element) -> dict[str, Any]:
    """The whole feed as plain JSON-serializable data. Snapshot-safe by construction."""
    body: dict[str, Any] = {
        "total_results": _int_text(root.find(f"{_OPENSEARCH}totalResults")),
        "start_index": _int_text(root.find(f"{_OPENSEARCH}startIndex")),
        "items_per_page": _int_text(root.find(f"{_OPENSEARCH}itemsPerPage")),
        "entries": [],
    }
    entries: list[dict[str, Any]] = []
    for element in root.findall(f"{_ATOM}entry"):
        entry = _entry_to_dict(element)
        if _is_error_entry(entry):
            body["error"] = {"id": entry.get("id", ""), "summary": entry.get("summary", "")}
            continue
        entries.append(entry)
    body["entries"] = entries
    return body


def _entry_to_dict(element: ET.Element) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": _text(element.find(f"{_ATOM}id")),
        "title": _text(element.find(f"{_ATOM}title")),
        "summary": _text(element.find(f"{_ATOM}summary")),
        "published": _text(element.find(f"{_ATOM}published")),
        "updated": _text(element.find(f"{_ATOM}updated")),
        "authors": [
            _text(name)
            for author in element.findall(f"{_ATOM}author")
            for name in [author.find(f"{_ATOM}name")]
            if _text(name)
        ],
        "categories": [
            (category.get("term") or "").strip()
            for category in element.findall(f"{_ATOM}category")
            if (category.get("term") or "").strip()
        ],
        "links": [
            {
                "href": (link.get("href") or "").strip(),
                "rel": (link.get("rel") or "").strip(),
                "type": (link.get("type") or "").strip(),
                "title": (link.get("title") or "").strip(),
            }
            for link in element.findall(f"{_ATOM}link")
        ],
    }
    primary = element.find(f"{_ARXIV}primary_category")
    if primary is not None:
        entry["primary_category"] = (primary.get("term") or "").strip()
    for key, tag in (
        ("doi", f"{_ARXIV}doi"),
        ("journal_ref", f"{_ARXIV}journal_ref"),
        ("comment", f"{_ARXIV}comment"),
    ):
        value = _text(element.find(tag))
        if value:
            entry[key] = value
    return entry


def _is_error_entry(entry: Mapping[str, Any]) -> bool:
    """arXiv reports a rejected request as one entry pointing at ``/api/errors#...``."""
    return "/api/errors" in str(entry.get("id") or "")


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return " ".join(element.text.split())


def _int_text(element: ET.Element | None) -> int:
    try:
        return int(_text(element))
    except ValueError:
        return 0


def _id_from_entry(entry: Mapping[str, Any]) -> str:
    """``http://arxiv.org/abs/2005.13249v3`` -> ``2005.13249v3``."""
    raw = str(entry.get("id") or "")
    match = _ARXIV_URL_RE.match(raw)
    if match:
        return match.group("id").strip()
    return raw.rsplit("/abs/", 1)[-1].strip() if "/abs/" in raw else ""


def _link(entry: Mapping[str, Any], *, title: str = "", rel: str = "") -> str:
    for link in entry.get("links") or []:
        if title and str(link.get("title") or "") == title:
            return str(link.get("href") or "")
        if rel and not title and str(link.get("rel") or "") == rel:
            return str(link.get("href") or "")
    return ""


def _pdf_url(entry: Mapping[str, Any], versioned: str) -> str:
    url = _link(entry, title="pdf")
    if url:
        return url
    return f"https://arxiv.org/pdf/{versioned}" if versioned else ""


def _abs_url(entry: Mapping[str, Any], versioned: str) -> str:
    url = _link(entry, rel="alternate")
    if url:
        return url
    return f"https://arxiv.org/abs/{versioned}" if versioned else ""


def _build_search_query(query: str, since: int | None) -> str:
    """Build a ``search_query``. A bare phrase becomes ``all:"phrase"``; a fielded query passes."""
    text = query.strip()
    if not _FIELD_PREFIX_RE.search(text):
        text = 'all:"{}"'.format(text.replace('"', " ").strip())
    if since is not None:
        text = f"{text} AND submittedDate:[{int(since)}01010000 TO 99991231235959]"
    return text


def _strip_to_id_candidate(raw: str) -> str:
    """What to send as ``id_list`` when the input does not parse as an arXiv id.

    The API is the authority, not our regex: it answers "incorrect id format" (a clean
    negative) for a string that names no paper, and that beats guessing here.
    """
    text = raw.strip().strip("<>\"'").strip()
    if text.lower().startswith("arxiv:"):
        text = text[len("arxiv:") :].strip()
    return text


def _contact_email() -> str:
    """Optional contact email for the User-Agent. arXiv has no key and no polite-pool param."""
    for name in ("ARXIV_MAILTO", "RESEARCHER_CORE_MAILTO"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""
