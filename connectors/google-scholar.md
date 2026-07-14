# Google Scholar Connector

**What it provides**
Broad academic search coverage across disciplines, including citation counts and links to full text or PDFs where available. Least structured of the literature sources the plugin considers.

**Mechanism**
Docs-only. There is no stable free Google Scholar API; the plugin does not integrate it programmatically. Skills fall back to general web search when Scholar coverage is wanted.

**Install and environment variables**
Nothing to install. When Scholar coverage is desired, skills use Claude's web search tool with `site:scholar.google.com` queries instead of a dedicated API call.

**Used by**
fact-checking, literature-search, writing-style-analysis, sota-finder

**Fallback when absent**
Skills that would otherwise query Scholar directly run a general web search scoped to `site:scholar.google.com`, then treat results as unstructured leads to verify against primary sources (CrossRef, Semantic Scholar, or the publisher record) rather than as authoritative metadata.
