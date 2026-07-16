---
name: literature-monitoring
description: "Keep a review current with a standing saved search that reports only what is NEW since the last run. Triggers when user says: 'watch this topic', 'watch topic', 'living review', 'monitor literature', 'monitor the literature', 'alert me to new papers', 'keep this review current', 'keep my review up to date', 'saved search', 'rerun my search for new results', 'what is new since last time', 'set up a literature alert'. Saves the verbatim per-database strategies, the last-run timestamp, and the seen-record ids, then on rerun re-executes those strategies through core, diffs against what it has already seen, and surfaces only the unseen records as a new screening batch under the same locked protocol. Use this for an ONGOING watch that tracks new papers over time; for a ONE-SHOT search that returns everything now, use literature-search; for the full review workflow around it, use systematic-review."
---

# Literature Monitoring (living reviews)

A systematic review is a snapshot; a living review is that snapshot kept current. This skill holds
the piece that makes "kept current" mean "only the new records": a saved search (the verbatim
per-database strategies, the last-run timestamp, and the list of record ids already seen), plus a
diff on rerun that reports the records it has not seen before, and nothing else. Those new records
become the next screening batch under the same locked protocol, which is what makes the review
living rather than redone from scratch.

It is the ongoing counterpart to literature-search (one-shot discovery) and the entry point for the
`/researcher:watch-topic` command. The full review workflow that consumes its batches is
`systematic-review`.

## CRITICAL INTEGRITY RULE

Consume the four-state verdicts, never a boolean (D9). When a newly surfaced record is checked for
identity before it enters the review, read the axis (a) verdict from `verify-ref`
(`verified` / `mismatch` / `unresolvable` / `inconclusive`) and the kernel's `refusal_grade` flag,
never a true/false:

- Refusal-grade (withhold or flag as fabricated or wrong): `unresolvable`, `mismatch`, plus
  `retracted` on status (axis b) and `contradicted` on faithfulness (axis c).
- NEVER refusal-grade (surface as an open item, never drop): `inconclusive` (a source errored, or
  only one index holds the paper) and `insufficient-passage` (no OA full text to anchor a claim).

A source that times out or 5xxes is dirty evidence, not a clean negative (D9): its slice of the
diff is INCOMPLETE, so an empty result from a downed source is "unknown this run", never "no new
papers". Humans make every screening decision; this skill organizes and records. Canonical copy:
`references/integrity-constraints.md`.

## The saved-search state file

The state lives in `manuscript/monitoring.json`, the file the `monitor` command reads and writes.
It is JSON, not YAML: the kernel's runtime carries no YAML parser, so this is the on-disk form the
diff replays from. One state object per saved search:

```json
{
  "schema_version": "1.0",
  "monitor_id": "crispr-offtarget-living",
  "strategies": [
    {"source": "openalex", "query": "CRISPR off-target detection", "label": "openalex-main"},
    {"source": "pubmed",   "query": "(CRISPR[Title]) AND (off-target[Title/Abstract])"}
  ],
  "seen_ids": ["10.1000/aaa", "10.1000/bbb"],
  "last_run": "2026-06-01T00:00:00Z",
  "run_count": 2
}
```

- `monitor_id`: names the saved search; required.
- `strategies[]`: the exact per-database query strings (M4.3), stored and replayed byte for byte,
  never paraphrased. Each carries `source`, verbatim `query`, an optional `endpoint`, and an
  optional `label` (a stable handle when two strategies target one source).
- `seen_ids[]`: the record ids already reported. This is the diff baseline. It only ever GROWS:
  ids are appended in order, deduplicated, and never removed or reordered, so a record reported new
  once is never reported new again. Ids are the kernel's stable record id (lowercased DOI when one
  exists, otherwise a source-prefixed native id such as `openalex:W2741809807`).
- `last_run`: the caller-supplied RFC 3339 timestamp of the last rerun; empty before the first run.
  Never read from the clock, so two replays of the same rerun stay identical (D19, D15).
- `run_count`: how many times this search has run.

## Workflow: setting up a watch (first run)

1. **Draft the strategies conversationally.** Help the user write one verbatim query per database,
   the same exact strings a systematic-review protocol locks (M4.3): the OpenAlex filter, the
   PubMed term string with field tags, the arXiv query. Never invent a strategy the user did not
   approve; record what they wrote, not a paraphrase.
2. **Establish the baseline.** Run each strategy once through core (see Deterministic backend). The
   records returned are the initial set. For a watch attached to an existing review, its already
   screened record ids seed `seen_ids` so the first rerun reports only what arrived since. For a
   fresh watch, the whole first result set is the opening screening batch, and all its ids go into
   `seen_ids`.
3. **Write `manuscript/monitoring.json`** with the strategies, the seed `seen_ids`, `last_run` set
   to the run timestamp, and `run_count: 1`.
4. **Confirm** the saved search back to the user: the `monitor_id`, the strategies verbatim, and
   how many ids are in the baseline.

## Workflow: the rerun (diff-on-rerun)

The CLI surface today is `monitor status` (it reads the saved state); the diff itself executes the
saved strategies through the `search` command and compares against `seen_ids`.

1. **Read the state.** `monitor status --state manuscript/monitoring.json --json`; take
   `strategies[]`, `seen_ids[]`, and `last_run`.
2. **Re-execute every strategy VERBATIM** through `search`, one call per strategy, passing the
   stored `query` and `source` unchanged. Discovering genuinely new papers needs fresh data, so
   this is a live `--record` call that captures a snapshot of every response; those snapshots are
   what make THIS rerun replayable and auditable offline afterward (D15). Determinism is never
   claimed for the live discovery call itself.
3. **Collect the current ids.** From each `search` JSON, read every record's `id` from `records[]`.
   Combine across strategies, order-stable and deduplicated: this is `current_ids`.
4. **Check reachability first (D9).** For each strategy, read `warnings[]` and `sources[]` from its
   `search` output. If a source errored (timeout, rate limit, 5xx), its slice of the diff is
   incomplete: say so explicitly ("PubMed was not reached this run; new PubMed records may be
   missing") and do NOT record its absence as "no new papers". A downed index is not a clean
   negative.
5. **Diff.** The new batch is exactly the ids in `current_ids` that are not in `seen_ids`,
   order-stable and deduplicated. Both inputs are recorded artifacts (the state file and the
   snapshot-backed searches), so the diff is auditable after the fact.
6. **Report only the new records.** For each, present the CSL metadata and, when it will enter the
   included set, its axis (a) identity verdict and layer (see the integrity rule). Say plainly when
   there are zero new records, distinguishing that from "a source was unreachable".
7. **Record the rerun on the ledger.** Append one `retrieval` event per strategy through
   `provenance append`, carrying the verbatim query, the source, the ids returned this run, and the
   snapshot hashes, so the derived PRISMA counts move (M4.12) and the rerun is on the trail.
8. **Feed the living review.** Hand the new batch to the screening streams as a new screening batch
   under the SAME locked protocol (see below).
9. **Advance the state.** Append the new ids to `seen_ids` (in order, no duplicates, never removing
   any), set `last_run` to this run's timestamp, and increment `run_count`. Write
   `manuscript/monitoring.json` back. This mirrors the kernel's own monotonic update, so the state
   stays consistent whether the skill or the kernel wrote it.

## Deterministic backend

Retrieval, id extraction, and snapshotting route through the `core/` evidence kernel; the skill
reads its JSON and never hand-builds an API call.

### Read the saved state

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core monitor status --state manuscript/monitoring.json --json
```

Read `strategies[]` (each `source`, `query`, optional `label`), `seen_ids[]`, `last_run`, and
`run_count`. `--state` is required; there is no implicit default path.

### Re-execute one strategy (the rerun's discovery call)

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<verbatim query>" --sources <source> --record --json
```

Read from the JSON:
- `records[]`: each record's `id` is what the diff compares. The records are CSL-JSON with kernel
  metadata under `custom`.
- `warnings[]`: a source that timed out or was rate-limited lands here; its diff slice is incomplete
  (D9). Never read a downed source as "no new papers".
- `sources[]`: which sources actually answered.
- `counts{retrieved, deduplicated, duplicates_removed}`: the tallies for the rerun report.

`--record` makes the live call and captures a content-addressed snapshot of every response. To
REPLAY a past rerun offline (auditing, or reproducing the diff), set
`RESEARCHER_CORE_SNAPSHOT_MODE=replay` and run the same strategy: it reads only the snapshots that
rerun captured and a missing one raises loudly rather than going to the network (D15). Add `--since
<last-run-year>` to bound a strategy to recent work when the source supports it. Full command, flag,
and JSON reference: `references/core-cli.md`.

### Record the rerun on the ledger

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core provenance append '<event-json>' --json
```

Append one `retrieval` event per strategy: type `retrieval`, payload carrying the verbatim `query`,
the `source`, and the `record_ids` returned this run, with the rerun's caller-supplied `ts` and the
strategy's `source_response_hashes` from the search. PRISMA counts are DERIVED from these events by
`provenance prisma`, never stored (D10):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core provenance prisma --json
```

Read `identified`, `identified_by_source{}`, `duplicates_removed`, `deduplicated`, `screened`,
`included`, and `excluded` straight from the derived object; the living-review flow updates because
the ledger grew, not because a total was edited.

### Degradation path (never hard-fail, D3)

The kernel is optional; state which tier produced the rerun.
1. `core/` present: `monitor status` plus snapshot-backed `search` as above (the deterministic path).
2. No `uv` or `core/`: fall back to connected MCP servers (Scite, Zotero) or web search for the
   discovery call, diff their results against `seen_ids` by hand, and say the kernel was
   unavailable, so the rerun is not snapshot-reproducible. Keep maintaining
   `manuscript/monitoring.json` by hand under the same schema.
3. Neither: web search, clearly labeled non-deterministic and unverified.

## Feeding the living review

A living review is not a fresh search each time; it is the same locked protocol with new records
arriving. So the new batch flows straight into the M4.4 screening streams:

- **Same criteria:** record the new ids as a new screening batch under the existing `run_id` and
  locked `protocol_version`, then run dual screening on them exactly as the original set
  (`screen decide` per screener, `screen conflicts` for blind adjudication, `screen kappa`). The
  batch is additive; nothing already screened is re-screened.
- **Criteria must change** (a new inclusion rule, a widened population): this is a protocol
  deviation, so `protocol amend` first (it emits an `amendment` event and bumps
  `protocol_version`), then screen the new batch under the amended version. The ledger shows the
  locked original plus the amendment trail (PRISMA 2020 item 24b); never silently edit the criteria.

Every record entering the included set passes axis (a) identity verification; an `inconclusive`
entry is flagged for human review, never dropped as fabricated.

## Scheduling reruns

No scheduler ships inside the plugin, by design: this skill produces the batch, it does not run
itself on a clock. Automate reruns from OUTSIDE the plugin:

- an external cron job (or Windows Task Scheduler) that invokes `/researcher:watch-topic` on a
  cadence;
- Claude Code recurring tasks: the `/loop` feature (rerun on an interval) or the `/schedule`
  feature (a cron-scheduled agent).

Whatever the trigger, the rerun is the same diff-on-rerun above, and each run passes its own
caller-supplied timestamp so the ledger and the state file stay deterministic.

## Disambiguation

- Use **literature-monitoring** for a STANDING watch with saved state that reports only what is new
  since last time and feeds a living review.
- Use **literature-search** for a ONE-SHOT search that returns everything relevant now, with no
  saved state and no diff.
- Use **systematic-review** for the surrounding workflow (protocol lock, dual screening, PRISMA
  reporting) that a living review's batches plug into.

## References

For the full core CLI (every command, flag, JSON shape, and the four verification axes), read
`references/core-cli.md`. For search-strategy construction, read `references/search-strategies.md`.

## Integrity constraints

1. Never fabricate citations: every surfaced record comes from an actual retrieval (core, MCP, or
   web search). If a rerun reaches no source, report that, never an invented paper.
2. Never invent data: report the diff the recorded searches produced; a downed source is "unknown
   this run", never a fabricated empty result.
3. Consume four-state verdicts (D9): refusal-grade only on `unresolvable`, `mismatch`, `retracted`,
   or `contradicted`; `inconclusive` and `insufficient-passage` are open items, never refusals, and
   a `source_error` is dirty evidence, never a clean negative.
4. Humans screen; this skill organizes and records. PRISMA counts are always derived via
   `provenance prisma`, never stored (D10).

Canonical copy: `references/integrity-constraints.md`.
</content>
</invoke>
