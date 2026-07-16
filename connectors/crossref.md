# Crossref Connector

**What it provides**
DOI resolution, bibliographic metadata lookup, reference validation, and citation counts, drawn directly from the Crossref REST API.

**Mechanism**
Direct public REST API (api.crossref.org) called from skills and by scripts/bib-validator.py. No MCP server bundled. No key required; a mailto User-Agent puts requests in the polite pool.

**Install and environment variables**
Nothing to install. Set a `CROSSREF_MAILTO` environment variable (or pass a mailto parameter) so requests use the polite pool and get more reliable rate limits.

**Used by**
citation-management, fact-checking, literature-search, journal-finder

**Fallback when absent**
If the API is unreachable, these skills fall back to manual DOI entry and skip automated reference validation, flagging citations as unverified instead.

**Data egress**
Host: `api.crossref.org` (HTTPS). Sent: a DOI to resolve, or bibliographic query terms (title, author, year) for reference validation, plus the polite-pool address from `CROSSREF_MAILTO` in both the User-Agent and the `mailto` parameter when set. A title query can carry a reference title taken from the manuscript bibliography; a DOI lookup carries only the DOI. Core sends no manuscript file or section prose. Remote retention: governed by Crossref's privacy policy (linked below); the mailto is a politeness signal, not an identifier of your machine.

**Terms of use**
Crossref metadata is open and, for the great majority of records, free of reuse restrictions (CC0-facing); the REST API is free and keyless. Metadata license: https://www.crossref.org/documentation/retrieve-metadata/rest-api/ . Privacy: https://www.crossref.org/operations-and-sundry/privacy/ . Verified as of 2026-07-14; re-verify at release.
