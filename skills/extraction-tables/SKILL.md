---
name: extraction-tables
description: "Elicit-style structured data extraction into an evidence table. Triggers when the user says: 'extraction table', 'extract data from these papers', 'structured extraction', 'data extraction', 'build an evidence table', 'pull the numbers from these studies', 'extraction sheet', 'characteristics table', 'extract effect sizes', 'extract sample sizes', 'Elicit-style table'. The user defines the columns (population, method, dataset, metric, effect size, variance, and so on) and the skill fills one row per paper, anchoring every populated cell against a stable full-text passage when an open-access copy exists and the abstract otherwise. Use this once studies are in hand (typically the included set of a systematic review) and you need their values side by side; finding the papers is literature-search, checking one claim against sources is fact-checking, and the end-to-end review workflow is systematic-review."
---

# Extraction Tables

Structured, anchored data extraction: the user defines columns, the skill fills one row per paper, and every populated cell carries a source anchor and the verification layer it was checked at. Built on the M2 evidence kernel so an extracted number can be traced back to the exact passage it came from, and so the typed effect-size columns feed a meta-analysis mechanically.

## Refusal-grade integrity rules (inlined; canonical copy `references/integrity-constraints.md`)

These are binding. When a task cannot proceed without violating one, stop, name the rule, and ask the user how to proceed.

1. **Never fabricate a cell value.** Every populated cell comes from an actual passage of an actual paper. Do not fill a plausible-looking number, sample size, or metric from memory or by inference across studies.
2. **Genuinely absent data is `not reported`, never invented.** If the paper does not state a value, the cell is `not reported`. That is an honest abstention, and it is scored as one by the benchmark (see Gate). It is NOT the same as `insufficient-passage` (rule 4).
3. **A cell is only ever presented at the layer it was checked at.** A value read from an abstract is an abstract-layer cell and carries `insufficient-passage`; it must never be shown as full-text-verified.
4. **Consume the four-state verdicts, never a boolean (D9).** Read `refusal_grade` from the core JSON; do not re-derive the rule. Refusal-grade fires ONLY on `unresolvable` or `mismatch` (identity, axis a), `retracted` (status, axis b), or `contradicted` (faithfulness, axis c). `inconclusive` (identity) and `insufficient-passage` (faithfulness) are NEVER refusal-grade: they are open items, surfaced for a human, never dropped as fabrication and never accusations. A `source_error` is dirty evidence, not a clean negative.
5. **The human extracts; the skill organizes and records.** Cell values are the user's judgment (or a second extractor's). The skill retrieves the candidate passages, anchors them, records the table into the ledger, and flags conflicts. It does not silently accept or silently drop a value.

## What this skill produces

A table with one row per paper and the columns the user defined. Each **populated** cell carries, alongside its value:

- **source anchor**: `{paper (DOI or record id), passage_id, char_start, char_end}` for a full-text cell, or `{paper, section: abstract}` for an abstract cell.
- **verification layer**: `full-text` (anchored on an indexed OA passage) or `abstract` (only the abstract was reachable).
- **faithfulness verdict (axis c)** for the cell against its anchor: `supported`, `partial`, `contradicted`, or `insufficient-passage`. An abstract-layer cell is `insufficient-passage` by construction.

Cells that are not populated are exactly one of: `not reported` (the paper is fully readable but states no such value) or an open item awaiting full text (`insufficient-passage`, with a note on what would resolve it).

## Defining columns

Free-text columns (population, method, dataset, setting, and so on) hold a short extracted value plus its anchor. **Effect-size columns are TYPED** so the meta-analysis in the statistical-analysis skill can consume them without re-parsing prose. A typed effect cell carries these fields, and any the paper does not report are `not reported`:

| field | meaning |
|---|---|
| `measure` | the effect measure: `MD`, `SMD`, `OR`, `RR`, `RD`, `HR`, `r`, or a named metric (`accuracy`, `AUROC`, `F1`, ...) |
| `estimate` | the point estimate, as a number |
| `ci_low`, `ci_high` | confidence-interval bounds, OR |
| `se` | the standard error, when a CI is not given |
| `n_arm1`, `n_arm2` | sample size per arm (or `n_total` for single-group metrics) |
| `events_arm1`, `events_arm2` | event counts per arm, for binary outcomes |
| `metric_definition` | one line: exactly what was measured and how (units, direction, which arm is the reference) |
| `direction` | which arm or condition the estimate favors, so signs are not guessed downstream |

Record the estimate exactly as reported (do not recompute or convert measures during extraction; conversion is the meta-analysis step's job, done in code and lineage-bound). If a paper reports a CI, keep the CI; if it reports an SE or an exact p with a test statistic, keep those and leave `ci_low`/`ci_high` as `not reported`.

## Workflow

1. **Confirm the study set and columns.** Take the included papers (identifiers) and the column list from the user. If this is inside a systematic review, the study set is the included set from screening and the columns should match the review's planned synthesis.
2. **Verify each paper before extracting from it** (axes a, b). Run `verify-ref` per identifier. A `retracted` paper (axis b) is flagged for the user and never extracted from silently; an `unresolvable` or `mismatch` identity is refusal-grade and the paper does not enter the table until resolved; an `inconclusive` identity is flagged as an open item (one index only, or a source errored), never dropped as fabricated.
3. **Index the full text where an OA copy exists** (axis d). Run `passages index` per paper. A document with reachable full text yields stable passage IDs; an abstract-only or unavailable document yields zero passages, which is the signal that its cells extract at the abstract layer.
4. **For each cell, locate and anchor the value.** Use `passages search` to pull the candidate passage(s) for the column concept, read the value from the passage, and record the anchor (passage_id, offsets). Run `faithfulness` on the extracted value against the document to get the axis (c) verdict and the layer. A `contradicted` verdict means the passage says the opposite of the extracted value: treat it as a mis-extraction to fix, not a fact to record.
5. **Mark absences honestly.** Full text present but no such value: `not reported`. No full text at all: `insufficient-passage`, with the abstract-level reading (if any) shown as abstract-layer and flagged as unverified at full-text level.
6. **Record the completed table into the ledger** so it is content-addressed and the meta-analysis can bind to it (see Deterministic backend, step 5).
7. **Surface open items and conflicts** to the user: every `insufficient-passage` cell, every `inconclusive` paper, every `contradicted` cell, and (in dual mode) every extractor disagreement.

## Deterministic backend

Retrieval, identity, full-text extraction, passage anchoring, and provenance run through the `researcher-core` CLI, so an extracted number is traceable and the table is reproducible from snapshots (D15). Skills never import the kernel; they shell out and read `--json`. Full command and field reference: `references/core-cli.md`.

Standard invocation (two fallbacks in the reference, for a Codex install or a checkout without `uv`):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core <cmd> ... --json
```

**1. Verify each paper** (axes a, b, d), never a boolean:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-ref "<doi-or-title>" --json
```

Read per entry: `verdict` (`verified` / `mismatch` / `unresolvable` / `inconclusive`), `refusal_grade`, the `status` block (`current` / `corrected` / `retracted` / `expression-of-concern`), and `accessibility` (`full-text` / `abstract-only` / `unavailable`). A `status.checked: false` is an absence of evidence, not a clean bill of health.

**2. Index the full text** (axis d), which mints the stable passage IDs the anchors point at:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages index <doi-or-url> --db <review>.db --json
```

Read `document.accessibility` and `passages[]`. Zero passages with a `reason` means abstract-only or unavailable: every cell for this paper extracts at the abstract layer and is `insufficient-passage` at full-text level. Point `--db` at one index file for the whole review so every paper is searchable from the same store.

**3. Locate the candidate passage for a cell** (the anchor):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages search "<column concept, e.g. sample size / primary outcome / mean difference>" --doc <doc-id> --db <review>.db --limit 5 --json
```

Read each `passages[]` element's `passage_id`, `section_path`, `char_start`, `char_end`, `page_coords`, and `text`. The passage the value is read from is the cell's anchor. `page_coords` lets the report point a reader at the page.

**4. Confirm the extracted value against its anchor** (axis c) and record the layer:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core faithfulness "<the extracted value, stated as a claim>" --doc <doc-id> --db <review>.db --json
```

Read each `claims[]` entry's `verdict` and `evidence[]` anchors, and `document.accessibility` for the layer. Axis (c) is a LEXICAL baseline (BM25 plus token-overlap and polarity heuristics), measured coverage 0.750 in `evals/BENCHMARKS.md`: a `supported` verdict means "consistent with the passage at the lexical level", NOT proof the number is right, so a human still reads the passage. Only `contradicted` is refusal-grade on this axis; `insufficient-passage` is an open item.

**5. Record the completed table into the provenance ledger** so it is content-addressed and downstream steps can bind to this exact version (D19, D10):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core provenance append \
  '{"run_id":"<review-run-id>","type":"record_lineage","ts":"<caller-supplied RFC3339 ts>","payload":{"artifact_id":"extraction-table","artifact_hash":"sha256:<hash of the table file>","artifact_type":"extraction_table","inputs":[{"passage_id":"<id>","doc":"<doc-id>","response_hash":"<snapshot hash>"}]}}' \
  --ledger <review>.sqlite3 --json
```

`ts` is caller-supplied on purpose (the kernel never reads the clock, so replays stay byte-identical, D15). `record_lineage` is what the M3 compile gate reads to bind every pooled number in the manuscript to the input table hash and to catch a later-altered cell (`C002`) or a source that turned stale or retracted (`C003`, `C005`). Do not store derived PRISMA counts here; those are always derived via `provenance prisma` (D10). Use `provenance prisma --run-id <id> --json` only to READ counts, never to write them.

**Degradation path (the plugin never hard-fails without core, D3).** If `uv` or `core/` is unavailable, say so in the output and fall back in order: (1) the **Zotero MCP** where connected, for the user's stored PDFs and metadata; then (2) web search plus manual reading of the paper. Without core there are no stable passage IDs, so every cell degrades to abstract-or-manual layer, is marked as such, and no cell is presented as full-text-anchored. Name the tier that produced the table.

## Dual extraction (high-stakes reviews)

Cochrane-grade extraction is done independently by two people. This skill supports the same two-stream pattern the screening step uses (dual streams, disagreements reconciled by a human, everything recorded), organized here at the cell level:

1. Two extractors each fill the same columns for the same papers. Record each completed stream as its own `record_lineage` event with a distinct `artifact_id` (`extraction-table@stream-A`, `extraction-table@stream-B`), so the ledger holds both streams' content hashes.
2. The skill compares the two tables cell by cell and surfaces every disagreement, with each side's anchor, for a human adjudicator. Report the cell-level agreement rate as a diagnostic (this is computed here from the two tables; core's `screen kappa` derives kappa for the SCREENING streams, not for extraction cells).
3. The adjudicated value is recorded as the reconciled table (`extraction-table@final`) with its own `record_lineage` event; the meta-analysis and the compile gate bind to that final version.

Single-extractor mode remains available, but a review that used it must say so in its methods: single extraction is a stated limitation, not a hidden default.

## Gate (D18): accuracy is measured, not asserted

This skill is benchmark-gated. Its cell-level extraction accuracy, its `not reported` (abstention) precision, and its passage-anchoring rate are MEASURED on an extraction benchmark of at least 100 labeled cells (at least 20 per column type), with Wilson confidence intervals per D17. **The measured numbers live in `evals/BENCHMARKS.md`; read them there.** This skill does not quote an accuracy figure, because a figure typed into a skill file is a claim, not a measurement. When you report extraction quality to a user, cite the benchmark, not a remembered number. The skill ships only when that gate is green at D17 sizes.

## Output format

```markdown
# Extraction Table: <review or topic>
Papers: <N>   Columns: <list>   Mode: <single-extractor | dual-extractor>
Full-text layer: <n cells>   Abstract layer: <n cells>   not reported: <n>   insufficient-passage (open): <n>

| Paper | Population | Method | <Outcome> estimate | 95% CI / SE | n per arm | Layer |
|---|---|---|---|---|---|---|
| Smith 2023 [10.xxxx/yyyy] | adults with T2D | RCT, 12 wk | MD -0.4 | [-0.7, -0.1] | 60 / 58 | full-text |
| Jones 2022 [10.xxxx/zzzz] | adults, mixed | RCT, 8 wk | SMD 0.31 | SE 0.14 | 44 / 41 | full-text |
| Lee 2021 [10.xxxx/wwww] | older adults | cohort | not reported | not reported | 120 | abstract |

## Cell anchors
Smith 2023 / <Outcome> estimate = "MD -0.4":
  layer full-text; faithfulness supported (lexical, not proof); passage <passage-id> [methods 8123-8210]; page 6
Lee 2021 / <Outcome> estimate:
  layer abstract; insufficient-passage (no OA full text); open item, resolves if an OA copy is found

## Verification summary
Identity (a): <n> verified, <n> inconclusive (open, one index only), <n> flagged unresolvable/mismatch (not extracted)
Status (b): <n> current; flagged: <key> retracted (NOT extracted without user sign-off)
Faithfulness (c): <n> supported, <n> partial, <n> contradicted (mis-extractions to fix), <n> insufficient-passage

## Evidence provenance
core [verify-ref | passages | faithfulness | provenance]; passage index <review>.db; ledger <review>.sqlite3;
table artifact_hash sha256:<...>; snapshots [<response_hash>, ...]; mode [live | replay | record]

## Open items
[Every insufficient-passage cell, inconclusive paper, and contradicted cell, with what would resolve each.]
```

Typed effect-size columns are emitted in the machine-readable shape from "Defining columns" (a JSON or CSV sidecar keyed by the same fields), so the statistical-analysis meta-analysis step consumes them unchanged.

## Integration

- **systematic-review**: the extraction step of the end-to-end workflow; the study set is that review's included set and the ledger is that review's ledger. Extraction events feed the derived PRISMA flow and the review report.
- **statistical-analysis**: the typed effect-size columns flow into the meta-analysis handoff (routed to the Sonnet code agent). No pooled number is hand-typed; the analysis reads the recorded table, and the M3 compile gate binds each pooled estimate to the table's `record_lineage` hash.
- **fact-checking**: single-claim verification; this skill is the many-papers, many-columns tabular counterpart and reuses the same axes.
- **citation-management**: shares the paper identifiers and their verified metadata.

## Integrity constraints

1. Never fabricate a cell: every populated value comes from an actual passage of an actual paper. Absent data is `not reported`; unverifiable-at-full-text data is `insufficient-passage`. Never invent a number, sample size, or metric.
2. Never invent data: only values actually read from the source appear. Illustrative values are labeled `(synthetic, for demonstration)` and never presented as extracted findings.
3. Refuse to present as valid output: a cell traceable to no passage, a value read from a retracted source cited as current, or a table that hides that it was single-extractor when the review claims dual.
4. Consume the four-state verdicts, never a boolean. Refusal-grade fires ONLY on `unresolvable` / `mismatch` (a), `retracted` (b), or `contradicted` (c). `inconclusive` and `insufficient-passage` are NEVER refusal-grade: surface them as open items, never accusations, never clean. Read `refusal_grade` from the core JSON rather than re-deriving the rule.
5. No em dashes in generated text: use commas, colons, parentheses, or separate sentences.

Canonical copy: `references/integrity-constraints.md`.
