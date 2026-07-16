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

**Data egress**
Host: `api.openalex.org` (HTTPS). Sent: the free-text search query, or a DOI / OpenAlex ID / arXiv ID to resolve, plus `&mailto=` from `OPENALEX_MAILTO` when set. A `search` can carry manuscript-derived terms (a title, keywords, or a claim phrase used as a query string), so treat a search as sending its query text; core never uploads a manuscript file or section prose, and the identity and status checks read only the returned record. The polite-pool email is the only contact string attached, and it is deliberately excluded from the snapshot and cache key, so a recording replays on any machine. Remote retention: governed by OpenAlex's privacy policy (linked below); no cookie, account, or persistent identifier of you is sent.

**Terms of use**
OpenAlex data is released under CC0 (public domain), so the metadata it returns may be reused without restriction; the service is free and keyless, and the polite pool asks only for a contact email. Data license: https://docs.openalex.org/ . Privacy: https://openalex.org/privacy-policy . Verified as of 2026-07-14; re-verify at release.
