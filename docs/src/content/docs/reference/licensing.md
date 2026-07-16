---
title: Licensing and retention
description: How long Researcher caches fetched content, why cached full text is never redistributed, and each source's terms of use.
sidebar:
  label: Licensing and retention
  order: 7
---

Researcher fetches metadata and, where a legal open-access copy exists, full text. This page states how
long it keeps that content, where it keeps it, and under whose terms. The short answer: fetched content
is cached locally to stay polite to the source APIs, cached full text is **never** redistributed, and
every source's reuse terms are summarized below with a link and a verification date.

## Two stores, never crossed

Researcher keeps two entirely separate local stores, and it is worth knowing which is which:

- **The response cache** lives in your platformdirs user cache directory (Windows-safe per the D5
  path convention). It exists to keep the kernel polite to public APIs during ordinary live use, so a
  repeated lookup does not hammer a source. It carries per-content-class time-to-live limits (below).
- **The snapshot store** is content-addressed by the SHA-256 of each raw response body. It is what the
  deterministic evals replay from, and its records are kept **indefinitely** because they gate those
  evals: editing or expiring one would change its hash and break the determinism the eval suite rests
  on. Eval snapshots are committed to the repository; a user's own `--record` snapshots live in the
  user cache, never in the repo.

Only the response cache expires content. The snapshot store does not.

## Retention policy

The response cache treats content classes differently, because a licensed OA PDF and a one-line DOI
resolution do not deserve the same shelf life:

| Content class | Retention | Store |
| --- | --- | --- |
| OA full text and extracted PDFs | 90 days | user cache |
| Unpaywall OA-location answers | 30 days | user cache |
| Bibliographic metadata responses | 7-day default, configurable per source | user cache |
| Eval metadata snapshots | indefinite (they gate the deterministic evals) | in-repo snapshot store |

**How it is enforced.** The response cache (`core/researcher_core/cache.py`) evicts lazily on read: an
expired row is deleted the moment it is looked up, so a stale entry never satisfies a request, and
`purge_expired()` sweeps the remainder. Time-to-live is configurable, a conservative default (7 days)
plus per-source overrides and a per-call override, and `RESEARCHER_CORE_CACHE_TTL` changes the default.
The 90-day and 30-day figures above are the retention ceilings the policy sets for full text and for
Unpaywall locations; they are applied through the same per-source time-to-live mechanism. Setting
`RESEARCHER_CORE_NO_CACHE=1` turns the cache off entirely, so every read is a miss and nothing is
stored.

## No redistribution

Cached full text is for local reading and verification, and it stays that way:

- It lives only in the platformdirs user cache. It is **never committed** to the repository.
- It is **never copied into `manuscript/`**. A manuscript folder carries your writing and your
  bibliography, not fetched article bodies.
- It is **never exported into the research passport**. The passport carries content **hashes** and
  stable **passage IDs** (per the D21 passage-ID scheme), not article text, so a passport can prove
  which passage supported a claim without shipping a copy of the passage.

The reason is simple: an OA license typically grants **you** the right to read and reuse a copy, not
the right to redistribute the publisher's or repository's file inside your own artifacts. Keeping the
bytes in your local cache and exporting only hashes and IDs respects that line.

## Terms of use, per source

Each connector doc carries the authoritative **Terms of use** note; this is the summary. Every entry
is **verified as of 2026-07-14** and should be re-verified at release time, because a provider can
change its terms under us.

| Source | Reuse terms (summary) | Connector note |
| --- | --- | --- |
| OpenAlex | Data released under CC0 (public domain); free, keyless, polite pool asks only for a contact email | [openalex.md](https://github.com/sokolmarek/researcher/blob/main/connectors/openalex.md) |
| Crossref | Metadata is open and, for the great majority of records, free of reuse restrictions (CC0-facing); free, keyless | [crossref.md](https://github.com/sokolmarek/researcher/blob/main/connectors/crossref.md) |
| DataCite | Metadata published under CC0 1.0; read access is free and keyless | [datacite.md](https://github.com/sokolmarek/researcher/blob/main/connectors/datacite.md) |
| arXiv | Metadata reusable via the API Terms of Use (attribution, rate limits); full-text PDFs keep each paper's own license, so a download is for local use, not redistribution | [arxiv.md](https://github.com/sokolmarek/researcher/blob/main/connectors/arxiv.md) |
| Semantic Scholar | Academic Graph under ODC-BY 1.0; API has rate and reuse terms; an optional API key identifies your usage | [semantic-scholar.md](https://github.com/sokolmarek/researcher/blob/main/connectors/semantic-scholar.md) |
| PubMed / PMC | E-utilities usage policy (rate limits, register a key or tool/email for volume); the PMC Open Access Subset carries per-article licenses, and only OA-subset articles are retrieved as full text | [pubmed.md](https://github.com/sokolmarek/researcher/blob/main/connectors/pubmed.md) |
| Unpaywall | Data set is CC0; the API expects a valid contact email (polite pool); the OA locations it points to keep their own licenses | [unpaywall.md](https://github.com/sokolmarek/researcher/blob/main/connectors/unpaywall.md) |
| OpenCitations | Citation data released under CC0; free, an optional access token raises rate headroom | [opencitations.md](https://github.com/sokolmarek/researcher/blob/main/connectors/opencitations.md) |

The four connectors core does not call (Scite, Zotero, Google Scholar, Mendeley) are user-connected or
documentation-only; their terms are the provider's, applied to what you send them yourself. See the
[data-egress page](/researcher/reference/data-egress/) for who reaches which host.

## Re-verify at release

The reuse terms above are a moving target. Treat the 2026-07-14 date as a freshness stamp, not a
guarantee: before each release, re-open each connector note's linked terms and confirm the summary
still holds. This is the same discipline the examples follow for volatile facts (the D8 "verified as
of" convention).
</content>
