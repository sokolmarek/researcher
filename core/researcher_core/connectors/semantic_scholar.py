"""Semantic Scholar Graph API connector.

Covers all six operations: search, get_by_id, resolve_doi, get_citations, get_references,
and get_oa_pdf. The Graph API is the kernel's broadest citation-graph source, and the only
one that hands back forward AND backward edges from the same identifier.

Two properties of this API drive the whole implementation:

1. **You must ask for fields, or you get almost nothing.** Every endpoint defaults to
   ``paperId`` plus ``title``. So every request here passes an explicit ``fields`` list, and
   that list is part of the snapshot key.

2. **Keyless traffic is aggressively rate limited.** The shared unauthenticated pool returns
   HTTP 429 constantly, and the ``/paper/search`` endpoint is the worst of it. An optional
   ``S2_API_KEY`` (sent as the ``x-api-key`` header) ADDS quota; it is never required, and a
   missing key is not a configuration error.

   A 429 is a :class:`SourceError` with kind ``rate_limit``, never a clean negative. This is
   the single most important line in this module: if an S2 outage were reported as "no match",
   then under D9 axis (a) an all-negative aggregation would call a perfectly real citation
   ``unresolvable``, which is the one refusal-grade verdict. A rate-limited index must never
   accuse a researcher of fabricating a reference. Retries and backoff are inherited from
   :class:`BaseConnector`; when they are exhausted the SourceError propagates.

A 404 from a lookup endpoint is the opposite case, and IS a clean negative: S2 answered, and
it genuinely has no paper under that identifier. :meth:`BaseConnector.parse_response` maps
404 and 410 to ``None`` for exactly this reason.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, ClassVar

from ..model import (
    CSLDate,
    CSLRecord,
    OALocation,
    is_valid_doi,
    normalize_authors,
    normalize_doi,
)
from . import register
from .base import BaseConnector, SourceError, SourceErrorKind

__all__ = ["SemanticScholarConnector"]

#: Fields requested for a full record. Anything not listed here comes back absent, so this
#: list is effectively the record schema.
PAPER_FIELDS: tuple[str, ...] = (
    "paperId",
    "externalIds",
    "url",
    "title",
    "abstract",
    "venue",
    "publicationVenue",
    "year",
    "publicationDate",
    "journal",
    "authors",
    "citationCount",
    "referenceCount",
    "isOpenAccess",
    "openAccessPdf",
    "publicationTypes",
)

#: Search results carry the same shape, minus the abstract (which bloats a 25-hit page).
SEARCH_FIELDS: tuple[str, ...] = tuple(f for f in PAPER_FIELDS if f != "abstract")

#: Citation and reference edges: enough to identify and rank the neighbor, no abstract.
EDGE_FIELDS: tuple[str, ...] = SEARCH_FIELDS

#: The narrow projection used by get_oa_pdf.
OA_FIELDS: tuple[str, ...] = ("paperId", "externalIds", "isOpenAccess", "openAccessPdf")

#: S2 search caps at 100 per page; citations and references cap at 1000.
MAX_SEARCH_LIMIT = 100
MAX_EDGE_LIMIT = 1000

_HEX_ID_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_ARXIV_RE = re.compile(r"^(\d{4}\.\d{4,5}(v\d+)?|[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?)$", re.I)
_KNOWN_PREFIXES = (
    "doi:",
    "arxiv:",
    "corpusid:",
    "mag:",
    "acl:",
    "pmid:",
    "pmcid:",
    "url:",
    "dblp:",
)

#: S2 publicationTypes -> CSL type. Anything unlisted falls back to "article-journal".
_TYPE_MAP: dict[str, str] = {
    "JournalArticle": "article-journal",
    "Conference": "paper-conference",
    "Review": "article-journal",
    "Book": "book",
    "BookSection": "chapter",
    "Dataset": "dataset",
    "Editorial": "article-journal",
    "LettersAndComments": "article-journal",
    "News": "article-newspaper",
    "Study": "article-journal",
    "CaseReport": "article-journal",
    "ClinicalTrial": "article-journal",
    "MetaAnalysis": "article-journal",
}


@register
class SemanticScholarConnector(BaseConnector):
    """Semantic Scholar Graph API (https://api.semanticscholar.org/graph/v1)."""

    name: ClassVar[str] = "semantic_scholar"
    base_url: ClassVar[str] = "https://api.semanticscholar.org/graph/v1"
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "search",
            "get_by_id",
            "resolve_doi",
            "get_citations",
            "get_references",
            "get_oa_pdf",
        }
    )
    #: Keyless S2 tolerates roughly one request per second before it starts 429ing.
    rate_limit_interval: ClassVar[float] = 1.0
    #: Higher than the default: keyless 429s are routine, not exceptional.
    max_retries: ClassVar[int] = 4

    #: Env var carrying the optional key. Present: more quota. Absent: fewer requests per
    #: second, and nothing else. NEVER required.
    API_KEY_ENV: ClassVar[str] = "S2_API_KEY"

    def __init__(self, *args: Any, api_key: str | None = None, **kwargs: Any) -> None:
        key = api_key if api_key is not None else os.environ.get(self.API_KEY_ENV, "")
        self.api_key = key.strip()
        super().__init__(*args, **kwargs)

    def default_headers(self) -> dict[str, str]:
        """Add ``x-api-key`` when a key exists. A missing key is not an error."""
        headers = super().default_headers()
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    # -- operations --------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        """Relevance search over ``/paper/search``. An empty list is a clean negative."""
        text = (query or "").strip()
        if not text:
            return []
        params: dict[str, Any] = {
            "query": text,
            "limit": max(1, min(int(limit), MAX_SEARCH_LIMIT)),
            "fields": ",".join(SEARCH_FIELDS),
        }
        if since is not None:
            # S2 open-ended year range: "2020-" means 2020 or later.
            params["year"] = f"{int(since)}-"

        body = await self.request_json("paper/search", params)
        if body is None:
            return []
        payload = self._as_mapping(body, "paper/search")
        items = payload.get("data")
        if not items:
            # total == 0 comes back either as an absent or an empty "data". Both are the
            # query succeeding with nothing to say: a clean negative, not an error.
            return []
        if not isinstance(items, list):
            raise SourceError(
                self.name,
                "paper/search returned a 'data' field that is not a list.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint="paper/search",
            )
        return [self.to_record(item) for item in items if isinstance(item, Mapping)]

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        """Fetch one paper by S2 paper id, DOI, arXiv id, PMID, or CorpusId.

        Bare identifiers are prefixed automatically (``10.x/y`` -> ``DOI:10.x/y``). ``None``
        is a clean negative: S2 answered 404, and has no such paper.
        """
        native = self.native_id(identifier)
        if not native:
            return None
        endpoint = f"paper/{native}"
        body = await self.request_json(endpoint, {"fields": ",".join(PAPER_FIELDS)})
        if body is None:
            return None
        payload = self._as_mapping(body, endpoint)
        if not payload.get("paperId"):
            # An error envelope without a 404 status ("Paper with id ... not found"). The
            # query still succeeded, so this too is a clean negative.
            return None
        return self.to_record(payload)

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        """Fetch one paper by DOI. ``None`` is a clean negative.

        A string that is not shaped like a DOI at all short-circuits to ``None`` without a
        request: there is no DOI to look up, so no index could ever resolve it. That is a
        genuine negative about the input, not a claim about S2's health.
        """
        if not is_valid_doi(doi):
            return None
        return await self.get_by_id(f"DOI:{normalize_doi(doi)}")

    async def get_citations(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Papers citing ``identifier`` (forward edges)."""
        return await self._edges(identifier, "citations", "citingPaper", limit)

    async def get_references(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Papers cited by ``identifier`` (backward edges)."""
        return await self._edges(identifier, "references", "citedPaper", limit)

    async def get_oa_pdf(self, doi: str) -> OALocation | None:
        """The ``openAccessPdf`` location for a DOI, or ``None`` when S2 knows of no OA copy."""
        if not is_valid_doi(doi):
            return None
        endpoint = f"paper/DOI:{normalize_doi(doi)}"
        body = await self.request_json(endpoint, {"fields": ",".join(OA_FIELDS)})
        if body is None:
            return None
        payload = self._as_mapping(body, endpoint)
        oa = payload.get("openAccessPdf")
        if not isinstance(oa, Mapping):
            return None
        url = str(oa.get("url") or "").strip()
        if not url:
            return None
        return OALocation(
            url=url,
            content_type="pdf",
            source=self.name,
            license=str(oa.get("license") or ""),
            is_oa=True,
        )

    # -- internals ---------------------------------------------------------

    async def _edges(
        self, identifier: str, edge: str, item_key: str, limit: int
    ) -> list[CSLRecord]:
        native = self.native_id(identifier)
        if not native:
            return []
        endpoint = f"paper/{native}/{edge}"
        params = {
            "limit": max(1, min(int(limit), MAX_EDGE_LIMIT)),
            "fields": ",".join(EDGE_FIELDS),
        }
        body = await self.request_json(endpoint, params)
        if body is None:
            # 404: S2 has no such paper, so it has no edges for it. Clean negative.
            return []
        payload = self._as_mapping(body, endpoint)
        items = payload.get("data")
        if not items:
            return []
        if not isinstance(items, list):
            raise SourceError(
                self.name,
                f"{endpoint} returned a 'data' field that is not a list.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        records: list[CSLRecord] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            paper = item.get(item_key)
            # S2 emits a null side for an edge it cannot resolve to a paper. Skip those
            # rather than fabricating an empty record.
            if isinstance(paper, Mapping) and paper.get("paperId"):
                records.append(self.to_record(paper))
        return records

    def _as_mapping(self, body: Any, endpoint: str) -> Mapping[str, Any]:
        if not isinstance(body, Mapping):
            raise SourceError(
                self.name,
                f"{endpoint} returned a payload that is not a JSON object.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        return body

    @staticmethod
    def native_id(identifier: str) -> str:
        """Coerce a user-supplied identifier into an S2-addressable one.

        Passes through anything already prefixed (``DOI:``, ``ARXIV:``, ``CorpusId:``, ...)
        and a bare 40-hex S2 paper id. Bare DOIs and bare arXiv ids get their prefix added.
        """
        text = str(identifier or "").strip()
        if not text:
            return ""
        lowered = text.lower()
        if lowered.startswith(_KNOWN_PREFIXES):
            head, _, tail = text.partition(":")
            if head.lower() == "doi":
                return f"DOI:{normalize_doi(tail)}"
            return text
        if _HEX_ID_RE.match(text):
            return text.lower()
        doi = normalize_doi(text)
        if doi.startswith("10."):
            return f"DOI:{doi}"
        if _ARXIV_RE.match(text) or lowered.startswith("arxiv."):
            return f"ARXIV:{text}"
        return text

    # -- normalization -----------------------------------------------------

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one S2 paper object into a :class:`CSLRecord`."""
        external = raw.get("externalIds")
        external = external if isinstance(external, Mapping) else {}

        journal = raw.get("journal")
        journal = journal if isinstance(journal, Mapping) else {}
        venue_obj = raw.get("publicationVenue")
        venue_obj = venue_obj if isinstance(venue_obj, Mapping) else {}

        container = (
            str(journal.get("name") or "")
            or str(venue_obj.get("name") or "")
            or str(raw.get("venue") or "")
        )

        pmcid = str(external.get("PubMedCentral") or "")
        if pmcid and not pmcid.upper().startswith("PMC"):
            pmcid = f"PMC{pmcid}"

        oa = raw.get("openAccessPdf")
        oa = oa if isinstance(oa, Mapping) else {}

        issn = str(venue_obj.get("issn") or "")

        corpus_id = external.get("CorpusId")
        extra: dict[str, Any] = {}
        if corpus_id not in (None, ""):
            extra["corpus_id"] = str(corpus_id)
        oa_status = str(oa.get("status") or "")
        if oa_status:
            extra["oa_status"] = oa_status

        return CSLRecord(
            type=self._csl_type(raw),
            title=str(raw.get("title") or ""),
            # S2 gives one flat display name per author. normalize_authors (the model's own
            # normalizer) splits it into CSL family / given / suffix. Never done by hand here.
            author=normalize_authors(
                [
                    str(a.get("name") or "")
                    for a in raw.get("authors") or []
                    if isinstance(a, Mapping) and a.get("name")
                ]
            ),
            issued=self._issued(raw),
            container_title=container,
            volume=str(journal.get("volume") or ""),
            issue=str(journal.get("issue") or ""),
            page=str(journal.get("pages") or "").strip(),
            abstract=str(raw.get("abstract") or ""),
            DOI=str(external.get("DOI") or ""),
            URL=str(raw.get("url") or ""),
            ISSN=[issn] if issn else [],
            source=self.name,
            source_id=str(raw.get("paperId") or ""),
            s2_id=str(raw.get("paperId") or ""),
            arxiv_id=str(external.get("ArXiv") or ""),
            pmid=str(external.get("PubMed") or ""),
            pmcid=pmcid,
            citation_count=_as_int(raw.get("citationCount")),
            reference_count=_as_int(raw.get("referenceCount")),
            is_oa=_as_bool(raw.get("isOpenAccess")),
            oa_url=str(oa.get("url") or ""),
            extra=extra,
        )

    @staticmethod
    def _csl_type(raw: Mapping[str, Any]) -> str:
        types = raw.get("publicationTypes")
        if isinstance(types, list):
            for entry in types:
                mapped = _TYPE_MAP.get(str(entry))
                if mapped:
                    return mapped
        return "article-journal"

    @staticmethod
    def _issued(raw: Mapping[str, Any]) -> CSLDate | None:
        """Prefer the full publicationDate; fall back to the bare year."""
        date = str(raw.get("publicationDate") or "").strip()
        if date:
            parsed = CSLDate.parse(date)
            if parsed is not None and parsed.year is not None:
                return parsed
        return CSLDate.from_year(_as_int(raw.get("year")))


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    return bool(value)
