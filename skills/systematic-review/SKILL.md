---
name: systematic-review
description: "Run a methodologically defensible systematic review end to end over the provenance ledger. Triggers when user says: 'systematic review', 'PRISMA', 'PRISMA flow diagram', 'screening', 'title and abstract screening', 'dual screening', 'dual independent screening', 'eligibility criteria', 'inclusion and exclusion criteria', 'PICO', 'PECO', 'SPIDER', 'lock the protocol', 'register a review protocol', 'Cohen's kappa', 'screening conflicts', 'meta-analysis review', 'Cochrane review', 'RoB 2', 'GRADE', 'living systematic review'. Locks a hash-bound protocol before any screening, records verbatim per-database search strategies, runs dual independent screening with blinded adjudication, and derives every PRISMA 2020 count from the ledger. Humans make every screening decision; this skill organizes and records them. For simply finding papers use literature-search; for auditing one manuscript's citations use citation-audit; for pulling structured data from included studies use extraction-tables."
---

# Systematic Review

The end-to-end systematic-review workflow, built on the append-only provenance ledger and the four
verification axes of the evidence kernel. PRISMA 2020 is the REPORTING layer here, not the
architecture: the architecture is the event ledger, and the flow diagram and checklist are views
DERIVED over it (D10). This skill locks a protocol before screening starts, records the exact
per-database search strings, runs two independent screening streams with blinded adjudication, and
derives every count. It NEVER makes an eligibility judgment for the user: humans screen, and this
skill organizes and records what they decide.

Invoked as `/researcher:systematic-review`.

## Refusal-grade constraints (inlined, binding)

Canonical copy: `references/integrity-constraints.md`. The refusal-grade rules below are binding and
present in context even when that file is never read.

1. **Never fabricate citations.** Every record entering the review comes from an actual retrieval
   (kernel search, MCP result, or a source the user supplied). Never invent a DOI, author, venue, or
   year, and never "fill in" plausible metadata from memory.
2. **Never invent data.** Screening tallies, PRISMA counts, and extracted values describe only what
   the ledger actually holds. Counts are DERIVED (see below), never typed in by hand.
3. **Consume the four-state verdicts, never a boolean (D9).** Refusal-grade fires ONLY on
   `unresolvable` or `mismatch` (identity, axis a), `retracted` (status, axis b), or `contradicted`
   (faithfulness, axis c). `inconclusive` and `insufficient-passage` are OPEN ITEMS, never
   refusal-grade: a rate-limited source or a single-index paper is not evidence of fabrication.
   A `source_error` is dirty evidence, not a clean negative. Reading either as fabrication would
   accuse an honest reviewer of inventing a real citation, the worst failure this system can make.
4. **Humans decide; the skill records.** Every screening and appraisal decision is made by a person.
   Automation flags (prioritization order, single-screener mode) are disclosed in the report, never
   a hidden default, and no flag ever auto-excludes a record.
5. **No em dashes in generated prose.** Restructure with commas, colons, parentheses, or two
   sentences.

## Precondition: no screening without a locked protocol (M4.1)

Screening cannot begin until a `protocol_locked` event exists for the run. Before recording any
screening decision, confirm the lock:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core protocol check protocol.yaml --run-id <run-id> --json
```

If `amendment_trail` is empty and `expected_hash` is `""`, no protocol is locked: STOP and route the
user to Stage 1. Do not screen. If `matches` is `false` with a non-empty `expected_hash`, the
protocol file was edited after locking WITHOUT an amendment (a hash mismatch, exit 1): STOP, report
the tamper, and either restore the locked content or record the change as an amendment (Stage 1).

## Deterministic backend: the workflow over the ledger

Every stage below is an exact kernel invocation writing to, or deriving from, the D19 ledger. The
standard form is `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core <cmd>`.
Full command, flag, and JSON reference: `references/core-cli.md`. Pick one `run-id` at Stage 1 and
reuse it for the whole review; supply an ISO 8601 `--ts` (for example `2026-07-16T09:00:00Z`) on
every writing command, so replays stay byte-identical (D15). The kernel never reads the clock.

### Stage 1: Draft and lock the protocol (M4.1, M4.2)

Help the user draft the protocol conversationally: the question, the structured eligibility profile,
the per-database search strategies, and the planned synthesis. Use
`templates/eligibility-profile.yaml`, which frames eligibility as PICO, PECO, or SPIDER with
per-element include and exclude criteria. Map a qualitative question onto SPIDER cleanly rather than
faking PICO fields. Leave any element the user has not decided BLANK; never fill it in.

The eligibility elements (population, intervention or exposure, outcome) are the SAME qualifier axes
the compile-gate evidence edges carry, so screening reasons and the later qualifier checks share one
vocabulary.

Write the drafted protocol to `protocol.yaml` (question, eligibility, strategies, synthesis), then
lock it. The lock hashes the content and emits a `protocol_locked` event:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core protocol lock protocol.yaml --run-id <run-id> --ts <TS> --json
```

Read from the returned event: `protocol_version` (`"1.0"` for the lock) and
`payload.content_hash`. From here the run is bound to that hash.

A deviation is NEVER an edit. To change the locked protocol, record an amendment (this bumps the
version and preserves the original plus the full trail, PRISMA 2020 item 24b):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core protocol amend protocol.yaml --run-id <run-id> --ts <TS> --summary "what changed" --rationale "why" --json
```

`--summary` and `--rationale` are required: an unexplained amendment is exactly the silent edit this
system exists to prevent.

### Stage 2: Execute and record per-database strategies (M4.3)

Each source gets a VERBATIM query string, not a paraphrase: the exact OpenAlex filter expression, the
Crossref query, the PubMed term string with field tags, the arXiv query. Run each database strategy
through the kernel in record mode so every response is snapshotted:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<verbatim query>" --sources pubmed --json --record
```

Read `records[]`, `counts{retrieved, deduplicated, duplicates_removed}`, and `dedup_decisions[]` from
the search JSON. Then record the strategy as a `retrieval` event carrying the verbatim string, so the
derived search-strategy appendix reproduces it byte for byte. Write the event JSON to a file and
append it:

```
{"run_id": "<run-id>", "type": "retrieval", "ts": "<TS>",
 "payload": {"source": "pubmed", "query": "<verbatim query>", "record_ids": ["...", "..."]}}
```

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core provenance append retrieval-pubmed.json --json
```

Repeat per database. `payload.query` is what PRISMA 2020 item 7 requires and what most tools fake;
`payload.source` and the `record_ids` length feed the derived `identified_by_source` counts. Live
re-runs are canary-only and never gate; an offline replay from the same snapshots yields identical
identified counts.

### Stage 3: Deduplicate

The kernel already deduped within each `search` call and reported `dedup_decisions[]`. Record each
collapse as a `dedup_decision` event so the derived flow can count duplicates removed:

```
{"run_id": "<run-id>", "type": "dedup_decision", "ts": "<TS>",
 "payload": {"winner": "<kept id>", "losers": ["<removed id>"], "reason": "same DOI", "similarity": 1.0}}
```

Append it with `provenance append`. Do not compute or store a duplicates total yourself; the flow
derives it (Stage 8).

### Stage 4: Dual independent screening with blinded adjudication (M4.4)

Two independent streams, each keyed by a distinct `--screener` id, over two stages in order:
`title-abstract`, then `full-text`. A person makes each call; you record it. One decision per record
per screener per stage:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core screen decide --run-id <run-id> --screener alice --record <record-id> --stage title-abstract --decision include --ts <TS> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core screen decide --run-id <run-id> --screener bob --record <record-id> --stage title-abstract --decision exclude --reason "wrong population" --ts <TS> --json
```

`--decision` is `include` or `exclude`; `--reason` is drawn from the eligibility profile and is what
populates the excluded-with-reasons counts. Each command returns its event; keep the `event_id`, you
need both to adjudicate.

Surface the disagreements BLIND. `screen conflicts` returns, per conflicting record, ONLY the record
and the eligibility profile: never the other screener's verdict or reason. This is the blinding the
methodology depends on, and it is constructed by the kernel, not by Claude summarizing the ledger, so
a vote cannot leak into the adjudication prompt:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core screen conflicts --run-id <run-id> --stage title-abstract --corpus corpus.json --profile profile.json --json
```

`corpus.json` maps record id to its metadata; `profile.json` is the eligibility profile. The output
is an array of `{record_id, stage, record, eligibility_profile}` objects with NO votes. Present each
to the adjudicator, take their independent decision, and record it as an `adjudication` event whose
`resolves` carries BOTH original `screening_decision` event ids, so the ledger proves which two
decisions were reconciled:

```
{"run_id": "<run-id>", "type": "adjudication", "ts": "<TS>",
 "payload": {"record_id": "<record-id>", "stage": "title-abstract", "decision": "include",
             "reason": "", "rationale": "meets population and outcome criteria",
             "resolves": ["<alice event_id>", "<bob event_id>"]}}
```

Append with `provenance append`. An adjudicated `exclude` needs a `reason` from the profile so it
lands in the excluded-with-reasons breakdown. Report inter-rater agreement, DERIVED from the ledger:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core screen kappa --run-id <run-id> --stage title-abstract --json
```

Read `kappa`, `n`, `observed_agreement`, `table`, and `single_screener`. A one-stream run returns
`kappa: null` with `single_screener: true` rather than a fabricated number (see Single-screener
mode). Run full-text screening the same way, on the records that passed title-abstract.

### Stage 5: Optional prioritization (M4.5)

Prioritization reorders the remaining screening queue by lexical similarity to already-included
records, so relevant records surface earlier. It is OFF by default and it changes ORDER ONLY: every
record is still screened by a person, nothing is auto-excluded, and there is no cut point. If the
user opts in, disclose in the report that prioritized screening was used and that no record was
dropped. Disabling it restores insertion order exactly.

### Stage 6: Identity-verify the included set

Every reference entering the included set passes axis (a) identity verification before it is cited.
Build a `.bib` of the included studies and run:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-bib manuscript/references/library.bib --json
```

Per entry, read `verdict`, `refusal_grade`, `source_outcomes[]`, and the `status` block. Block only
refusal-grade entries (`unresolvable`, `mismatch`, or `retracted` on status). An `inconclusive` entry
(a source errored, or only one index holds the paper) is FLAGGED FOR HUMAN REVIEW, never dropped as
fabricated. Surface `expression-of-concern` as an open item too.

### Stage 7: Handoff to extraction, appraisal, and synthesis

With the included set fixed, hand off to the specialist skills. This skill owns the protocol,
screening, and reporting spine; these own the downstream artifacts:

- **Extraction**: the `extraction-tables` skill pulls structured per-study values (population,
  method, metric, effect size, variance) anchored against full-text passages when available, abstract
  otherwise. Abstract-only cells carry `insufficient-passage` and are never shown as full-text
  verified.
- **Appraisal**: complete a `references/rob2-worksheet.md` (RoB 2, for randomized trials) or
  `references/grade-worksheet.md` (GRADE certainty) per study or outcome. The worksheets prefill only
  mechanical fields; the human makes every risk-of-bias and certainty judgment. There is NO automated
  risk-of-bias scoring. Completed worksheets are hashed into the ledger so the report can prove which
  appraisal version fed the conclusions.
- **Synthesis**: for a meta-analysis, route the typed effect-size columns to the
  `statistical-analysis` skill, which generates the pooling script (pooled effect, I-squared,
  tau-squared, forest and funnel plots) through the Sonnet code agent. No pooled number is hand-typed;
  the compile gate binds every pooled number to the script and its input table hash.

### Stage 8: Report with the derived PRISMA 2020 flow and checklist (M4.12)

Every count in the report is DERIVED by aggregating ledger events; nothing is stored or hand-edited
(D10). Deleting a screening event changes the derived flow, which is what proves the counts are
derived rather than stored.

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core prisma flow --run-id <run-id> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core prisma checklist --run-id <run-id> --json
```

From `prisma flow` read `identified`, `identified_by_source{}`, `duplicates_removed`,
`records_after_dedup`, `records_screened`, `records_excluded`, `reports_sought_for_retrieval`,
`reports_assessed`, `reports_excluded_by_reason{}`, `studies_included`, `protocol_locked`, and
`amendments`. These are the boxes of the PRISMA 2020 flow diagram; render it as a TikZ figure through
the `tikz-diagrams` skill plus a plain table. From `prisma checklist` read `coverage{}` and
`items[]`, each mapping a PRISMA item to ledger evidence or marking it author-supplied.

List every amendment in the report (PRISMA 2020 item 24b): the locked original plus each amendment,
from the `amendment_trail` that `protocol check` returns. Compile-check the review manuscript stub
before delivery per the integrity constraints.

### Degradation path (D3)

The kernel is optional and the plugin never hard-fails for want of it. State which tier produced the
result:

1. `core/` present: the deterministic workflow above. This is the only tier that gives a hash-bound
   protocol, a byte-reproducible search appendix, blinded adjudication constructed by the kernel, and
   DERIVED PRISMA counts.
2. No `uv` or `core/`: fall back to connected MCP servers (Zotero for the user's library, Scite for
   citation context) for retrieval, and record the protocol, decisions, and search strings as a
   plain structured log the user keeps. Say plainly that the ledger, the blinding guarantee, and the
   derived counts were NOT produced, so a count in this mode is author-maintained, not derived.
3. Neither: web search, clearly labeled non-deterministic and unverified, with the same disclosure.

Never present a systematic review as PRISMA-derived or its adjudication as blinded unless tier 1
produced it.

## Single-screener mode

Dual independent screening is the default and the methodologically defensible choice. Single-screener
mode (one `--screener` id) is available but is a STATED LIMITATION, never a hidden default:
`screen kappa` returns `single_screener: true` and `kappa: null`, and the report must say that only
one stream screened the records. Do not present a single-screener review as if two independent
reviewers had agreed.

## Amendments and living reviews

A living review reruns the saved search strategies and screens only the new records under the SAME
locked protocol (or a recorded amendment if the criteria must change). The `literature-monitoring`
skill owns the saved-search state (`manuscript/monitoring.yaml`) and the diff-on-rerun; its output
feeds back into Stage 4 as a new screening batch, and the derived PRISMA flow (Stage 8) then shows
the updated counts. Inspect the saved state with:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core monitor status --state manuscript/monitoring.yaml --json
```

## Integrity constraints

1. Never fabricate citations: every record comes from an actual retrieval (kernel, MCP, or
   user-provided source). If a citation cannot be verified, flag it as an open item; never invent a
   DOI, author list, venue, or year, and never drop an `inconclusive` real citation as fabricated.
2. Never invent data: screening tallies and PRISMA counts are derived from the ledger, never typed by
   hand. Any illustrative value is labeled "(synthetic, for demonstration)".
3. Refuse to present as valid output: a likely-fabricated or `unresolvable` citation, a `mismatch`, a
   `retracted` source (unless the user explicitly cites it as retracted), or a `contradicted` claim.
   `inconclusive`, `expression-of-concern`, and `insufficient-passage` are open items, surfaced for
   the user, never refusal-grade.

Canonical copy: `references/integrity-constraints.md`. Full CLI and the four axes:
`references/core-cli.md`.
