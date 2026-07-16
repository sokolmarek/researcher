# Semantic Scholar Connector

**What it provides**
Paper search, citation graph traversal, author lookup, and paper recommendations, drawn from the Semantic Scholar corpus.

**Mechanism**
Direct public REST API (api.semanticscholar.org) called from skills at runtime. No MCP server bundled. Works keyless at low volume; S2_API_KEY raises rate limits.

**Install and environment variables**
Nothing to install. Optionally set S2_API_KEY in your environment to raise rate limits above the keyless tier.

**Used by**
fact-checking, literature-search, writing-style-analysis, sota-finder

**Fallback when absent**
Without S2_API_KEY, skills still call the API keyless but may hit rate limits sooner, so searches fall back to smaller batches or slower retries.

**Data egress**
Host: `api.semanticscholar.org` (HTTPS). Sent: a search query, an author name, or paper / DOI identifiers; when set, `S2_API_KEY` is sent as a request header. A free-text search can carry manuscript-derived terms; an ID lookup carries only the identifier. The API key is a credential that identifies your usage to Semantic Scholar, so unlike the optional polite-pool emails it is an identifier you are choosing to attach. No manuscript file or section prose is sent. Remote retention: governed by the Allen Institute for AI privacy policy (linked below).

**Terms of use**
The Semantic Scholar Academic Graph is provided under ODC-BY 1.0; the API carries rate limits and reuse terms, and an API key raises the rate ceiling. API license: https://www.semanticscholar.org/product/api/license . Privacy: https://allenai.org/privacy-policy . Verified as of 2026-07-14; re-verify at release.
