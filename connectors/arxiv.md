# arXiv Connector

**What it provides**
Search of the arXiv preprint corpus by query, author, or category, returning metadata (title, authors, abstract, category, date, and the DOI and journal reference once a preprint is published) plus a free PDF for every resolvable paper. In the evidence kernel it implements `search`, `get_by_id` (old-style `math/0309136` and new-style `2005.13249` identifiers, with or without a `v2` version suffix), `get_oa_pdf` (arXiv is a reliable open-access source), and `resolve_doi` for arXiv-issued DOIs (`10.48550/arXiv.<id>`). arXiv has no DOI index and no citation graph, so `resolve_doi` on a publisher DOI, `get_citations`, and `get_references` are declared unsupported rather than answered with a misleading empty result.

**Mechanism**
Direct public API (export.arxiv.org, Atom XML) called from skills at runtime and by `core/researcher_core/connectors/arxiv.py`. No MCP server bundled. No key required.

**Install and environment variables**
Nothing to install. No environment variables needed: the connector calls the public export.arxiv.org API directly and is keyless. Optionally set `ARXIV_MAILTO` (or `RESEARCHER_CORE_MAILTO`) to a contact email, which is added to the User-Agent; arXiv has no polite-pool parameter, so this only helps them contact you. Requests are throttled to one every three seconds, per arXiv's stated policy.

**Used by**
fact-checking, literature-search, sota-finder

**Fallback when absent**
If the API is unreachable, skills fall back to manual web search or other configured literature sources (e.g. Semantic Scholar, CrossRef) for preprint coverage. Inside the kernel, a timeout, rate limit (HTTP 429), or 5xx raises `SourceError`, which forces an `inconclusive` verdict; it is never reported as "no match found", so a rate-limited arXiv can never contribute to a "likely fabricated" judgment.

**Data egress**
Hosts: `export.arxiv.org` (Atom metadata) and `arxiv.org` (the PDF, when `get_oa_pdf` fetches OA full text), both HTTPS. Sent: an arXiv ID, or a search query (by term, author, or category); an optional contact email from `ARXIV_MAILTO` or `RESEARCHER_CORE_MAILTO` folded into the User-Agent. A search query can carry manuscript-derived terms; an ID lookup or a PDF fetch carries only the identifier or URL. Requests are throttled to one every three seconds per arXiv policy. No manuscript file or section prose is sent. Remote retention: governed by arXiv's privacy policy (linked below).

**Terms of use**
arXiv metadata is reusable through the arXiv API under its Terms of Use (attribution and rate limits). Full-text PDFs keep each paper's own license, so a downloaded PDF is for local reading and verification, not redistribution (see the licensing and retention page). API terms: https://info.arxiv.org/help/api/tou.html . Licenses: https://info.arxiv.org/help/license/ . Verified as of 2026-07-14; re-verify at release.
