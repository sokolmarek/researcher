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

**Data egress**
Core makes no call to Scite: nothing leaves through this plugin for it. Egress happens only through the Scite MCP server that you connect with your own account. What that server sends (DOIs and citation-statement queries) and how long Scite keeps it is governed by Scite's terms and your subscription, applied through your MCP client, not by Researcher.

**Terms of use**
User-connected MCP, separately governed. Scite is a subscription service; its terms and privacy policy apply to what you send it. See https://scite.ai/ . Verified as of 2026-07-14; re-verify at release.
