# Unpaywall Connector

**What it provides**
Open-access location resolution for a DOI: whether a legal free copy exists, where it is, and under what license and version. This is the accessibility axis of citation verification, answering `full-text`, `abstract-only`, or `unavailable` for each reference. Unpaywall is not a search index and holds no citation graph, so this connector does DOI lookup only.

**Mechanism**
Direct public REST API (api.unpaywall.org/v2), called by `researcher_core.connectors.unpaywall`. No MCP server. No API key exists and none is ever required; the API asks only for a contact email so it can track usage.

**Install and environment variables**
Nothing to install. Set `UNPAYWALL_EMAIL` to your address so requests carry a valid contact; the connector falls back to a documented default when it is unset, so it works out of the box. The email is a politeness parameter only: it never changes the response, and it is deliberately excluded from the snapshot and cache key so recorded snapshots replay on any machine.

**Used by**
fact-checking, citation-management, literature-search (OA cascade: Unpaywall, then arXiv, then PMC)

**Fallback when absent**
If the API is unreachable, the lookup raises a source error rather than a negative result, and the accessibility verdict becomes inconclusive rather than `unavailable`. A downed Unpaywall never counts as evidence that a citation is fabricated. Skills fall back to the publisher landing page and flag the reference as accessibility-unknown.

**Result semantics**

| Outcome | Meaning | Return |
| --- | --- | --- |
| `full-text` | DOI known, an OA location exists | `OALocation` (url, content type, host type, license, version) |
| `abstract-only` | DOI known, no OA copy | `None` from `get_oa_pdf`, `known=True` from `get_accessibility` |
| `unavailable` | DOI unknown to Unpaywall (HTTP 404) | `None`, a clean negative |
| source error | timeout, 429, 5xx, unparseable body | raises `SourceError` (never a negative) |

`get_oa_pdf` returns `None` for both `abstract-only` and `unavailable`, so call `get_accessibility` when the difference matters. Unpaywall's coverage is Crossref-derived, so a clean negative means "not in Crossref", not "does not exist": DataCite DOIs are legitimately absent, and the verdict layer weighs Unpaywall as one source among several.

**Data egress**
Hosts: `api.unpaywall.org` (v2, HTTPS), and then the resolved OA host (a publisher or repository) when full text is fetched. Sent: a DOI, plus a required contact `email` from `UNPAYWALL_EMAIL`; when that is unset the connector falls back to a documented default contact address so it works out of the box. Unpaywall is a DOI-lookup service only, so the query cannot carry manuscript prose. The email never changes the response and is excluded from the snapshot and cache key. Remote retention: governed by the OurResearch / Unpaywall privacy policy (linked below).

**Terms of use**
The Unpaywall data set is CC0, and the API is free and expects a valid contact email (the polite-pool expectation). The OA locations it points to are hosted elsewhere and keep their own licenses, so a fetched copy is for local reading and verification, not redistribution (see the licensing and retention page). API: https://unpaywall.org/products/api . Privacy: https://ourresearch.org/privacy . Verified as of 2026-07-14; re-verify at release.
