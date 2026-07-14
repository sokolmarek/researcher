# OpenAlex Connector

**What it provides**
Free-text work search, DOI / OpenAlex ID / arXiv ID lookup, forward and backward citation edges, open-access locations, citation counts, and the `is_retracted` flag that publication-status checking (axis b) reads. The broadest keyless index the kernel talks to.

**Mechanism**
Direct public REST API (api.openalex.org), called by `researcher_core.connectors.openalex`. No MCP server bundled. No key exists and none is needed; a contact email puts requests in the polite pool.

**Install and environment variables**
Nothing to install. Set `OPENALEX_MAILTO` (for example `OPENALEX_MAILTO=you@example.com`) so live requests carry `&mailto=` and land in the polite pool with more reliable rate limits. The address is added at the HTTP layer only: it never enters the snapshot or cache key, so a snapshot recorded on one machine replays on another that has no email set.

**Used by**
literature-search, fact-checking, citation-management, citation-context, research-gaps, sota-finder

**Fallback when absent**
A timeout, rate limit, or 5xx raises a source error, which forces an `inconclusive` verification verdict and is never treated as evidence of fabrication. A 404 on a DOI lookup is different: it is a clean negative (OpenAlex genuinely does not hold that work) and counts toward `unresolvable` only when every other queried source agrees. With OpenAlex unavailable, Crossref alone cannot satisfy the two-confirmation identity gate, so entries degrade to `inconclusive` rather than to a false accusation.
