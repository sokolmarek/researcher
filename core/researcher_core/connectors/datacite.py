"""DataCite connector (D22): the DOIs Crossref does not index.

Crossref registers DOIs for the traditional literature (journal articles, books,
proceedings). DataCite registers DOIs for everything else research produces: datasets
(Dryad, figshare, Pangaea), software releases (every Zenodo GitHub release), preprints
(arXiv mints ``10.48550/arxiv.*`` through DataCite), theses, and reports. A reference
list that cites a dataset or a software release will come back as a clean negative from
Crossref, and under D9 a chorus of clean negatives is the ONLY refusal-grade state. So
DataCite is not a nice-to-have here: without it, citing your data would look like
fabricating it.

API: https://api.datacite.org, JSON:API shaped. Everything hangs off ``data.attributes``
for a single DOI, or ``data[].attributes`` for a search page. Keyless: credentials exist
only for minting DOIs, never for reading them. ``DATACITE_MAILTO`` (or the shared
``RESEARCHER_CORE_MAILTO``) only adds a contact address to the User-Agent.

Operations implemented: :meth:`search`, :meth:`get_by_id`, :meth:`resolve_doi`. The
citation graph and OA-location operations are declared unsupported rather than faked:
DataCite exposes related identifiers, but they are registration-time assertions from the
depositor, not a citation index, so they do not belong behind ``get_citations``.

Clean negative versus source error, the distinction D9 rests on:

* ``GET /dois/<doi>`` returning 404 means DataCite genuinely has no record for that DOI
  (which is the normal answer for every Crossref-registered DOI). That is a clean
  negative: ``None``.
* A 429, a 5xx, a timeout, or an unparseable body means we learned nothing. That is a
  :class:`~researcher_core.connectors.base.SourceError`, and it can never contribute to
  an ``unresolvable`` verdict.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from ..model import CSLDate, CSLName, CSLRecord, normalize_doi
from . import register
from .base import BaseConnector, SourceError, SourceErrorKind, escape_lucene

__all__ = ["DataCiteConnector"]

#: ``resourceTypeGeneral`` (the DataCite controlled vocabulary) mapped onto CSL types.
#: Preprints land on ``article-journal``: a preprint is a journal article that has not
#: cleared review yet, and every downstream emitter (BibTeX, RIS, CSL) already knows how
#: to render that. The two that justify this connector's existence, Dataset and Software,
#: map onto the CSL types of the same name.
RESOURCE_TYPE_TO_CSL: dict[str, str] = {
    "audiovisual": "motion_picture",
    "book": "book",
    "bookchapter": "chapter",
    "collection": "dataset",
    "computationalnotebook": "software",
    "conferencepaper": "paper-conference",
    "conferenceproceeding": "book",
    "datapaper": "article-journal",
    "dataset": "dataset",
    "dissertation": "thesis",
    "event": "event",
    "image": "figure",
    "journal": "periodical",
    "journalarticle": "article-journal",
    "model": "dataset",
    "outputmanagementplan": "document",
    "peerreview": "review",
    "physicalobject": "document",
    "preprint": "article-journal",
    "report": "report",
    "service": "software",
    "software": "software",
    "sound": "song",
    "standard": "standard",
    "text": "document",
    "workflow": "software",
    "other": "document",
}

#: Fallback when ``resourceTypeGeneral`` is missing or unknown: DataCite computes a
#: citeproc type itself, so we use theirs rather than guessing.
CITEPROC_FALLBACK: dict[str, str] = {
    "article": "article-journal",
    "article-journal": "article-journal",
    "book": "book",
    "chapter": "chapter",
    "dataset": "dataset",
    "paper-conference": "paper-conference",
    "report": "report",
    "software": "software",
    "thesis": "thesis",
}


@register
class DataCiteConnector(BaseConnector):
    """DataCite REST API: datasets, software, preprints, theses, and reports."""

    name: ClassVar[str] = "datacite"
    base_url: ClassVar[str] = "https://api.datacite.org"
    capabilities: ClassVar[frozenset[str]] = frozenset({"search", "get_by_id", "resolve_doi"})
    #: DataCite publishes no hard public quota, but asks for restraint. 5 req/s.
    rate_limit_interval: ClassVar[float] = 0.2
    #: DataCite caps ``page[size]`` at 1000; we cap at 100, which is all any caller wants.
    max_page_size: ClassVar[int] = 100

    def __init__(self, *, mailto: str | None = None, **kwargs: Any) -> None:
        self.mailto = (
            mailto
            or os.environ.get("DATACITE_MAILTO")
            or os.environ.get("RESEARCHER_CORE_MAILTO")
            or ""
        ).strip()
        super().__init__(**kwargs)

    def default_headers(self) -> dict[str, str]:
        """Standard headers, plus a contact address when one is configured.

        DataCite has no mailto query parameter (that is a Crossref and OpenAlex
        convention), so a contact address goes in the User-Agent, where DataCite's
        operators actually look when a client misbehaves. Purely optional: omitting it
        changes nothing about what the API returns.
        """
        headers = super().default_headers()
        if self.mailto:
            headers["User-Agent"] = f"{self.user_agent} (mailto:{self.mailto})"
        return headers

    # -- queries -----------------------------------------------------------

    def sanitize_query(self, query: str) -> str:
        """The common repair, then a Lucene escape on top, then the slash.

        DataCite's ``query`` parameter is an Elasticsearch ``query_string``, so it is the
        one source here that reads punctuation as grammar. Unescaped, it answers HTTP 400
        for a title carrying a stray brace, quote, or backslash, and it answers HTTP 200
        with ZERO HITS for a title carrying a colon ("Attention: Is All You Need" parses as
        a query for the term "Is" in a field named "Attention", which does not exist). The
        silent one is the more dangerous: it is a source error dressed up as a clean
        negative, and under D9 a clean negative is the only thing that can build toward a
        refusal. Escaping every reserved character turns the title back into the bag of
        words it always was, and DataCite finds the same 2371 records it finds for the
        colon-free spelling.

        The slash is the exception, and it has to be handled by substitution rather than by
        escaping, because Elasticsearch will not accept the escape. ``CRISPR\\/Cas9`` is a
        400 (``token_mgr_error``); ``CRISPR/Cas9`` is a clean 200. But a bare slash is not
        safe to leave either, because a SECOND one turns the pair into a Lucene regex
        (``/pattern/``) and the query silently stops meaning what it says. Replacing the
        slash with a space escapes that dilemma: DataCite tokenizes "CRISPR/Cas9" on the
        slash anyway, so "CRISPR Cas9" is the same query to it (both return 3213 records),
        and no regex delimiter survives to be paired up.
        """
        text = super().sanitize_query(query).replace("/", " ")
        return escape_lucene(" ".join(text.split()))

    # -- operations --------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
        resource_type: str | None = None,
    ) -> list[CSLRecord]:
        """Free-text search over DataCite's index.

        ``since`` becomes an Elasticsearch range clause on ``publicationYear``, because
        DataCite's ``query`` parameter accepts query-string syntax and there is no
        ``from-publication-year`` filter. ``resource_type`` narrows to one
        ``resourceTypeGeneral`` (``dataset``, ``software``, ...), which is how a caller
        asks DataCite for exactly the thing Crossref cannot answer.

        An empty list means the search ran and matched nothing. A dead API raises
        :class:`SourceError`.

        The query is escaped by :meth:`sanitize_query` BEFORE the ``since`` clause is
        wrapped around it, never after: the parentheses and the ``publicationYear:[...]``
        range below are our own Lucene syntax and must reach DataCite unescaped.
        """
        text = self.sanitize_query(query)
        if not text:
            return []
        size = max(1, min(int(limit), self.max_page_size))
        expression = text
        if since is not None:
            expression = f"({text}) AND publicationYear:[{int(since)} TO *]"
        params: dict[str, Any] = {"query": expression, "page[size]": size}
        if resource_type:
            params["resource-type-id"] = str(resource_type).strip().lower()

        body = await self.request_json("dois", params)
        items = self._data_list(body, "dois")
        return [self.to_record(item) for item in items][:size]

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        """DataCite's native identifier IS the DOI, so this is :meth:`resolve_doi`."""
        return await self.resolve_doi(identifier)

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        """Fetch one DOI from ``/dois/<doi>``.

        ``None`` is a clean negative, and it is the expected answer for any DOI that
        Crossref (not DataCite) registered. It never means DataCite fell over: that is a
        :class:`SourceError`.
        """
        key = normalize_doi(doi)
        if not key:
            return None
        body = await self.request_json(f"dois/{key}")
        if body is None:  # 404 / 410, mapped to a clean negative by parse_response.
            return None
        item = self._data_object(body, f"dois/{key}")
        if item is None:
            return None
        return self.to_record(item)

    # -- payload handling --------------------------------------------------

    def _data_list(self, body: Any, endpoint: str) -> list[Mapping[str, Any]]:
        """The ``data`` array of a JSON:API collection response. Absent means no results."""
        if body is None:
            return []
        if not isinstance(body, Mapping):
            raise SourceError(
                self.name,
                f"Expected a JSON:API object from {endpoint}, got {type(body).__name__}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        data = body.get("data")
        if data is None:
            return []
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            raise SourceError(
                self.name,
                f"Expected a JSON:API `data` array from {endpoint}, "
                f"got {type(data).__name__}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        return [item for item in data if isinstance(item, Mapping)]

    def _data_object(self, body: Any, endpoint: str) -> Mapping[str, Any] | None:
        """The ``data`` object of a JSON:API single-resource response."""
        if not isinstance(body, Mapping):
            raise SourceError(
                self.name,
                f"Expected a JSON:API object from {endpoint}, got {type(body).__name__}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        data = body.get("data")
        if data is None:
            return None
        if not isinstance(data, Mapping):
            raise SourceError(
                self.name,
                f"Expected a JSON:API `data` object from {endpoint}, "
                f"got {type(data).__name__}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        return data

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one JSON:API ``data`` item into a :class:`CSLRecord`.

        Everything interesting lives under ``attributes``; ``id`` is the DOI. No manual
        normalization happens here: :class:`CSLRecord` does that in ``__post_init__``.
        """
        attributes = raw.get("attributes")
        attrs: Mapping[str, Any] = attributes if isinstance(attributes, Mapping) else {}

        doi = normalize_doi(str(attrs.get("doi") or raw.get("id") or ""))
        container = attrs.get("container")
        container_map: Mapping[str, Any] = container if isinstance(container, Mapping) else {}

        return CSLRecord(
            type=self._csl_type(attrs),
            title=self._title(attrs),
            author=self._names(attrs.get("creators")),
            editor=self._contributor_editors(attrs.get("contributors")),
            issued=CSLDate.from_year(_as_int(attrs.get("publicationYear"))),
            container_title=str(container_map.get("title") or ""),
            publisher=self._publisher(attrs.get("publisher")),
            volume=str(container_map.get("volume") or ""),
            issue=str(container_map.get("issue") or ""),
            page=self._page(container_map),
            version=str(attrs.get("version") or ""),
            abstract=self._abstract(attrs.get("descriptions")),
            DOI=doi,
            URL=str(attrs.get("url") or (f"https://doi.org/{doi}" if doi else "")),
            language=str(attrs.get("language") or ""),
            keyword=self._subjects(attrs.get("subjects")),
            source=self.name,
            source_id=doi,
            citation_count=_as_int(attrs.get("citationCount")),
            reference_count=_as_int(attrs.get("referenceCount")),
            extra=self._extra(attrs),
        )

    # -- field mappers -----------------------------------------------------

    def _csl_type(self, attrs: Mapping[str, Any]) -> str:
        """Map ``types.resourceTypeGeneral`` onto a CSL type (D22's whole point).

        Falls back to DataCite's own ``types.citeproc``, then to ``article-journal``.
        The special case worth spelling out: arXiv deposits preprints as
        ``resourceTypeGeneral: Preprint``, and some older repositories deposit them as
        ``Text`` with ``resourceType: preprint``, so the free-text ``resourceType`` is
        consulted before the ``Text`` default is accepted.
        """
        types = attrs.get("types")
        type_map: Mapping[str, Any] = types if isinstance(types, Mapping) else {}
        general = str(type_map.get("resourceTypeGeneral") or "").strip().lower()
        specific = str(type_map.get("resourceType") or "").strip().lower()

        if general == "preprint" or "preprint" in specific:
            return "article-journal"
        # "Text" and "Other" are DataCite's catch-alls, so the depositor's own free-text
        # resourceType is more informative there than the controlled term.
        if general and general not in ("text", "other"):
            mapped = RESOURCE_TYPE_TO_CSL.get(general)
            if mapped:
                return mapped
        by_specific = RESOURCE_TYPE_TO_CSL.get(specific)
        if by_specific:
            return by_specific
        by_general = RESOURCE_TYPE_TO_CSL.get(general)
        if by_general:
            return by_general
        citeproc = str(type_map.get("citeproc") or "").strip().lower()
        return CITEPROC_FALLBACK.get(citeproc, "article-journal")

    def _title(self, attrs: Mapping[str, Any]) -> str:
        titles = attrs.get("titles")
        if not isinstance(titles, Sequence) or isinstance(titles, (str, bytes)):
            return ""
        for entry in titles:
            if isinstance(entry, Mapping) and not entry.get("titleType"):
                text = str(entry.get("title") or "")
                if text:
                    return text
        for entry in titles:
            if isinstance(entry, Mapping):
                text = str(entry.get("title") or "")
                if text:
                    return text
        return ""

    def _names(self, raw: Any) -> list[CSLName]:
        """DataCite creators/contributors into CSL names.

        Four shapes occur in the wild, and every one of them is in our own fixtures:

        * A real split: ``givenName`` "Alexandra", ``familyName`` "Elbakyan" (Dryad).
        * A bare ``name`` in "Family, Given" order with no parts broken out.
        * An organization: ``nameType: Organizational``.
        * The Zenodo pathology: ``nameType: Personal`` with the ENTIRE display name copied
          into ``familyName`` and no ``givenName`` at all ("Ines Montani" as a family
          name). Trusting that would make the first-author surname "Ines Montani", which
          matches nothing. When DataCite hands us no actual split we say so, and fall back
          to :func:`researcher_core.model.parse_name`, the same parser the kernel runs over
          BibTeX author strings, so both sides of a comparison are split the same way.
        """
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return []
        out: list[CSLName] = []
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            name = str(entry.get("name") or "").strip()
            given = str(entry.get("givenName") or "").strip()
            family = str(entry.get("familyName") or "").strip()
            if str(entry.get("nameType") or "").strip().lower() == "organizational":
                literal = name or family
                if literal:
                    out.append(CSLName(literal=literal))
                continue
            if given:
                out.append(CSLName(given=given, family=family or name))
            elif family and family != name:
                out.append(CSLName(family=family))
            elif name or family:
                out.append(CSLName.parse(name or family))
        return [n for n in out if not n.is_empty()]

    def _contributor_editors(self, raw: Any) -> list[CSLName]:
        """Only contributors DataCite labels as editors become CSL editors."""
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return []
        editors = [
            entry
            for entry in raw
            if isinstance(entry, Mapping)
            and str(entry.get("contributorType") or "").strip().lower() == "editor"
        ]
        return self._names(editors)

    def _publisher(self, raw: Any) -> str:
        """Publisher is a string in schema 4.4 and an object in 4.5. Accept both."""
        if isinstance(raw, Mapping):
            return str(raw.get("name") or "")
        return str(raw or "")

    def _page(self, container: Mapping[str, Any]) -> str:
        first = str(container.get("firstPage") or "").strip()
        last = str(container.get("lastPage") or "").strip()
        if first and last and first != last:
            return f"{first}-{last}"
        return first or last

    def _abstract(self, raw: Any) -> str:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return ""
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            if str(entry.get("descriptionType") or "").strip().lower() == "abstract":
                text = str(entry.get("description") or "")
                if text:
                    return text
        return ""

    def _subjects(self, raw: Any) -> list[str]:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return []
        seen: list[str] = []
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            subject = str(entry.get("subject") or "").strip()
            if subject and subject not in seen:
                seen.append(subject)
        return seen

    def _extra(self, attrs: Mapping[str, Any]) -> dict[str, Any]:
        """DataCite-specific fields worth keeping, under the CSL ``custom`` slot."""
        extra: dict[str, Any] = {}
        types = attrs.get("types")
        if isinstance(types, Mapping):
            general = str(types.get("resourceTypeGeneral") or "")
            if general:
                extra["datacite_resource_type"] = general
        client = attrs.get("client-id") or attrs.get("clientId")
        if client:
            extra["datacite_client"] = str(client)
        for key in ("downloadCount", "viewCount"):
            value = _as_int(attrs.get(key))
            if value is not None:
                extra[f"datacite_{key[0].lower()}{key[1:]}"] = value
        return extra


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
