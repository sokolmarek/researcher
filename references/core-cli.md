# researcher-core CLI Reference

Loaded on demand by any skill that needs deterministic retrieval or citation verification.
Skills link here instead of inlining API detail, so SKILL.md files stay under the 500-line cap.

`researcher-core` is the evidence kernel: a small Python package (`core/`) that does the
reproducible work a language model should not be asked to do. Multi-source literature
retrieval, deduplication, per-axis citation verification, publication-status checks,
open-access full-text extraction, passage retrieval, and an append-only provenance ledger.
Skills never import it. They shell out to it and read its JSON.

## The standard invocation

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<query>" --json
```

This is the form every skill uses. It needs no install step: `uv` provisions the environment
from `core/pyproject.toml` on first run.

Two fallbacks, in case `uv` is absent or `CLAUDE_PLUGIN_ROOT` is not set (a Codex install, a
bare checkout):

```
pip install -e core/                 # then: researcher-core search "<query>" --json
python -m researcher_core search "<query>" --json    # from a checkout, with core/ on sys.path
```

**The kernel is optional.** If it is not installed, say so and fall back to whatever the skill
does without it. The plugin never hard-fails for want of core.

## Every command

All commands accept `--json` and `--record`. Default output is a compact human table.

| Command | Does |
|---|---|
| `search "<query>" [--sources a,b,c] [--limit N] [--since YEAR]` | fan out, dedupe, rank; returns CSL-JSON records |
| `get <doi-or-arxiv-or-openalex-id> [--sources a,b]` | one normalized record |
| `verify-bib <library.bib> [--sources a,b,c]` | per entry: axis (a) identity with per-source outcomes, axis (b) status, axis (d) accessibility |
| `verify-ref "<doi-or-title>"` | the same report for one reference |
| `status <doi-or-bib>` | axis (b) sweep: current / corrected / retracted / expression-of-concern |
| `citations <id> [--depth 1] [--limit N]` | forward citations (works that cite this one) |
| `references <id> [--depth 1] [--limit N]` | backward references (works this one cites) |
| `oa-pdf <doi>` | OA location cascade: Unpaywall, then arXiv, then PMC |
| `fulltext <doi-or-url> [--sections]` | resolve an OA copy, extract text, split into sections |
| `passages index <doi-or-url> [--db PATH]` | extract and index a document with stable passage IDs |
| `passages search "<query>" [--doc <id>] [--limit N] [--db PATH]` | BM25-ranked passages with IDs, offsets, page coordinates |
| `faithfulness "<claim>" --doc <id> [--db PATH]` | axis (c) verdict, anchored on passage IDs |
| `snapshot record\|replay\|diff` | capture live responses, replay a stored request set, report drift |
| `provenance append <event-json> \| prisma \| export` | append an event, derive PRISMA counts, export JSONL |
| `compile [--manuscript DIR] [--lineage PATH] [--recheck-status] [--ts TS]` | walk the lineage graph and gate the manuscript; exits 1 on a failing gate, appends a `gate` event when given `--ts` |
| `passport --format ro-crate\|prov-jsonld [--manuscript DIR] [--out PATH]` | export the evidence lineage as an RO-Crate 1.1 or W3C PROV-JSON-LD research passport |

### Global flags

| Flag | Meaning |
|---|---|
| `--json` | machine output, validated against `core/schemas/*.json` in the test suite |
| `--record` | make live calls and capture every response as a content-addressed snapshot |
| `--version` | core, parser, and protocol versions |

### Sources

`openalex`, `crossref`, `datacite`, `semantic_scholar`, `arxiv`, `pubmed`, `unpaywall`,
`opencitations`. Pass them comma-separated to `--sources`. An unknown name is an argument
error (exit 2), never a silent skip.

| Command | Default sources |
|---|---|
| `search`, `get` | `openalex,crossref,arxiv` |
| `verify-bib`, `verify-ref` | `openalex,crossref,datacite` |
| `status` | `crossref,openalex` |
| `citations`, `references` | `openalex,semantic_scholar,opencitations` |

OpenAlex and Crossref alone satisfy the two-confirmation identity gate. DataCite is in the
verification default because it holds the DOIs Crossref does not mint (datasets, software,
arXiv preprints), so a preprint citation can reach two confirmations instead of falling to
`inconclusive` for want of an index that holds it.

## The four verification axes

The axes are independent and are reported side by side. A reference can be perfectly
`verified` on identity and still be `retracted` on status. Never fold one into the other.

| Axis | Command | Verdicts |
|---|---|---|
| (a) reference identity | `verify-bib`, `verify-ref` | `verified`, `mismatch`, `unresolvable`, `inconclusive` |
| (b) publication status | `status` (also carried by `verify-*`) | `current`, `corrected`, `retracted`, `expression-of-concern` |
| (c) claim faithfulness | `faithfulness` | `supported`, `partial`, `contradicted`, `insufficient-passage` |
| (d) accessibility | `oa-pdf`, `fulltext` (also carried by `verify-*`) | `full-text`, `abstract-only`, `unavailable` |

**Only `unresolvable` and `mismatch` are refusal-grade.** They are the only two verdicts that
license telling a researcher a citation looks fabricated or wrong. `inconclusive` is NEVER
refusal-grade: it means a source was rate-limited, or only one index holds the paper, so a
clean negative could not be asserted. Acting on it would accuse an honest researcher of
fabricating a real citation, which is the worst failure this system can have. The JSON carries
`refusal_grade` per entry so a skill never has to re-derive this rule.

An `insufficient-passage` on axis (c) is an abstention, not a pass. It is emitted with
`clean: false` and no passage anchors, and it must be surfaced, never dropped.

## The compile gate

`researcher compile` walks the lineage graph (`researcher_core.lineage`: claim nodes hash-anchored
to a manuscript span, evidence edges tying each claim to an external source passage or an internal
experiment run, and experiment manifests) and reports one diagnostic per defect class. It exits `1`
on a failing gate and `0` on a clean one. Given `--ts`, it appends a `gate` event to the provenance
ledger carrying the pass/fail verdict and the diagnostic codes; the timestamp is caller-supplied
(D19), so replays stay deterministic. `--recheck-status` re-runs the axis (b) status sweep over
every cited source at compile time; `--lineage` points at the graph file, and `--manuscript` at the
manuscript directory.

| Code | Defect |
|---|---|
| `C001` orphan claim | a claim node with no evidence edge |
| `C002` altered number | a generated artifact's content hash no longer matches its manifest |
| `C003` stale evidence | a source snapshot was superseded, or the status axis flipped, since the edge was created |
| `C004` qualifier mismatch | the claim's population/intervention/outcome does not match the cited source's |
| `C005` retraction | a cited source is now retracted or under an expression of concern |
| `C006` artifact-code drift | a run's commit is not an ancestor of HEAD, or its worktree was dirty at run time |

Only C001 through C006 on clean evidence are refusal-grade. A source error during the compile-time
status re-check yields an `inconclusive` line item, NEVER a C003 or C005 (D9), and a claim with only
abstract-level evidence is `insufficient-passage`, an open item, never a refusal (D11). Neither ever
fails the gate. Compile is replayable per D15: the same worktree bytes, snapshots, configuration,
and parser version produce a byte-identical `--json` report.

`researcher passport --format ro-crate|prov-jsonld` re-expresses the same graph as a research
passport, a pure function of the lineage. `ro-crate` emits an RO-Crate 1.1 metadata descriptor (a
descriptor that conformsTo the profile plus a root dataset, with files, claims, and sources as
entities, runs as CreateActions, and artifacts); `prov-jsonld` emits W3C PROV-JSON-LD (claims and
sources as Entities, runs and the compile gate as Activities, edges as Derivation and Generation
relations). `--out` writes the passport to a path.

## JSON output shapes

Every `--json` output validates against a schema in `core/schemas/`, checked in
`core/tests/test_cli.py` with `jsonschema` (a dev dependency; the runtime never imports it).

| Command | Shape | Schema |
|---|---|---|
| `search` | `{query, records[], warnings[], sources[], dedup_decisions[], counts{retrieved, deduplicated, duplicates_removed}}` | each `records[]` element: `record.schema.json` |
| `get` | `{identifier, found, record, sources[], warnings[]}` | `record`: `record.schema.json` |
| `citations`, `references` | `{seeds[], direction, depth, nodes[], edges[], warnings[], sources[], counts{}}` | each `nodes[]` element: `record.schema.json` |
| `verify-bib`, `verify-ref` | `{schema_version, protocol_version, versions{}, input{}, thresholds{}, sources_queried[], entries[], summary{}}` | `verification-report.schema.json` |
| `status` | `{schema_version, protocol_version, versions{}, input{}, entries[], summary{}}` | `status-report.schema.json` |
| `oa-pdf` | `{doi, verdict, known, location{url, content_type, source, version, license, host_type, is_oa}, sources_tried[], errors[]}` | (no schema; a plain object) |
| `fulltext` | `{doc_id, doi, url, content_type, accessibility, parser_version, doc_hash, abstract, char_count, section_count, segment_count, sections[]}`, each section `{section, text, char_offsets, page_coords, ordinal}` | (no schema; a plain object) |
| `passages index` | `{document{}, passages[]}` | each `passages[]` element: `passage.schema.json` |
| `passages search` | `{query, doc_id, count, passages[]}` | each `passages[]` element: `passage.schema.json` |
| `faithfulness` | `{schema_version, protocol_version, versions{}, method, document{}, claims[], summary{coverage, abstention_rate, verdicts{}}}` | `faithfulness-report.schema.json` |
| `snapshot replay` | one snapshot object, or an array of them | `snapshot.schema.json` |
| `snapshot diff` | `{compared, changed, diffs[]}` | (no schema; a plain object) |
| `provenance append` | one event object | `provenance-event.schema.json` |
| `provenance prisma` | `{run_id, identified, identified_by_source{}, duplicates_removed, deduplicated, screened, included, excluded, event_counts{}}` | (no schema; counts are derived, never stored) |
| `provenance export` | JSONL by default, one event per line; a JSON array with `--json` | each event: `provenance-event.schema.json` |

Records are CSL-JSON. Kernel metadata (which sources produced the record, citation counts,
the OA URL, the rank score, and the ISSN and keyword lists, which upstream CSL types as
scalars) rides under the standard `custom` extension object, so the top level stays valid
CSL-JSON.

Per entry, a `verify-*` report carries `verdict`, `refusal_grade`, `reason`, the full
`source_outcomes[]` (each `confirmed`, `negative`, or `source_error`), a `tally`, the
`best_match` record, and the `status` and `accessibility` blocks. A `status.checked: false`
means axis (b) was never answered; an unchecked status is an absence of evidence, not evidence
of currency, and must not be read as a clean bill of health.

## Environment variables

Keyless by default. The mail variables put requests in each API's polite pool, which buys
higher rate limits and costs nothing. None of them changes a snapshot key, so a colleague with
a different address replays the same snapshots byte for byte.

| Variable | Purpose |
|---|---|
| `OPENALEX_MAILTO` | polite-pool contact for OpenAlex |
| `CROSSREF_MAILTO` | polite-pool contact for Crossref |
| `UNPAYWALL_EMAIL` | contact address the Unpaywall API asks for |
| `S2_API_KEY` | optional; raises Semantic Scholar rate limits |
| `NCBI_API_KEY` | optional; raises PubMed E-utilities rate limits |

Kernel behavior:

| Variable | Purpose |
|---|---|
| `RESEARCHER_CORE_SNAPSHOT_MODE` | `live` (default), `record`, or `replay` |
| `RESEARCHER_CORE_SNAPSHOT_DIR` | override the snapshot store root |
| `RESEARCHER_CORE_CACHE_DIR` | override the response-cache directory |
| `RESEARCHER_CORE_CACHE_TTL` | override the default cache TTL, in seconds |
| `RESEARCHER_CORE_NO_CACHE` | set to `1` to bypass the response cache |

## Extras

The base install pulls exactly three runtime dependencies: `httpx`, `rapidfuzz`,
`platformdirs`. Everything else is optional.

| Extra | Pulls | Needed for |
|---|---|---|
| `fulltext` | pymupdf, selectolax | extracting text from an OA **PDF** |
| `rerank` | rank-bm25 | optional lexical reranking over the BM25 passage index |
| `dev` | pytest, jsonschema, ruff, mypy, respx | the test, lint, and type gate |

```
uv sync --project "${CLAUDE_PLUGIN_ROOT}/core" --extra fulltext
pip install -e "core/[fulltext]"
```

`fulltext` and `passages index` work on **HTML** open-access articles with no extra at all.
The extra is required only for PDFs; without it, those two commands exit 1 with an install
pointer rather than a traceback. Embeddings, vector stores, and GROBID are out of scope.

## Determinism, and what it does not cover

Deterministic means replayable given three things: a source snapshot, a configuration, and a
parser version. Identical inputs under those three produce byte-identical `--json` output.
Nothing in the CLI generates a timestamp, which is what makes that true.

Determinism is **never** claimed for live calls. Live indexes change: OpenAlex adds a citation,
a publisher fixes a title, a paper gets retracted. So:

- `--record` makes live calls and writes a content-addressed snapshot of every response.
- `RESEARCHER_CORE_SNAPSHOT_MODE=replay` reads snapshots only. A missing snapshot raises,
  loudly. It never falls back to a live call.
- `snapshot diff` re-runs a stored request and reports field-level drift.

Never present a retrieval result as reproducible without saying which mode produced it.

## Failure modes

| Exit | Means | What a skill should do |
|---|---|---|
| `0` | success | proceed |
| `1` | operational failure | report it to the user; do not retry the same call blindly |
| `2` | invalid arguments, with usage text on stderr | fix the invocation; retrying it unchanged is pointless |

The `1` cases, and what each one really means:

- **A source failed** (timeout, rate limit, 5xx, network). One failing source never fails a
  `search`: it lands in `warnings[]` and every other source still returns records. On a
  `verify-*`, it becomes a `source_error` per-source outcome, which forces `inconclusive` and
  can never produce a refusal-grade `unresolvable`. A downed index is not evidence of
  fabrication.
- **Nothing found.** `get` and `oa-pdf` exit 1 when they resolve nothing. This is a clean
  negative, not an error: the JSON still reports `found: false` or `verdict: unavailable`, with
  an empty `warnings[]`. Read the JSON, do not infer failure from the exit code alone.
- **A missing snapshot** in replay mode. A hole in the fixture set, not an outage. Re-record it.
- **The `[fulltext]` extra is missing** and the resolved document is a PDF. The message names
  the extra; install it or fall back to the abstract.
- **The document is not in the passage index.** Run `passages index <doi>` first.
- **A duplicate provenance event.** The ledger is append-only; nothing is ever overwritten.
- **A failing compile gate.** `researcher compile` exits `1` when the gate fails on a refusal-grade
  diagnostic (C001-C006 on clean evidence). This is a gate verdict, not an operational error: read
  the `--json` report for the codes. `inconclusive` and `insufficient-passage` items never fail it.

## Integrity

Everything the kernel emits is evidence, and evidence is only useful if it is honest about its
own limits. Four rules bind every skill that reads this output, and they come from
`references/integrity-constraints.md`:

1. **Never present an unverified citation as verified.** If `verify-*` says `inconclusive`,
   say `inconclusive`. Do not round it up to `verified` and do not round it down to fabricated.
2. **Never act on `inconclusive` as if it were refusal-grade.** Only `unresolvable` and
   `mismatch` license telling a user a citation looks fabricated or wrong.
3. **Never present an `insufficient-passage` claim as checked.** It is an abstention. It
   carries `clean: false` and no passage anchors, and it must be surfaced to the user.
4. **Surface a retraction.** An entry can be `verified` on identity and `retracted` on status.
   Report both. A retraction is a human checkpoint, not a silent drop.
