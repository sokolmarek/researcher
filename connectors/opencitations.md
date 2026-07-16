# OpenCitations Connector

**What it provides**
Citation-graph edges (which works cite a DOI, and which DOIs a work cites) from the OpenCitations Index, the open citation database behind COCI. It is an independently built graph, so it supplements OpenAlex and Semantic Scholar rather than duplicating them: an edge those two miss can still be confirmed here. It returns edges only, with no titles, authors, or venues, so records come back carrying the DOI (plus the edge provenance) and are hydrated through OpenAlex or Crossref.

**Mechanism**
Direct public REST API, implemented in `core/researcher_core/connectors/opencitations.py` as the `opencitations` connector. No MCP server. No key required. The documented COCI route (`opencitations.net/index/coci/api/v1/...`) now redirects to the unified index at `api.opencitations.net/index/v1/`, which is what the connector calls. It implements `get_citations` and `get_references`; `search`, `get_by_id`, `resolve_doi`, and `get_oa_pdf` do not exist in this API and are declared unsupported.

**Install and environment variables**
Nothing to install. Both optional: `OPENCITATIONS_TOKEN` (a free access token from https://opencitations.net/accesstoken) raises rate-limit headroom, and `OPENCITATIONS_MAILTO` (or `RESEARCHER_MAILTO`) adds a contact address to the User-Agent. Every operation works with neither set.

**Used by**
citation-management, fact-checking, citation-context, literature-search (citation-graph traversal)

**Fallback when absent**
If the API is unreachable, graph traversal falls back to the OpenAlex and Semantic Scholar edges alone, and the affected references are reported as inconclusive rather than unresolvable: a source outage is never counted as evidence that a citation was fabricated.

**Data egress**
Host: `api.opencitations.net` (the unified index, `/index/v1/`, HTTPS). Sent: a DOI, to fetch its citing or cited edges; optional `OPENCITATIONS_TOKEN` and a contact address from `OPENCITATIONS_MAILTO` or `RESEARCHER_MAILTO` in the User-Agent. This is a DOI-lookup service returning edges only, so the query cannot carry manuscript prose. The access token, when set, identifies your usage to OpenCitations. Remote retention: governed by the OpenCitations privacy policy (linked below).

**Terms of use**
OpenCitations citation data is released under CC0, so it may be reused without restriction; the API is free, and an optional access token raises rate-limit headroom. About and license: https://opencitations.net/ . Privacy: https://opencitations.net/privacy . Verified as of 2026-07-14; re-verify at release.
