---
title: Connectors
description: External data connectors that feed Researcher's literature search, citation context, and reference management.
sidebar:
  label: Connectors
  order: 3
---

Researcher reaches the outside world through a small set of connectors. Some run as MCP servers, some are plain keyless REST APIs, and a couple are documentation-only stubs that exist so a skill knows how to fall back gracefully. This page is the map of what talks to what.

## Connector table

| Service | Access | What it provides |
| --- | --- | --- |
| Scite | MCP | Smart Citation context and supporting / contrasting / mentioning classification for a DOI |
| PubMed / Europe PMC | API | Biomedical and life-sciences literature, abstracts, and MeSH metadata |
| Semantic Scholar | API | CS and general-science papers, citation graphs, and machine-generated TLDR summaries |
| arXiv | API | Preprints across physics, CS, statistics, and quantitative biology |
| Crossref | REST | DOI resolution and metadata validation for citation records |
| OpenAlex | REST | Open scholarly graph, author and venue records, and retraction flags |
| DataCite | REST | DOI metadata for datasets, software, and the DOIs Crossref does not hold |
| Unpaywall | REST | Legal open-access locations for a DOI, feeding full-text retrieval |
| OpenCitations | REST | Open citation links for citation-graph traversal |
| Zotero | MCP / API | Two-way sync with your reference library and collections |
| Google Scholar | Web search | Broad coverage as a last-resort search fallback (documentation-only) |
| Mendeley | API | Reference-library interchange (documentation-only) |

## How the connectors run

### MCP servers

Scite and Zotero run as MCP servers you connect yourself. Since 1.0.0 the plugin also bundles a `.mcp.json` registering the local `researcher-mcp` stdio server, so kernel users get an MCP surface with no extra setup. Once connected, skills call their tools directly rather than scraping the web.

- **Scite** is the primary source of citation context. When it is connected, the citation-context and fact-checking skills use it to tell whether a citing paper actually supports a claim, contrasts with it, or merely mentions it. Without Scite, those skills degrade to abstract-level reasoning, which is less certain and says so.
- **Zotero** keeps your local reference library in sync. The citation-management skill reads and writes collections through it, so a citation you add in Researcher lands in the same library you use everywhere else.
- **researcher-mcp** (bundled since 1.0.0) is the thin stable-core MCP server: five tools (`search_papers`, `get_paper`, `verify_citations`, `export_bibliography`, `download_oa`) that re-export the evidence kernel, so any MCP client can query the eight keyless scholarly sources below without juggling eight endpoints by hand. Its outputs inherit offline mode and the output sanitizer.

### Keyless, free-first APIs

All eight kernel sources (OpenAlex, Crossref, DataCite, arXiv, Semantic Scholar, PubMed / Europe PMC, Unpaywall, and OpenCitations) are keyless and free-first. They need no account, no token, and no billing, so Researcher reaches for them before anything that requires credentials. Crossref and OpenAlex do most of the DOI resolution and metadata validation, with DataCite covering the dataset, software, and preprint DOIs Crossref does not hold; OpenAlex additionally carries retraction flags, which the fact-checking skill uses to catch a source that has been pulled out from under a claim. Unpaywall resolves legal open-access copies and OpenCitations supplies the citation graph. Being polite about rate limits (a contact email in the request) is encouraged but not required.

### Documentation-only connectors

Google Scholar and Mendeley are documentation-only. There is no stable, sanctioned API for either, so Researcher does not pretend to have one.

- **Google Scholar** has no official API and actively discourages automated access. Skills fall back to ordinary web search when broad coverage matters and no structured source has the paper.
- **Mendeley** is documented for users who live in that ecosystem, but the workflow is manual export (BibTeX or RIS) that you import through the citation-management skill rather than a live sync.

If either of these ever grows a usable API, the fallback path is already in place to be swapped for it.

## External reviewer models (documented, not yet implemented)

The peer-review skill documents an integration point for external reviewer models (OpenAI, Google Gemini, and Ollama) that would sit alongside its Claude-based personas. The skill specifies the environment variables and the intended behavior, but no dispatch code exists yet: setting those variables today has no effect.

What the plugin actually ships is the Claude-only multi-persona review panel, and that is what `/researcher:review-paper` runs. When the external dispatch is built, the documented env vars are the interface it will pick up, and reviewers will stay off unless you set them. Until then, treat this section as a specification, not a capability.
