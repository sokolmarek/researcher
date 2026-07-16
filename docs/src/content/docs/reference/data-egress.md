---
title: Privacy and data egress
description: Exactly what Researcher sends over the network, per connector, and how offline mode keeps everything local.
sidebar:
  label: Data egress
  order: 6
---

This page is the precise, per-connector companion to the [Privacy policy](/researcher/reference/privacy/):
what leaves your machine, to which host, and when. If you want the short version, it is the next two
paragraphs. If you want to audit every outbound call, the table below names each one.

## The short version

Researcher has no telemetry, no analytics, and no accounts. Nothing reports back to the maintainer,
and nothing can: the plugin is skills plus a local Python core plus local scripts.

By default, skills send **bibliographic metadata** (a DOI, a title, an author name, or a search term)
to public scholarly APIs when you invoke a skill that needs data to do its job. That is the whole of
the outbound traffic. Your **manuscript prose never leaves the machine through core**: core sends only
the identifiers and query strings a skill passes it, never a manuscript file or a section of body
text, and the faithfulness check (axis c) compares your claims against downloaded passages **locally**,
so claim text is not uploaded to grade it. A literature or fact-check search does put its query string
on the wire, and that query can contain terms you drew from the manuscript (a title, keywords, or a
claim phrase used as a search), so treat a search as sending its query, not your document.

## Offline mode: nothing leaves at all

Set `--offline` on a core command, or export `RESEARCHER_OFFLINE=1`, and every network-touching
command answers **exclusively** from the local snapshot store and the response cache. A cache miss
returns a typed `offline-miss` result: it never falls through to a live HTTP call, and no socket is
opened. This reuses the same snapshot layer the deterministic evals replay from, so offline mode is
not a second, half-trusted cache. It is the honest answer "no local record, and I did not go to the
network to get one."

Use it when you are on a plane, on a metered link, or working with material you would rather keep
strictly local: record the snapshots you need once while online (`--record`), then run offline.

## Per-connector egress summary

Every host below is reached over HTTPS. "Manuscript terms?" marks whether the query a skill sends can
carry text you derived from the manuscript (a free-text search can; a DOI-only lookup cannot). No
connector uploads a manuscript file or section prose, and none attaches a cookie, an account, or a
persistent identifier of you. The optional polite-pool email is the only contact string ever sent, and
it is deliberately kept out of the snapshot and cache keys so a recording replays on any machine.

| Connector | Host(s) | What is sent | Manuscript terms? | Connector doc |
| --- | --- | --- | --- | --- |
| OpenAlex | `api.openalex.org` | search query, or DOI / OpenAlex ID / arXiv ID; optional `mailto` | Yes (free-text search) | [openalex.md](https://github.com/sokolmarek/researcher/blob/main/connectors/openalex.md) |
| Crossref | `api.crossref.org` | a DOI, or title / author / year for reference validation; optional `mailto` | Yes (title query) | [crossref.md](https://github.com/sokolmarek/researcher/blob/main/connectors/crossref.md) |
| DataCite | `api.datacite.org` | a DOI, or a free-text search plus resource-type filter; optional `mailto` | Yes (free-text search) | [datacite.md](https://github.com/sokolmarek/researcher/blob/main/connectors/datacite.md) |
| arXiv | `export.arxiv.org`, `arxiv.org` (PDF) | an arXiv ID or a search query; a PDF URL to fetch OA full text | Yes (free-text search) | [arxiv.md](https://github.com/sokolmarek/researcher/blob/main/connectors/arxiv.md) |
| Semantic Scholar | `api.semanticscholar.org` | search query, author name, or paper IDs; optional `S2_API_KEY` header | Yes (free-text search) | [semantic-scholar.md](https://github.com/sokolmarek/researcher/blob/main/connectors/semantic-scholar.md) |
| PubMed | `eutils.ncbi.nlm.nih.gov` | search query or PMIDs; optional `NCBI_API_KEY`, tool and email params | Yes (free-text search) | [pubmed.md](https://github.com/sokolmarek/researcher/blob/main/connectors/pubmed.md) |
| Unpaywall | `api.unpaywall.org`, then the resolved OA host | a DOI plus a required contact `email` | No (DOI only) | [unpaywall.md](https://github.com/sokolmarek/researcher/blob/main/connectors/unpaywall.md) |
| OpenCitations | `api.opencitations.net` | a DOI; optional access token and `mailto` | No (DOI only) | [opencitations.md](https://github.com/sokolmarek/researcher/blob/main/connectors/opencitations.md) |
| Scite | none from core | user-connected MCP only (see below) | n/a | [scite.md](https://github.com/sokolmarek/researcher/blob/main/connectors/scite.md) |
| Zotero | none from core | user-connected MCP only (see below) | n/a | [zotero.md](https://github.com/sokolmarek/researcher/blob/main/connectors/zotero.md) |
| Google Scholar | none from core | assistant web search only (see below) | n/a | [google-scholar.md](https://github.com/sokolmarek/researcher/blob/main/connectors/google-scholar.md) |
| Mendeley | none from core | none (manual export only) | n/a | [mendeley.md](https://github.com/sokolmarek/researcher/blob/main/connectors/mendeley.md) |

Each connector doc carries a full **Data egress** section with the exact identifiers, the remote
retention note where the provider states one, and, for the eight kernel connectors, a **Terms of use**
note. The eight kernel connectors (OpenAlex, Crossref, DataCite, arXiv, Semantic Scholar, PubMed,
Unpaywall, OpenCitations) are the only ones core calls directly.

## Connectors you connect yourself

Four connectors are not called by core, so nothing leaves through the plugin for them:

- **Scite** and **Zotero** are Model Context Protocol servers **you** connect with your own account.
  When connected, what you send them (DOIs and citation queries for Scite, library items for Zotero)
  and how long they keep it is governed by **their** terms and your subscription, not by this plugin.
  Core never calls either one.
- **Google Scholar** has no sanctioned API. When Scholar coverage is wanted, a skill uses the AI
  assistant's built-in web search with a `site:scholar.google.com` query, which travels through the
  assistant's web-search provider and Google, not through core. That query can carry manuscript-derived
  search terms, so it is governed by the assistant provider's and Google's terms.
- **Mendeley** has no live integration at all. The workflow is a manual BibTeX export you import
  yourself, so core makes no Mendeley network call.

## Related

- The formal [Privacy policy](/researcher/reference/privacy/): what the plugin collects (nothing) and
  what runs locally.
- [Licensing and retention](/researcher/reference/licensing/): how long fetched content is cached, why cached
  full text is never redistributed, and each source's terms of use.
</content>
</invoke>
