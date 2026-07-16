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

**Data egress**
Core makes no call to Google Scholar: there is no sanctioned API, so the plugin integrates none. When Scholar coverage is wanted, a skill uses the AI assistant's built-in web search with a `site:scholar.google.com` query. That query travels through the assistant's web-search provider and Google, not through core, and it can carry manuscript-derived search terms. It is governed by the assistant provider's and Google's terms, not by Researcher.

**Terms of use**
Documentation-only. Google Scholar has no free, sanctioned API and discourages automated access, so Researcher does not integrate it programmatically; any traffic is the assistant's web search under Google's terms. See https://scholar.google.com/intl/en/scholar/about.html . Verified as of 2026-07-14; re-verify at release.
