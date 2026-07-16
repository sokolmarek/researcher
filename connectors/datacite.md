# DataCite Connector

**What it provides**
DOI resolution and metadata for the research outputs Crossref does not register: datasets (Dryad, figshare, Pangaea), software releases (every Zenodo release of a GitHub repository), preprints (arXiv mints its `10.48550/arxiv.*` DOIs through DataCite), theses, and reports. Free-text search across that same index, filterable to one resource type. This is why a cited dataset or software release resolves instead of coming back unverified.

**Mechanism**
Direct public REST API (api.datacite.org), JSON:API shaped, called by the `datacite` connector in `core/` (`researcher_core.connectors.datacite`). No MCP server bundled. No key required, and none exists for reading: DataCite credentials only mint DOIs. Implemented operations are `search`, `get_by_id`, and `resolve_doi`. Citation-graph traversal (`get_citations`, `get_references`) and OA-location resolution (`get_oa_pdf`) are declared unsupported rather than faked; DataCite exposes depositor-asserted related identifiers, which are not a citation index.

**Install and environment variables**
Nothing to install. Optionally set `DATACITE_MAILTO` (or the shared `RESEARCHER_CORE_MAILTO`) to a contact address. DataCite has no mailto query parameter, so the address is added to the User-Agent instead; it is entirely optional and changes nothing about what the API returns.

**Used by**
fact-checking, citation-management, literature-search, implementation (software and dataset citations)

**Fallback when absent**
If the API is unreachable, the affected reference is reported as `inconclusive`, never as unresolvable. A timeout, a rate limit, or a 5xx raises a source error, which can never count as evidence that a citation was fabricated; only a clean negative (the query succeeded and DataCite genuinely holds no such DOI) does. A 404 from `/dois/<doi>` is exactly that clean negative, and it is the expected answer for any Crossref-registered DOI.

**Data egress**
Host: `api.datacite.org` (HTTPS). Sent: a DOI to resolve, or a free-text search query plus an optional resource-type filter, with an optional contact address from `DATACITE_MAILTO` or `RESEARCHER_CORE_MAILTO` in the User-Agent. Read access is keyless. A search query can carry manuscript-derived terms (a dataset or software title); a `resolve_doi` or `get_by_id` call carries only the DOI. No manuscript file or section prose is sent. Remote retention: governed by DataCite's privacy policy (linked below).

**Terms of use**
DataCite metadata is published under CC0 1.0, so it may be reused without restriction; read access is free and keyless (DataCite credentials only mint DOIs, and Researcher never uses them). Metadata terms: https://datacite.org/ . Privacy: https://datacite.org/privacy-policy/ . Verified as of 2026-07-14; re-verify at release.
