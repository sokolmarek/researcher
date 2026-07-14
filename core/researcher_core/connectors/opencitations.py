"""OpenCitations connector: an independent third source for the citation graph.

OpenCitations (COCI, now served by the unified OpenCitations Index) is a citation index,
not a metadata index. It answers exactly two questions:

* ``/citations/<doi>``  -> the edges pointing AT this DOI (who cites it).
* ``/references/<doi>`` -> the edges leaving this DOI (what it cites).

Each edge is an OCI object carrying the ``citing`` and ``cited`` DOI strings, a creation
date, and a timespan. It carries no title, no authors, no venue. So
:meth:`OpenCitationsConnector.get_citations` and :meth:`~OpenCitationsConnector.get_references`
return :class:`~researcher_core.model.CSLRecord` objects populated with the DOI and the edge
provenance only. That is honest (nothing is invented) and useful: ``search.py`` and
``graph.py`` can hydrate the DOIs through OpenAlex or Crossref. Its value is precisely that
it is a THIRD, independently built graph: an edge OpenAlex and Semantic Scholar both miss can
still be confirmed here.

``search``, ``get_by_id``, and ``resolve_doi`` do not exist in this API at all, so they raise
:class:`~researcher_core.connectors.base.UnsupportedOperation` rather than pretending.

Endpoint note: the documented COCI route
``https://opencitations.net/index/coci/api/v1/{citations,references}/<doi>`` now answers with
a 301 to ``https://api.opencitations.net/index/v1/...`` (the unified index, COCI data
included). This connector calls that canonical host directly, so every request is one hop.

D9 semantics, which this connector is careful about:

* An empty JSON array is a CLEAN NEGATIVE: OpenCitations knows of no such edges. It is an
  ordinary empty list, never an error.
* A timeout, 429, or 5xx is a :class:`~researcher_core.connectors.base.SourceError`, so a
  downed index can never be read as evidence that a real citation was fabricated.
* A non-DOI identifier is also a ``SourceError`` (kind ``config``), NOT an empty list: this
  index is DOI-addressed, so it was never actually asked the question, and a clean negative
  it did not give must never be manufactured on its behalf.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from ..model import CSLRecord, is_valid_doi, normalize_doi
from . import register
from .base import BaseConnector, SourceError, SourceErrorKind, UnsupportedOperation

__all__ = ["OpenCitationsConnector"]

#: Optional access token (https://opencitations.net/accesstoken). It only ADDS headroom on
#: the rate limiter; every operation here works keyless.
TOKEN_ENV_VAR = "OPENCITATIONS_TOKEN"

#: Optional contact address advertised in the User-Agent, the OpenCitations analogue of a
#: polite-pool mailto. Never required.
MAILTO_ENV_VARS = ("OPENCITATIONS_MAILTO", "RESEARCHER_MAILTO")


@register
class OpenCitationsConnector(BaseConnector):
    """Citation-graph edges from the OpenCitations Index (COCI and successors)."""

    name = "opencitations"
    base_url = "https://api.opencitations.net/index/v1"
    capabilities = frozenset({"get_citations", "get_references"})
    rate_limit_interval = 0.2
    max_retries = 2

    def __init__(
        self,
        *,
        token: str | None = None,
        mailto: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.token = token or os.environ.get(TOKEN_ENV_VAR, "").strip()
        self.mailto = mailto or _mailto_from_env()
        super().__init__(**kwargs)

    def default_headers(self) -> dict[str, str]:
        headers = super().default_headers()
        if self.mailto:
            headers["User-Agent"] = f"{self.user_agent} mailto:{self.mailto}"
        if self.token:
            # Documented OpenCitations header. Keyless callers simply never send it.
            headers["authorization"] = self.token
        return headers

    # -- unsupported operations -------------------------------------------
    #
    # COCI indexes citation EDGES. It has no free-text search, no work lookup, and no DOI
    # metadata resolution. Declaring that honestly (rather than faking a lookup out of the
    # edge list) is what lets search.py skip this source for those operations instead of
    # recording a misleading outcome for it.

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        raise UnsupportedOperation(self.name, "search")

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        raise UnsupportedOperation(self.name, "get_by_id")

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        raise UnsupportedOperation(self.name, "resolve_doi")

    # -- the citation graph ------------------------------------------------

    async def get_citations(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Works citing ``identifier``. Reads each edge's ``citing`` DOI.

        An empty list is a clean negative: OpenCitations has no incoming edges for this DOI.
        """
        edges = await self._edges("citations", identifier)
        return self._records(edges, doi_field="citing", role="cites", limit=limit)

    async def get_references(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Works cited by ``identifier``. Reads each edge's ``cited`` DOI.

        An empty list is a clean negative: OpenCitations has no outgoing edges for this DOI.
        """
        edges = await self._edges("references", identifier)
        return self._records(edges, doi_field="cited", role="cited_by", limit=limit)

    # -- internals ---------------------------------------------------------

    async def _edges(self, operation: str, identifier: str) -> list[Mapping[str, Any]]:
        """Fetch one edge list. Returns ``[]`` for a clean negative; raises on a real failure."""
        doi = normalize_doi(identifier)
        if not is_valid_doi(doi):
            # NOT an empty list. The index is DOI-addressed, so it was never asked anything;
            # inventing a clean negative here would let a bad identifier read as evidence of
            # fabrication under D9. A config-kind SourceError forces `inconclusive` instead.
            raise SourceError(
                self.name,
                f"OpenCitations is addressed by DOI only; {identifier!r} is not a DOI.",
                kind=SourceErrorKind.CONFIG,
                endpoint=operation,
            )

        # The DOI lives in the path, so it belongs in the endpoint (which is what keys the
        # snapshot), not in params: sending it as a query parameter would put a stray
        # `?doi=` on every live request.
        endpoint = f"{operation}/{doi}"
        url = f"{self.base_url}/{operation}/{quote(doi, safe='/')}"
        body = await self.request_json(endpoint, url=url)

        if body is None:
            # base.parse_response maps 404/410 to None. For a lookup route that is a clean
            # negative: the query ran, the index holds nothing under this DOI.
            return []
        if not isinstance(body, list):
            raise SourceError(
                self.name,
                f"Expected a JSON array of OCI edges from {endpoint}, got {type(body).__name__}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                endpoint=endpoint,
            )
        return [edge for edge in body if isinstance(edge, Mapping)]

    def _records(
        self,
        edges: list[Mapping[str, Any]],
        *,
        doi_field: str,
        role: str,
        limit: int,
    ) -> list[CSLRecord]:
        """Turn edges into DOI-only records: deduplicated, order-preserving, capped at ``limit``."""
        out: list[CSLRecord] = []
        seen: set[str] = set()
        for edge in edges:
            record = self.to_record(edge, doi_field=doi_field, role=role)
            if record is None or record.DOI in seen:
                continue
            seen.add(record.DOI)
            out.append(record)
            if limit is not None and limit > 0 and len(out) >= limit:
                break
        return out

    def to_record(  # type: ignore[override]
        self,
        raw: Mapping[str, Any],
        *,
        doi_field: str = "cited",
        role: str = "cited_by",
    ) -> CSLRecord | None:
        """Normalize one OCI edge into a DOI-only :class:`CSLRecord`.

        Returns ``None`` when the edge carries no usable DOI on the requested side (COCI does
        emit edges with an empty ``cited`` string). No title, author, or year is set, because
        the API supplies none: a hydration pass through OpenAlex or Crossref fills those in.
        """
        dois = _split_dois(raw.get(doi_field))
        if not dois:
            return None
        primary, aliases = dois[0], dois[1:]

        extra: dict[str, Any] = {"edge_role": role}
        # Everything below is verbatim from the payload; nothing is inferred.
        for key in ("creation", "timespan", "journal_sc", "author_sc"):
            value = raw.get(key)
            if value not in (None, ""):
                extra[key] = value
        if aliases:
            # One OpenCitations entity can carry several DOIs (a preprint and its version of
            # record). Keep them all rather than silently dropping the alternates.
            extra["doi_aliases"] = aliases

        return CSLRecord(
            DOI=primary,
            source=self.name,
            source_id=str(raw.get("oci") or ""),
            URL=f"https://doi.org/{primary}",
            extra=extra,
        )


def _split_dois(value: Any) -> list[str]:
    """Split an OCI ``citing`` / ``cited`` field into its normalized DOIs.

    The field holds one DOI, several space-separated DOIs (one entity, several DOIs), or the
    empty string (the endpoint of the edge has no DOI at all).
    """
    if not isinstance(value, str):
        return []
    out: list[str] = []
    for token in value.split():
        doi = normalize_doi(token)
        if is_valid_doi(doi) and doi not in out:
            out.append(doi)
    return out


def _mailto_from_env() -> str:
    for name in MAILTO_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""
