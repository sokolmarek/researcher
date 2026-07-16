# PubMed Connector

**What it provides**
Access to PubMed/MEDLINE biomedical literature: search (esearch), record retrieval (efetch), and citation/related-article linking (elink) against the NCBI E-utilities API.

**Mechanism**
Direct public REST API (NCBI E-utilities) called from skills at runtime via web fetches or scripts. No MCP server bundled. No API key required for polite low-volume use; NCBI_API_KEY raises rate limits.

**Install and environment variables**
Nothing to install. Skills call https://eutils.ncbi.nlm.nih.gov/ directly. Optionally set NCBI_API_KEY in the environment to raise the default rate limit.

**Used by**
fact-checking, literature-search, journal-finder

**Fallback when absent**
If the E-utilities API is unreachable, affected skills fall back to other configured literature sources (for example Semantic Scholar or CrossRef) and note reduced biomedical-specific coverage.

**Data egress**
Host: `eutils.ncbi.nlm.nih.gov` (NCBI E-utilities, HTTPS). Sent: a search query (esearch), record identifiers (efetch), or linking identifiers (elink); optional `NCBI_API_KEY`, `tool`, and `email` parameters, none of which enters the snapshot or cache key. A free-text search can carry manuscript-derived terms; an identifier fetch carries only the PMID. The API key, when set, identifies your usage to NCBI. No manuscript file or section prose is sent. Remote retention: governed by the NLM privacy and web policies (linked below).

**Terms of use**
The E-utilities have a usage policy (rate limits, and registering an API key or a tool and email for higher volume). PubMed records are US government works subject to NLM's usage guidelines, and the PMC Open Access Subset carries per-article licenses, so only OA-subset articles are retrieved as full text. E-utilities policy: https://www.ncbi.nlm.nih.gov/books/NBK25497/ . PMC OA subset: https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/ . Web policies: https://www.nlm.nih.gov/web_policies.html . Verified as of 2026-07-14; re-verify at release.
