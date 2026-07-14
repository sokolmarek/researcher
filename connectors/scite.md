# Scite Connector

**What it provides**
Smart Citation context (supporting, contrasting, mentioning classification), citation statement search, full-text excerpt retrieval, and retraction/correction checks via editorial notices.

**Mechanism**
MCP server that the USER connects themselves (Scite MCP / claude.ai Scite connector; requires a Scite account, full access needs a subscription). The plugin does NOT bundle an .mcp.json today; bundling is planned. When connected, it is the primary citation-context source.

**Install and environment variables**
User connects the Scite MCP server through claude.ai (or their Claude Code MCP config) using their own Scite account credentials. No plugin-side environment variables or install steps are required; the plugin only calls the tools once the user has connected them.

**Used by**
citation-management, fact-checking, citation-context, literature-search, research-gaps, sota-finder, journal-finder

**Fallback when absent**
Skills fall back to other configured literature sources (e.g. Semantic Scholar, CrossRef, PubMed, arXiv, Google Scholar) or manual/web search for citation verification, losing Scite's supporting/contrasting classification and Smart Citation excerpts.
