"""OpenAlex connector (https://api.openalex.org).

OpenAlex is the broadest keyless index the kernel talks to, and the only one that ships
``is_retracted`` on the work object itself, so axis (b) (``status.py``) depends on this
connector populating that field. It is therefore mapped straight onto
:attr:`~researcher_core.model.CSLRecord.is_retracted` and never dropped.

Politeness: OpenAlex has a polite pool keyed on a contact email. Set ``OPENALEX_MAILTO``
and every live request carries ``&mailto=<address>``. No key exists and none is needed.

One subtlety worth stating, because it is deliberate: the ``mailto`` value is injected at
the HTTP layer (:meth:`OpenAlexConnector._http_json`), NOT into the params that
:meth:`~researcher_core.connectors.base.BaseConnector.request_json` hashes. The snapshot
and cache key of a request must not depend on whose machine made it, otherwise a snapshot
recorded with an email set could never be replayed on a machine without one, and CI would
have to know a contributor's address to run offline.

Clean negatives versus source errors, per the base-class contract:

* OpenAlex answers a DOI it has never heard of with **HTTP 404**. That is a CLEAN NEGATIVE:
  the query succeeded and the answer is "no such work". It returns ``None`` (the base
  ``parse_response`` already maps 404/410 to a ``None`` body), and never raises.
* A 429, a 5xx, a timeout, or a malformed body is a :class:`SourceError`. Under D9 that
  forces ``inconclusive``, so a downed OpenAlex can never accuse a researcher of
  fabricating a real citation.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, ClassVar

from ..model import CSLDate, CSLName, CSLRecord, OALocation, normalize_authors, normalize_doi
from . import register
from .base import BaseConnector

__all__ = ["OpenAlexConnector", "invert_abstract"]

#: Fields requested from every works endpoint. Explicit because the full work object is
#: enormous (topics, concepts, counts_by_year, every referenced work), and a snapshot is
#: only useful if a human can read it. Everything the CSLRecord and the four axes need is
#: here; nothing else is fetched.
WORK_FIELDS: tuple[str, ...] = (
    "id",
    "doi",
    "ids",
    "title",
    "display_name",
    "publication_year",
    "publication_date",
    "type",
    "language",
    "authorships",
    "primary_location",
    "best_oa_location",
    "open_access",
    "biblio",
    "cited_by_count",
    "cited_by_api_url",
    "referenced_works",
    "referenced_works_count",
    "is_retracted",
    "abstract_inverted_index",
)

_OPENALEX_ID_RE = re.compile(r"^[WwAaSsIiCcPpFfTt]\d{4,}$")
_ARXIV_ID_RE = re.compile(
    r"^(?:arxiv[:/])?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)$",
    re.I,
)

#: OpenAlex work types -> CSL-JSON types. Anything unlisted falls back to article-journal.
_TYPE_MAP: dict[str, str] = {
    "article": "article-journal",
    "journal-article": "article-journal",
    "book": "book",
    "book-chapter": "chapter",
    "dissertation": "thesis",
    "dataset": "dataset",
    "preprint": "article",
    "posted-content": "article",
    "proceedings-article": "paper-conference",
    "report": "report",
    "review": "review",
    "editorial": "article-journal",
    "letter": "article-journal",
    "paratext": "document",
    "other": "document",
}


def invert_abstract(inverted: Mapping[str, Any] | None) -> str:
    """Rebuild a plain abstract from OpenAlex's ``abstract_inverted_index``.

    OpenAlex ships no plain abstract string; it ships ``{word: [positions...]}``. Inverting
    it is just scattering each word back into its positions and reading left to right.
    Malformed entries (non-integer positions) are skipped rather than raising: a broken
    abstract must degrade to a shorter abstract, never to a source error.
    """
    if not inverted:
        return ""
    slots: list[tuple[int, str]] = []
    for word, positions in inverted.items():
        if not isinstance(positions, (list, tuple)):
            continue
        for position in positions:
            if isinstance(position, bool) or not isinstance(position, int):
                continue
            slots.append((position, str(word)))
    if not slots:
        return ""
    slots.sort(key=lambda item: item[0])
    return " ".join(word for _, word in slots)


def _strip_openalex_prefix(value: str) -> str:
    """``https://openalex.org/W123`` -> ``W123``. Anything else passes through, trimmed."""
    text = str(value or "").strip()
    if not text:
        return ""
    for prefix in ("https://openalex.org/", "http://openalex.org/", "openalex:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip().strip("/")


@register
class OpenAlexConnector(BaseConnector):
    """The OpenAlex works API: search, lookup, citation graph, and OA locations."""

    name: ClassVar[str] = "openalex"
    base_url: ClassVar[str] = "https://api.openalex.org"
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
    #: OpenAlex allows 10 requests/second in the polite pool. Stay well under it.
    rate_limit_interval: ClassVar[float] = 0.15
    #: OpenAlex caps ``per-page`` at 200, and ``filter=openalex:a|b|c`` at 50 OR-ed values.
    max_per_page: ClassVar[int] = 200
    max_or_values: ClassVar[int] = 50

    def __init__(self, *, mailto: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.mailto = (mailto or os.environ.get("OPENALEX_MAILTO") or "").strip()

    # -- transport ---------------------------------------------------------

    async def _http_json(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
    ) -> Any:
        """Add the polite-pool ``mailto`` to the live call only, never to the snapshot key."""
        merged = dict(params)
        if self.mailto and "mailto" not in merged:
            merged["mailto"] = self.mailto
        return await super()._http_json(
            endpoint, merged, method=method, headers=headers, url=url
        )

    # -- operations --------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        """Free-text search over OpenAlex works. Empty list is a clean negative.

        OpenAlex's ``search`` parameter understands quoted phrases and uppercase AND / OR /
        NOT, so an unbalanced quote or a dangling operator out of a truncated .bib title is
        a malformed query here too. :meth:`~BaseConnector.sanitize_query` repairs it.
        """
        text = self.sanitize_query(query)
        if not text:
            return []
        params: dict[str, Any] = {
            "search": text,
            "per-page": max(1, min(int(limit), self.max_per_page)),
            "select": ",".join(WORK_FIELDS),
        }
        if since is not None:
            params["filter"] = f"from_publication_date:{int(since)}-01-01"
        body = await self.request_json("works", params)
        return self._records_from_page(body, limit)

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        """Fetch one work by OpenAlex ID (``W123``), DOI, or arXiv ID. ``None`` = no match."""
        text = str(identifier or "").strip()
        if not text:
            return None

        native = _strip_openalex_prefix(text)
        if _OPENALEX_ID_RE.match(native):
            return await self._get_work(f"works/{native}")

        doi = normalize_doi(text)
        if doi.startswith("10."):
            return await self.resolve_doi(doi)

        arxiv = _ARXIV_ID_RE.match(text)
        if arxiv:
            # OpenAlex has no /works/arxiv:<id> route, but every arXiv work carries the
            # DataCite-minted arXiv DOI, which it does index.
            return await self.resolve_doi(f"10.48550/arxiv.{arxiv.group(1).lower()}")

        return None

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        """Fetch one work by DOI via ``/works/doi:<doi>``.

        A DOI OpenAlex does not hold answers 404, which the base ``parse_response`` turns
        into a ``None`` body. That is a clean negative and is returned as ``None``, exactly
        as the contract requires: it must never be raised as a :class:`SourceError`.
        """
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        return await self._get_work(f"works/doi:{normalized}")

    async def get_citations(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Works citing ``identifier`` (forward edges), via ``filter=cites:<openalex-id>``."""
        work_id = await self._resolve_openalex_id(identifier)
        if not work_id:
            return []
        params = {
            "filter": f"cites:{work_id}",
            "per-page": max(1, min(int(limit), self.max_per_page)),
            "select": ",".join(WORK_FIELDS),
        }
        body = await self.request_json("works", params)
        return self._records_from_page(body, limit)

    async def get_references(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Works ``identifier`` cites (backward edges), from its ``referenced_works`` list.

        The seed work carries reference IDs but not reference metadata, so the IDs are
        hydrated in OR-ed batches (``filter=openalex:W1|W2|...``, capped at 50 per request).
        """
        seed = await self.get_by_id(identifier)
        if seed is None:
            return []
        raw_ids = seed.extra.get("referenced_works") or []
        work_ids = [_strip_openalex_prefix(str(v)) for v in raw_ids]
        work_ids = [w for w in work_ids if w][: max(0, int(limit))]
        if not work_ids:
            return []

        records: list[CSLRecord] = []
        for start in range(0, len(work_ids), self.max_or_values):
            batch = work_ids[start : start + self.max_or_values]
            params = {
                "filter": "openalex:" + "|".join(batch),
                "per-page": len(batch),
                "select": ",".join(WORK_FIELDS),
            }
            body = await self.request_json("works", params)
            records.extend(self._records_from_page(body, len(batch)))
        return records[:limit]

    async def get_oa_pdf(self, doi: str) -> OALocation | None:
        """The best OA location OpenAlex knows for a DOI. ``None`` means no OA copy."""
        raw = await self._get_raw_work_by_doi(doi)
        if raw is None:
            return None
        return self._oa_location(raw)

    # -- internals ---------------------------------------------------------

    async def _get_work(self, endpoint: str) -> CSLRecord | None:
        body = await self.request_json(endpoint, {"select": ",".join(WORK_FIELDS)})
        if not isinstance(body, Mapping):
            return None
        return self.to_record(body)

    async def _get_raw_work_by_doi(self, doi: str) -> Mapping[str, Any] | None:
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        body = await self.request_json(
            f"works/doi:{normalized}", {"select": ",".join(WORK_FIELDS)}
        )
        return body if isinstance(body, Mapping) else None

    async def _resolve_openalex_id(self, identifier: str) -> str:
        """Coerce a DOI / arXiv ID / OpenAlex ID into a bare OpenAlex work ID (``W123``)."""
        native = _strip_openalex_prefix(str(identifier or ""))
        if _OPENALEX_ID_RE.match(native):
            return native
        record = await self.get_by_id(identifier)
        if record is None:
            return ""
        return _strip_openalex_prefix(record.openalex_id)

    def _records_from_page(self, body: Any, limit: int) -> list[CSLRecord]:
        """Parse a works page. A 404 body (``None``) or an empty page is a clean negative."""
        if not isinstance(body, Mapping):
            return []
        results = body.get("results")
        if not isinstance(results, list):
            return []
        out: list[CSLRecord] = []
        for item in results[: max(0, int(limit))]:
            if isinstance(item, Mapping):
                out.append(self.to_record(item))
        return out

    # -- parsing -----------------------------------------------------------

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one OpenAlex work into a :class:`CSLRecord`.

        ``is_retracted`` is carried through verbatim, because axis (b) reads it. So are
        ``cited_by_count`` (as ``citation_count``) and ``open_access.is_oa`` (as ``is_oa``).
        The abstract is reconstructed from the inverted index.
        """
        ids = _mapping(raw.get("ids"))
        openalex_id = _strip_openalex_prefix(str(raw.get("id") or ids.get("openalex") or ""))
        doi = normalize_doi(raw.get("doi") or ids.get("doi") or "")

        location = _mapping(raw.get("primary_location"))
        venue = _mapping(location.get("source"))

        biblio = _mapping(raw.get("biblio"))
        first_page = str(biblio.get("first_page") or "").strip()
        last_page = str(biblio.get("last_page") or "").strip()
        if first_page and last_page and first_page != last_page:
            page = f"{first_page}-{last_page}"
        else:
            page = first_page or last_page

        open_access = _mapping(raw.get("open_access"))
        oa_location = self._oa_location(raw)

        issn = venue.get("issn")
        if isinstance(issn, str):
            issn_list = [issn]
        elif isinstance(issn, list):
            issn_list = [str(v) for v in issn if v]
        else:
            issn_list = []
        issn_l = str(venue.get("issn_l") or "").strip()
        if issn_l and issn_l not in issn_list:
            issn_list.insert(0, issn_l)

        extra: dict[str, Any] = {}
        referenced = raw.get("referenced_works")
        if isinstance(referenced, list) and referenced:
            extra["referenced_works"] = [str(v) for v in referenced]
        cited_by_api_url = str(raw.get("cited_by_api_url") or "").strip()
        if cited_by_api_url:
            extra["cited_by_api_url"] = cited_by_api_url

        title = str(raw.get("title") or raw.get("display_name") or "")
        date = CSLDate.parse(str(raw.get("publication_date") or "")) or CSLDate.from_year(
            _as_int(raw.get("publication_year"))
        )
        if date is not None and date.year is None:
            date = CSLDate.from_year(_as_int(raw.get("publication_year")))

        return CSLRecord(
            type=_TYPE_MAP.get(str(raw.get("type") or "").lower(), "article-journal"),
            title=title,
            author=self._authors(raw),
            issued=date,
            container_title=str(venue.get("display_name") or ""),
            publisher=str(venue.get("host_organization_name") or ""),
            volume=str(biblio.get("volume") or ""),
            issue=str(biblio.get("issue") or ""),
            page=page,
            abstract=invert_abstract(raw.get("abstract_inverted_index")),
            DOI=doi,
            URL=str(location.get("landing_page_url") or "")
            or (f"https://doi.org/{doi}" if doi else ""),
            ISSN=issn_list,
            language=str(raw.get("language") or ""),
            source=self.name,
            source_id=openalex_id,
            openalex_id=openalex_id,
            arxiv_id=self._arxiv_id(raw, doi),
            pmid=_tail(str(ids.get("pmid") or "")),
            pmcid=_tail(str(ids.get("pmcid") or "")),
            citation_count=_as_int(raw.get("cited_by_count")),
            reference_count=_as_int(raw.get("referenced_works_count")),
            # Load-bearing for axis (b). OpenAlex is one of only two sources that carry it.
            is_retracted=_as_bool(raw.get("is_retracted")),
            is_oa=_as_bool(open_access.get("is_oa")),
            oa_url=oa_location.url if oa_location else "",
            extra=extra,
        )

    def _authors(self, raw: Mapping[str, Any]) -> list[CSLName]:
        """Authorship display names, split into CSL family / given by the model's parser.

        Never hand-rolled: :func:`~researcher_core.model.normalize_authors` owns name
        splitting so every connector produces identically shaped names.
        """
        authorships = raw.get("authorships")
        if not isinstance(authorships, list):
            return []
        names: list[str] = []
        for entry in authorships:
            if not isinstance(entry, Mapping):
                continue
            author = entry.get("author")
            display = ""
            if isinstance(author, Mapping):
                display = str(author.get("display_name") or "")
            if not display:
                display = str(entry.get("raw_author_name") or "")
            if display.strip():
                names.append(display.strip())
        return normalize_authors(names)

    def _arxiv_id(self, raw: Mapping[str, Any], doi: str) -> str:
        """arXiv ID from the arXiv DOI (``10.48550/arxiv.2501.01234``) or a preprint URL."""
        if doi.startswith("10.48550/arxiv."):
            return doi[len("10.48550/arxiv.") :]
        for key in ("primary_location", "best_oa_location"):
            location = raw.get(key)
            if not isinstance(location, Mapping):
                continue
            for url_key in ("pdf_url", "landing_page_url"):
                url = str(location.get(url_key) or "")
                match = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s?/]+?)(?:\.pdf)?$", url, re.I)
                if match:
                    return match.group(1)
        return ""

    def _oa_location(self, raw: Mapping[str, Any]) -> OALocation | None:
        """``best_oa_location`` -> :class:`OALocation`. ``None`` when there is no OA copy."""
        best = raw.get("best_oa_location")
        if not isinstance(best, Mapping):
            return None
        if best.get("is_oa") is False:
            return None
        pdf_url = str(best.get("pdf_url") or "").strip()
        landing = str(best.get("landing_page_url") or "").strip()
        url = pdf_url or landing
        if not url:
            return None
        host = _mapping(best.get("source"))
        return OALocation(
            url=url,
            content_type="pdf" if pdf_url else "html",
            source=self.name,
            version=str(best.get("version") or ""),
            license=str(best.get("license") or ""),
            host_type=str(host.get("type") or ""),
            is_oa=True,
        )


def _mapping(value: Any) -> dict[str, Any]:
    """``value`` as a plain dict when it is a mapping, else an empty dict. Never raises."""
    return dict(value) if isinstance(value, Mapping) else {}


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _tail(url: str) -> str:
    """``https://pubmed.ncbi.nlm.nih.gov/29456894`` -> ``29456894``."""
    return url.rstrip("/").rsplit("/", 1)[-1] if url else ""
