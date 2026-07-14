# Zotero Connector

**What it provides**
Access to a user's Zotero reference library: list collections, get items, export BibTeX, and sync the library. Useful for pulling existing bibliographies into a manuscript's reference file.

**Mechanism**
Community zotero-mcp MCP server, user-installed (for example: uvx zotero-mcp; env vars ZOTERO_API_KEY, ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE; check the zotero-mcp README for exact names). NOT bundled today; .mcp.json bundling is planned.

**Install and environment variables**
Not installed by this plugin. The user installs the community zotero-mcp server themselves (for example via uvx or pip) and configures it in their own MCP client settings, setting ZOTERO_API_KEY, ZOTERO_LIBRARY_ID, and ZOTERO_LIBRARY_TYPE (or the equivalent names documented by that server). Consult the zotero-mcp README for current variable names and setup steps.

**Used by**
citation-management

**Fallback when absent**
citation-management falls back to manual BibTeX entry and CrossRef API validation instead of pulling items directly from a Zotero library.
