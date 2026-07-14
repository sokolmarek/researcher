# arXiv Connector

**What it provides**
Search of the arXiv preprint corpus by query, author, or category, returning metadata (title, authors, abstract, category, date) and links to PDFs.

**Mechanism**
Direct public API (export.arxiv.org) called from skills at runtime. No MCP server bundled. No key required.

**Install and environment variables**
Nothing to install. No environment variables needed: the connector calls the public export.arxiv.org API directly.

**Used by**
fact-checking, literature-search, sota-finder

**Fallback when absent**
If the API is unreachable, skills fall back to manual web search or other configured literature sources (e.g. Semantic Scholar, CrossRef) for preprint coverage.
