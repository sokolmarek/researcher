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
