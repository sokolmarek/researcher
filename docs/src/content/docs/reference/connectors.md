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
| Zotero | MCP / API | Two-way sync with your reference library and collections |
| Google Scholar | Web search | Broad coverage as a last-resort search fallback (documentation-only) |
| Mendeley | API | Reference-library interchange (documentation-only) |

## How the connectors run

### MCP servers

Scite, Zotero, and paper-search run as MCP servers. Once connected, skills call their tools directly rather than scraping the web.

- **Scite** is the primary source of citation context. When it is connected, the citation-context and fact-checking skills use it to tell whether a citing paper actually supports a claim, contrasts with it, or merely mentions it. Without Scite, those skills degrade to abstract-level reasoning, which is less certain and says so.
- **Zotero** keeps your local reference library in sync. The citation-management skill reads and writes collections through it, so a citation you add in Researcher lands in the same library you use everywhere else.
- **Paper-search** wraps the keyless scholarly APIs (see below) behind a single MCP surface so literature-search, sota-finder, and research-gaps can query them without juggling nine endpoints by hand.

### Keyless, free-first APIs

OpenAlex, Crossref, and arXiv are keyless and free-first. They need no account, no token, and no billing, so Researcher reaches for them before anything that requires credentials. Crossref and OpenAlex do most of the DOI resolution and metadata validation; OpenAlex additionally carries retraction flags, which the fact-checking skill uses to catch a source that has been pulled out from under a claim. PubMed / Europe PMC and Semantic Scholar are also free to query and cover biomedical and CS literature respectively. Being polite about rate limits (a contact email in the request) is encouraged but not required.

### Documentation-only connectors

Google Scholar and Mendeley are documentation-only. There is no stable, sanctioned API for either, so Researcher does not pretend to have one.

- **Google Scholar** has no official API and actively discourages automated access. Skills fall back to ordinary web search when broad coverage matters and no structured source has the paper.
- **Mendeley** is documented for users who live in that ecosystem, but the workflow is manual export (BibTeX or RIS) that you import through the citation-management skill rather than a live sync.

If either of these ever grows a usable API, the fallback path is already in place to be swapped for it.

## Optional external reviewer models

For multi-model peer review, Researcher can optionally call external reviewer models in addition to its own Claude-based personas. These are configured by environment variable and stay off unless you set them:

- **OpenAI** (set the relevant API key env var)
- **Google Gemini** (set the relevant API key env var)
- **Ollama** (point the env var at your local server for a fully offline reviewer)

These add extra perspectives during peer review. They are strictly optional: with none configured, the peer-review skill runs its default Claude-only multi-persona panel. See [Commands](/researcher/reference/commands/) for how `/review-paper` picks up these settings.
