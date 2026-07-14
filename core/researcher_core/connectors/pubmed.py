"""PubMed connector (NCBI E-utilities).

Two-step, as the API demands: ``esearch.fcgi`` returns PMIDs, then ``efetch.fcgi`` returns
the full MEDLINE records for those PMIDs as XML. ``esummary.fcgi`` is deliberately not used:
it omits the abstract and the full author list, and efetch gives both plus the
``ArticleIdList`` that carries the DOI and the PMCID.

What this connector implements: :meth:`search`, :meth:`get_by_id` (PMID, PMCID, or any other
article identifier PubMed indexes under ``[AID]``), and :meth:`resolve_doi`. Citation edges
(``elink``) and OA resolution are not implemented, so the base class raises
:class:`~researcher_core.connectors.base.UnsupportedOperation` for them rather than this
connector pretending to a capability it does not have. It does populate ``pmcid``, which is
the free-full-text route the axis (d) OA cascade consumes.

Clean negative versus source error (D9, and the reason this file is careful about it):

* esearch returning ``count: 0`` with an empty ``idlist`` is a CLEAN NEGATIVE. So is efetch
  returning an empty ``<PubmedArticleSet></PubmedArticleSet>``, which is exactly what NCBI
  sends for a syntactically valid but nonexistent PMID. Both come back as ``[]`` / ``None``.
* An ``<ERROR>`` element at the top of an eFetchResult, an ``ERROR`` key in an esearchresult,
  a body that is not the shape the API documents, unparseable XML, a 429, a 5xx, or a timeout
  are SOURCE ERRORS and raise :class:`~researcher_core.connectors.base.SourceError`. NCBI
  throttles hard (3 requests/second without a key), and a throttled index must never be
  allowed to look like evidence that a real citation was fabricated.

Keyless by default. ``NCBI_API_KEY`` is optional: it raises the rate ceiling from 3 to 10
requests per second and is never required. ``NCBI_EMAIL`` (or ``RESEARCHER_CORE_EMAIL``) sets
the polite-pool contact address. None of the three is part of the snapshot or cache key, so
snapshots recorded on one machine replay on any other machine, with or without a key.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import httpx

from ..model import CSLDate, CSLName, CSLRecord, is_valid_doi, normalize_doi
from . import register
from .base import BaseConnector, SourceError, SourceErrorKind

__all__ = ["PubMedConnector"]

ESEARCH = "esearch.fcgi"
EFETCH = "efetch.fcgi"

#: NCBI's ceiling is 3 requests/second without a key and 10 with one.
KEYLESS_INTERVAL = 0.34
KEYED_INTERVAL = 0.11

#: esearch caps retmax at 100000, but a single efetch GET has to carry every PMID, so the
#: connector caps a page at 100 ids to keep the URL and the snapshot a sane size.
MAX_PAGE = 100

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

#: MEDLINE publication type that marks the article itself as retracted. "Retraction of
#: Publication" is the notice, not the retracted paper, and must not be confused with it.
RETRACTED_TYPE = "Retracted Publication"


@register
class PubMedConnector(BaseConnector):
    """PubMed / MEDLINE via the NCBI E-utilities."""

    name: ClassVar[str] = "pubmed"
    base_url: ClassVar[str] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    capabilities: ClassVar[frozenset[str]] = frozenset({"search", "get_by_id", "resolve_doi"})
    rate_limit_interval: ClassVar[float] = KEYLESS_INTERVAL
    max_retries: ClassVar[int] = 2

    #: NCBI asks every client to identify itself with `tool` and `email`.
    tool_name: ClassVar[str] = "researcher-core"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        email: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = (api_key or os.environ.get("NCBI_API_KEY") or "").strip()
        self.email = (
            email
            or os.environ.get("NCBI_EMAIL")
            or os.environ.get("RESEARCHER_CORE_EMAIL")
            or ""
        ).strip()
        if self.api_key:
            # Instance-level override of the class default, so a keyed client runs at the
            # keyed ceiling without raising it for every other PubMedConnector in the process.
            self.rate_limit_interval = KEYED_INTERVAL  # type: ignore[misc]

    # -- transport ---------------------------------------------------------

    def default_headers(self) -> dict[str, str]:
        headers = super().default_headers()
        # efetch answers in XML whatever the Accept header says, but asking honestly costs
        # nothing and keeps proxies from second-guessing the response.
        headers["Accept"] = "application/json, text/xml;q=0.9, */*;q=0.8"
        return headers

    def _credential_params(self) -> dict[str, str]:
        """The identifying params NCBI wants, kept OUT of the snapshot and cache key.

        ``tool``, ``email``, and ``api_key`` do not change what the API returns, and a key is
        a secret that must never be written into a committed snapshot file. So they are
        injected here, at the transport edge, below the layer that computes the request key.
        """
        params: dict[str, str] = {"tool": self.tool_name}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    async def _http_json(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
    ) -> Any:
        merged = {**dict(params), **self._credential_params()}
        return await super()._http_json(
            endpoint, merged, method=method, headers=headers, url=url
        )

    def parse_response(self, response: httpx.Response, endpoint: str) -> Any:
        """JSON for esearch; parsed XML for efetch.

        The returned structure IS the snapshot body, so efetch is parsed into a stable
        JSON-serializable shape (``{"articles": [...]}``) here rather than downstream.
        """
        if endpoint != EFETCH:
            return super().parse_response(response, endpoint)
        if response.status_code in (404, 410):
            return None
        if response.status_code >= 400:
            raise SourceError(
                self.name,
                f"{response.request.url} returned HTTP {response.status_code}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                status_code=response.status_code,
                endpoint=endpoint,
            )
        return self.parse_efetch_xml(response.text, endpoint)

    # -- XML parsing -------------------------------------------------------

    def parse_efetch_xml(self, text: str, endpoint: str = EFETCH) -> dict[str, Any]:
        """Turn an efetch PubmedArticleSet into ``{"articles": [ ... ]}``.

        An empty article set is a clean negative and produces ``{"articles": []}``. An
        ``<ERROR>`` element with no articles is a malformed exchange, not a "no match", so it
        raises :class:`SourceError` and can only ever produce an ``inconclusive`` verdict.
        """
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise SourceError(
                self.name,
                f"efetch returned a body that is not valid XML: {exc}",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            ) from exc

        articles: list[dict[str, Any]] = []
        for element in root.findall("PubmedArticle"):
            parsed = _parse_pubmed_article(element)
            if parsed:
                articles.append(parsed)
        for element in root.findall("PubmedBookArticle"):
            parsed = _parse_pubmed_book(element)
            if parsed:
                articles.append(parsed)

        if not articles:
            error = root.find("ERROR")
            if error is not None:
                raise SourceError(
                    self.name,
                    f"efetch reported an error: {_text(error) or 'unspecified'}",
                    kind=SourceErrorKind.BAD_RESPONSE,
                    endpoint=endpoint,
                )
        return {"articles": articles}

    # -- operations --------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        term = str(query or "").strip()
        if not term:
            return []
        pmids = await self._esearch(term, limit=limit, since=since)
        if not pmids:
            return []
        return await self._efetch(pmids)

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        raw = _strip_pmid_prefix(str(identifier or "").strip())
        if not raw:
            return None
        if raw.isdigit():
            records = await self._efetch([raw])
            return records[0] if records else None
        if is_valid_doi(raw):
            return await self.resolve_doi(raw)
        # A PMCID, a publisher PII, or any other identifier: PubMed indexes them all under
        # the [AID] article-identifier field, so this stays a real query and a miss stays a
        # real clean negative.
        return await self._first_by_aid(raw)

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        key = normalize_doi(doi)
        if not key:
            return None
        record = await self._first_by_aid(key, expect_doi=key)
        return record

    # -- internals ---------------------------------------------------------

    async def _first_by_aid(
        self, identifier: str, *, expect_doi: str | None = None
    ) -> CSLRecord | None:
        """Resolve one record through the [AID] article-identifier index."""
        pmids = await self._esearch(f"{identifier}[AID]", limit=5)
        if not pmids:
            return None
        records = await self._efetch(pmids)
        if not records:
            return None
        if expect_doi is None:
            return records[0]
        # PubMed tokenizes identifiers, so [AID] can in principle match a neighbor. Only
        # answer with a record whose DOI is actually the DOI that was asked for; anything
        # else is a clean negative, never a confirmation.
        for record in records:
            if record.DOI == expect_doi:
                return record
        return None

    async def _esearch(
        self, term: str, *, limit: int = 25, since: int | None = None
    ) -> list[str]:
        """PMIDs for a term, best match first. An empty list is a clean negative."""
        page = max(1, min(int(limit), MAX_PAGE))
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": page,
            "sort": "relevance",
        }
        if since is not None:
            params["datetype"] = "pdat"
            params["mindate"] = str(int(since))
            params["maxdate"] = "3000"

        body = await self.request_json(ESEARCH, params)
        if body is None:  # 404 / 410 from a lookup endpoint: a clean negative.
            return []
        if not isinstance(body, Mapping):
            raise SourceError(
                self.name,
                f"esearch returned {type(body).__name__}, expected a JSON object.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=ESEARCH,
            )
        result = body.get("esearchresult")
        if not isinstance(result, Mapping):
            raise SourceError(
                self.name,
                "esearch response has no 'esearchresult' object.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=ESEARCH,
            )
        error = result.get("ERROR")
        if error:
            raise SourceError(
                self.name,
                f"esearch reported an error: {error}",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=ESEARCH,
            )
        idlist = result.get("idlist")
        if idlist is None:
            return []
        if not isinstance(idlist, Sequence) or isinstance(idlist, (str, bytes)):
            raise SourceError(
                self.name,
                "esearch 'idlist' is not a list.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=ESEARCH,
            )
        return [str(pmid) for pmid in idlist if str(pmid).strip()][:page]

    async def _efetch(self, pmids: Sequence[str]) -> list[CSLRecord]:
        """Full records for PMIDs, returned in the order the PMIDs were given."""
        ids = [str(p).strip() for p in pmids if str(p).strip()][:MAX_PAGE]
        if not ids:
            return []
        body = await self.request_json(
            EFETCH, {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
        )
        if body is None:
            return []
        if not isinstance(body, Mapping):
            raise SourceError(
                self.name,
                f"efetch snapshot body is {type(body).__name__}, expected an object.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=EFETCH,
            )
        articles = body.get("articles") or []
        records = [self.to_record(article) for article in articles if isinstance(article, Mapping)]
        order = {pmid: index for index, pmid in enumerate(ids)}
        records.sort(key=lambda r: order.get(r.pmid, len(order)))
        return records

    # -- normalization -----------------------------------------------------

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """One parsed efetch article into a :class:`CSLRecord`.

        Normalization (DOI case, whitespace, author splitting) is the dataclass's job; this
        only maps MEDLINE's field names onto CSL's.
        """
        pmid = str(raw.get("pmid") or "")
        pub_types = [str(t) for t in raw.get("publication_types") or []]
        extra: dict[str, Any] = {}
        if pub_types:
            extra["publication_types"] = pub_types
        if raw.get("journal_abbreviation"):
            extra["journal_abbreviation"] = str(raw["journal_abbreviation"])

        return CSLRecord(
            type=_csl_type(raw, pub_types),
            title=_clean_title(str(raw.get("title") or "")),
            author=[
                CSLName.from_csl_json(a)
                for a in raw.get("authors") or []
                if isinstance(a, Mapping)
            ],
            issued=_issued(raw),
            container_title=str(raw.get("journal") or ""),
            publisher=str(raw.get("publisher") or ""),
            volume=str(raw.get("volume") or ""),
            issue=str(raw.get("issue") or ""),
            page=str(raw.get("page") or ""),
            abstract=str(raw.get("abstract") or ""),
            DOI=str(raw.get("doi") or ""),
            URL=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            ISSN=[str(i) for i in raw.get("issn") or []],
            language=str(raw.get("language") or ""),
            keyword=[str(k) for k in raw.get("keywords") or []],
            source=self.name,
            source_id=pmid,
            pmid=pmid,
            pmcid=str(raw.get("pmcid") or ""),
            # True when MEDLINE has flagged the article itself as retracted. Absence is not
            # proof of the negative (MEDLINE lags), so it stays None rather than False, and
            # axis (b) cross-checks Crossref and OpenAlex.
            is_retracted=True if RETRACTED_TYPE in pub_types else None,
            extra=extra,
        )


# ---------------------------------------------------------------------------
# XML helpers (module level: pure functions over an ElementTree element)
# ---------------------------------------------------------------------------


def _text(element: ET.Element | None) -> str:
    """All text under ``element``, inline markup flattened, whitespace collapsed."""
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _find_text(parent: ET.Element | None, path: str) -> str:
    if parent is None:
        return ""
    return _text(parent.find(path))


def _parse_pubmed_article(element: ET.Element) -> dict[str, Any]:
    citation = element.find("MedlineCitation")
    if citation is None:
        return {}
    article = citation.find("Article")
    journal = article.find("Journal") if article is not None else None
    issue = journal.find("JournalIssue") if journal is not None else None

    ids = _article_ids(element)
    pmid = _find_text(citation, "PMID") or ids.get("pubmed", "")

    out: dict[str, Any] = {
        "pmid": pmid,
        "doi": ids.get("doi", "") or _doi_from_elocation(article),
        "pmcid": ids.get("pmc", ""),
        "title": _find_text(article, "ArticleTitle"),
        "abstract": _abstract(article),
        "authors": _authors(article),
        "journal": _find_text(journal, "Title"),
        "journal_abbreviation": _find_text(journal, "ISOAbbreviation"),
        "issn": [i for i in [_find_text(journal, "ISSN")] if i],
        "volume": _find_text(issue, "Volume"),
        "issue": _find_text(issue, "Issue"),
        "page": _pagination(article),
        "language": _find_text(article, "Language"),
        "publication_types": [
            _text(t) for t in article.findall("PublicationTypeList/PublicationType")
        ]
        if article is not None
        else [],
        "keywords": [_text(k) for k in citation.findall("KeywordList/Keyword")],
        "record_type": "article",
    }
    out.update(_pub_date(article, issue))
    return out


def _parse_pubmed_book(element: ET.Element) -> dict[str, Any]:
    """Bookshelf records (rare in PubMed search hits, but they must not vanish silently)."""
    document = element.find("BookDocument")
    if document is None:
        return {}
    book = document.find("Book")
    ids = _article_ids(element, document)
    title = _find_text(document, "ArticleTitle") or _find_text(book, "BookTitle")
    return {
        "pmid": _find_text(document, "PMID") or ids.get("pubmed", ""),
        "doi": ids.get("doi", ""),
        "pmcid": ids.get("pmc", ""),
        "title": title,
        "abstract": _abstract(document),
        "authors": _authors(document) or _authors(book),
        "journal": "",
        "publisher": _find_text(book, "Publisher/PublisherName"),
        "year": _as_int(_find_text(book, "PubDate/Year")),
        "language": _find_text(document, "Language"),
        "publication_types": [_text(t) for t in document.findall("PublicationType")],
        "keywords": [_text(k) for k in document.findall("KeywordList/Keyword")],
        "record_type": "book",
    }


def _article_ids(*elements: ET.Element | None) -> dict[str, str]:
    """``{"pubmed": "34265844", "doi": "10.1038/...", "pmc": "PMC8371605"}``."""
    out: dict[str, str] = {}
    for element in elements:
        if element is None:
            continue
        for node in element.findall(".//ArticleIdList/ArticleId"):
            id_type = (node.get("IdType") or "").strip().lower()
            value = _text(node)
            if id_type and value and id_type not in out:
                out[id_type] = value
    return out


def _doi_from_elocation(article: ET.Element | None) -> str:
    if article is None:
        return ""
    for node in article.findall("ELocationID"):
        if (node.get("EIdType") or "").strip().lower() == "doi":
            return _text(node)
    return ""


def _abstract(parent: ET.Element | None) -> str:
    if parent is None:
        return ""
    parts: list[str] = []
    for node in parent.findall("Abstract/AbstractText"):
        body = _text(node)
        if not body:
            continue
        label = (node.get("Label") or "").strip()
        parts.append(f"{label}: {body}" if label else body)
    return " ".join(parts)


def _authors(parent: ET.Element | None) -> list[dict[str, str]]:
    if parent is None:
        return []
    out: list[dict[str, str]] = []
    for node in parent.findall("AuthorList/Author"):
        collective = _find_text(node, "CollectiveName")
        if collective:
            out.append({"literal": collective})
            continue
        family = _find_text(node, "LastName")
        given = _find_text(node, "ForeName") or _find_text(node, "Initials")
        suffix = _find_text(node, "Suffix")
        if not (family or given):
            continue
        author: dict[str, str] = {"family": family, "given": given}
        if suffix:
            author["suffix"] = suffix
        out.append(author)
    return out


def _pagination(article: ET.Element | None) -> str:
    if article is None:
        return ""
    medline = _find_text(article, "Pagination/MedlinePgn")
    if medline:
        return medline
    start = _find_text(article, "Pagination/StartPage")
    end = _find_text(article, "Pagination/EndPage")
    if start and end:
        return f"{start}-{end}"
    if start:
        return start
    for node in article.findall("ELocationID"):
        if (node.get("EIdType") or "").strip().lower() == "pii":
            return _text(node)
    return ""


def _pub_date(article: ET.Element | None, issue: ET.Element | None) -> dict[str, Any]:
    """Issue PubDate first, then the electronic ArticleDate, then a free-text MedlineDate."""
    out: dict[str, Any] = {"year": None, "month": None, "day": None, "date_raw": ""}
    if issue is not None:
        node = issue.find("PubDate")
        if node is not None:
            year = _as_int(_find_text(node, "Year"))
            if year is not None:
                out["year"] = year
                out["month"] = _month(_find_text(node, "Month"))
                out["day"] = _as_int(_find_text(node, "Day"))
                return out
            medline_date = _find_text(node, "MedlineDate")
            if medline_date:
                out["date_raw"] = medline_date
                out["year"] = _leading_year(medline_date)
    if article is not None:
        node = article.find("ArticleDate")
        if node is not None:
            year = _as_int(_find_text(node, "Year"))
            if year is not None and out["year"] is None:
                out["year"] = year
                out["month"] = _as_int(_find_text(node, "Month"))
                out["day"] = _as_int(_find_text(node, "Day"))
    return out


def _month(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    numeric = _as_int(text)
    if numeric is not None and 1 <= numeric <= 12:
        return numeric
    return _MONTHS.get(text[:3].lower())


def _leading_year(value: str) -> int | None:
    """The first four-digit year in a MedlineDate like ``2020 Nov-Dec``."""
    for token in value.replace("-", " ").split():
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None


def _as_int(value: str) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _issued(raw: Mapping[str, Any]) -> CSLDate | None:
    year = raw.get("year")
    date_raw = str(raw.get("date_raw") or "")
    if year is None and not date_raw:
        return None
    return CSLDate(
        year=int(year) if year is not None else None,
        month=raw.get("month"),
        day=raw.get("day"),
        raw=date_raw,
    )


def _strip_pmid_prefix(value: str) -> str:
    """``"PMID: 34265844"`` -> ``"34265844"``. Anything else passes through untouched."""
    text = value.strip()
    lowered = text.lower()
    for prefix in ("pmid:", "pmid "):
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _clean_title(title: str) -> str:
    """MEDLINE ends every ArticleTitle with a period and brackets translated titles."""
    text = title.strip()
    if text.endswith("."):
        text = text[:-1].rstrip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    return text


def _csl_type(raw: Mapping[str, Any], pub_types: Sequence[str]) -> str:
    if raw.get("record_type") == "book":
        return "chapter" if raw.get("title") else "book"
    lowered = {t.lower() for t in pub_types}
    if "preprint" in lowered:
        return "article"
    return "article-journal"
