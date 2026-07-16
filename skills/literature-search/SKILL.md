---
name: literature-search
description: "Search academic literature across multiple databases. Triggers when user says: 'search literature', 'find papers', 'literature review', 'what does research say about', 'find related work', 'search PubMed', 'search arXiv', 'find citations', 'related papers', 'prior work on', 'explore this topic in the literature', 'give me the key papers on this topic'. Searches PubMed, Semantic Scholar, arXiv, Scite, Google Scholar, and CrossRef. Use this skill whenever the user needs to find, discover, or explore academic papers on any topic."
---

# Literature Search

Multi-source academic literature search with deduplication and ranking.

## CRITICAL INTEGRITY RULE
**NEVER fabricate or hallucinate citations.** Every result must come from an actual search query to a real source. If a search returns no results, say so. Do not invent papers, authors, DOIs, or abstracts under any circumstances.

## Workflow

1. **Parse research question** → extract key concepts, synonyms, MeSH terms
2. **Construct queries** → adapt syntax per source (Boolean for PubMed, keywords for Semantic Scholar)
3. **Dispatch the fan-out** through the `core/` kernel (see Deterministic backend below), which
   queries the sources, isolates per-source errors, dedupes, and ranks in one call. When the
   Scite MCP server is connected, it enriches the top results with citation context.
4. **Read dedup and ranking from the kernel**: consume `dedup_decisions[]` and the ranked
   `records[]` from its JSON rather than re-implementing either.
5. **Present** results in structured format, naming which tier produced them (kernel, MCP, or web
   search) and which sources were not reached.

## Deterministic backend

Retrieval, deduplication, and ranking route through the `core/` evidence kernel, not hand-built
API calls. One fan-out call queries the sources, isolates per-source errors, dedupes, and ranks,
returning CSL-JSON records with kernel metadata (source provenance, citation count, OA URL, rank
score) under the `custom` extension.

### Fan-out search

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<query>" --sources openalex,crossref,arxiv --json
```

Consume from the JSON:
- `records[]`: the deduped, ranked results, already in CSL-JSON.
- `counts{retrieved, deduplicated, duplicates_removed}`: the tallies to report to the user.
- `dedup_decisions[]`: which records collapsed into which, and why.
- `warnings[]`: a source that timed out or was rate-limited lands here. One failing source never
  fails the search; name the sources that were not reached and never read a downed index as
  "no results".
- `sources[]`: which sources actually answered.

Add `--limit N` to cap results and `--since YEAR` to bound recency. Full command, flag, and JSON
reference: `references/core-cli.md`.

### Degradation path (never hard-fail, D3)

The kernel is optional; state which tier produced the results:
1. `core/` present: deterministic fan-out as above.
2. No `uv` or `core/`: fall back to connected MCP servers (Scite for citation context, Zotero for
   the user's library), and say the kernel was unavailable.
3. Neither: web search, clearly labeled as non-deterministic and unverified.

### Verdicts, never a boolean (D9)

When a result is checked for identity (a known-item lookup, or a paper about to be added to the
bibliography), consume the FOUR-STATE identity verdict from `verify-ref`
(`verified` / `mismatch` / `unresolvable` / `inconclusive`), never a true/false. The kernel
carries `refusal_grade` per entry so this rule is not re-derived:
- Refusal-grade (withhold, or flag as fabricated or wrong): `unresolvable`, `mismatch`, plus
  `retracted` on status (axis b) and `contradicted` on faithfulness (axis c).
- NEVER refusal-grade (surface as an open item): `inconclusive` (a source errored, or only one
  index holds the paper) and `insufficient-passage` (no OA full text to anchor a claim). Reading
  either as fabrication accuses an honest author of inventing a real citation, the worst failure
  this system can make.

### The layer every verdict names

Abstracts and "what does the research say" snippets are the ABSTRACT layer unless OA full text
was retrieved and indexed as M2 passages. Faithfulness (axis c) anchors on those passages; when
full text is unavailable the verdict is `insufficient-passage`, never clean or faithful, and each
verdict names its layer (abstract vs full-text). Axis (c) is a LEXICAL baseline (BM25 plus
token-overlap and polarity heuristics) that can miss overstatements, so a `supported` read off an
abstract is weak evidence, not a fact-check.

## Result Format

For each paper found:
```
[1] Title of the Paper
    Authors: First A., Second B., Third C.
    Year: 2024 | Journal: Nature Machine Intelligence
    Citations: 142 | DOI: 10.1234/example
    Abstract: First 2-3 sentences of abstract...
    Source: Semantic Scholar
    Scite Tallies: 89 supporting | 12 contrasting | 41 mentioning  (when Scite available)
    Identity: verified (2+ sources) | Layer: abstract  (when checked via core)
    [Add to bibliography]
```

## Search Modes

### Standard Search
Default mode. Searches all available sources, returns top 10-20 results.

### Systematic Review (PRISMA)
Triggered by: "systematic review", "PRISMA", "comprehensive search"
- Runs the fan-out `search` per protocol query. In systematic mode the kernel feeds the
  append-only provenance ledger: a `retrieval` event per source query, a `record_lineage` event
  per retained record, and a `dedup_decision` event per collapse (the `dedup_decisions[]` the
  search output carries).
- Reports PRISMA counts DERIVED from those events, never a stored total:

  ```
  uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core provenance prisma --json
  ```

  Read `identified`, `identified_by_source{}`, `duplicates_removed`, `deduplicated`, `screened`,
  `included`, and `excluded` straight from the derived object; the PRISMA flow diagram is built
  from these counts. Do not recompute, store, or cache a total.
- Documents the search strategy (databases, queries, date ranges) and exports the search log for
  reproducibility.

### Citation Chasing
Triggered by: "papers that cite this", "references of this paper"
- Forward citation search (who cites this paper)
- Backward reference search (what does this paper cite)
- Uses Semantic Scholar citation graph

## Sources

The kernel owns retrieval, so results stay deduped, ranked, and snapshot-reproducible; do not
hand-build API calls here. The default fan-out covers OpenAlex, Crossref, and arXiv; add others
with `--sources` (`semantic_scholar`, `pubmed`, `datacite`, `unpaywall`, `opencitations`). An
unknown source name is an argument error, never a silent skip. Per-source mechanics, env vars,
and fallbacks live in `references/core-cli.md` and `connectors/`.

## Deep Scite Integration

> **When the Scite MCP server is connected, this skill gains citation context superpowers.**

When the Scite MCP connector is available, it enriches the kernel's top results with citation context (and serves as a degradation tier when the kernel is unavailable). The following capabilities activate:

### Scite enrichment of top results
- After the kernel fan-out returns ranked `records[]`, enrich the TOP results with Scite: pull
  citation context and tallies for the highest-ranked papers.
- Scite is a citation-context layer over the kernel's results, not a replacement for the
  deterministic fan-out; when the kernel is unavailable it also serves as a degradation tier.
- Prefer Scite metadata when reconciling a paper's citation context, never when deciding identity
  (that stays the kernel's four-state verdict).

### Citation Tallies
For every paper found (from any source), retrieve Scite citation tallies when available:
- **Supporting citations**: how many papers cite this work in a supporting context
- **Contrasting citations**: how many papers cite this work to disagree or present conflicting findings
- **Mentioning citations**: neutral mentions without supporting or contrasting stance
- Use tallies as an additional ranking signal: papers with high supporting counts and low contrasting counts rank higher for established findings; papers with high contrasting counts are flagged as controversial

### Smart Citation Context
For each result, retrieve Scite smart citation snippets showing HOW the paper is being cited by others:
- Display 2-3 representative citation statements (actual sentences from citing papers)
- Label each statement as supporting, contrasting, or mentioning
- This gives the user immediate insight into a paper's reception and standing in the field

### Citation Landscape Analysis
Triggered by: "citation landscape", "citation network", "how is this paper cited", "map citations"

For a given paper or topic, map the citation network:
1. Start from a seed paper (by DOI or title) or a topic query
2. Retrieve all citing papers via Scite with their citation contexts
3. Classify relationships: which papers support each other vs contradict
4. Identify citation clusters: groups of papers that mutually support the same thesis
5. Identify controversies: pairs or groups of papers that contradict each other
6. Output a structured map:
   - Core papers (most cited within the network)
   - Supporting chains (A supports B, B supports C)
   - Contradiction pairs (A contradicts B)
   - Isolated papers (cited but not well-connected)
7. Suggest which "side" of a controversy has stronger citation support

This analysis helps authors position their work accurately within the existing discourse and avoid misrepresenting the state of consensus.

## Auto-Add to Bibliography

When user selects papers, generate BibTeX entries and append to `manuscript/references/library.bib`. Validate each entry has:
- Unique citation key (format: `authorYear` or `authorYearKeyword`)
- DOI (if available)
- Complete metadata (title, author, year, journal/booktitle)

Before appending, run `verify-ref` on each entry and read its four-state identity verdict:
withhold only refusal-grade entries (`unresolvable`, `mismatch`, `retracted`), and surface
`inconclusive` or `insufficient-passage` as open items rather than dropping a real citation.

## References

For advanced search strategies, read `references/search-strategies.md`. For the full core CLI
(every command, flag, JSON shape, and the four verification axes), read `references/core-cli.md`.

## Integrity constraints

1. Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it; never invent a DOI, author list, venue, or year.
2. Never invent data: only user-provided or actually computed numbers may appear as results. Anything illustrative must be labeled "(synthetic, for demonstration)".
3. Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).

Canonical copy: `references/integrity-constraints.md`.
