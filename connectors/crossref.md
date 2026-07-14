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
