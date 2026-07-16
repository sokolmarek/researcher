# The evidence-lineage graph

This is the data model behind `researcher compile` (M3). It connects every claim in a manuscript to
the evidence that backs it, so a compile can tell a supported claim from an orphan, a stale citation,
or a hand-edited number. Skills that build or read the graph shell out to the core CLI; this file
describes the shapes they exchange. The command reference is `references/core-cli.md`.

Nothing here is a mutable store. The graph lives as append-only events in the provenance ledger (D19),
and gate state is always re-derived from that stream, never written down as a `compiled: true` flag.
Every identifier is deterministic (D15): the same manuscript bytes, configuration, and parser version
produce byte-identical output, so a compile replays exactly. No part of the model reads the clock;
timestamps are supplied by the caller.

## Claim nodes

A claim node is a span of manuscript text with a stable identifier:

```
{claim_id, file, span: {start, end}, text_hash, normalized_text,
 kind: assertion | number | comparison, parser_version}
```

The `claim_id` is `hash(normalized_text + file + parser_version)`. Normalization is NFC plus
whitespace collapse, so re-wrapping a sentence keeps the same id and does not orphan its evidence,
while a substantive rewrite produces a new node and the old edge is reported dangling. The `text_hash`
is over the raw span bytes, so any edit at all stays visible even when the id survives it.

Claude proposes the span boundaries and the `kind`; core computes the ids and hashes. A `number` claim
points at an experiment run, the others at external sources.

## Evidence edges

An edge ties one claim to one piece of support. There are two kinds, and exactly one target is set.

**External** (a source passage):

```
{claim_id, target_kind: "external", passage_id,
 qualifiers: {population, intervention_or_exposure, outcome,
              source_version: {snapshot_hash, retrieved_at},
              evidence_quality: systematic-review | RCT | observational | preprint | abstract-only},
 axis_verdicts: {identity, status, faithfulness, accessibility}}
```

The `passage_id` is an M2 passage id (D21): the hash of a document's content hash, section path,
character offsets, and parser version, so it points at the exact span with page coordinates. The
qualifiers describe what the source actually studied, which is what the C004 qualifier-mismatch check
compares against the claim. `evidence_quality` is a string enum from day one; M4 upgrades it to GRADE
without changing the field. The four `axis_verdicts` are the D16 verdicts current when the edge was
made, so the compiler can tell later whether a source has since been retracted or corrected.

**Internal** (an experiment run):

```
{claim_id, target_kind: "internal", manifest_hash}
```

A results-section number points here, at the manifest that produced it, not at the literature.

### Which edges satisfy the gate

- A refusal-grade verdict on an edge (identity `unresolvable` or `mismatch`, status `retracted`,
  faithfulness `contradicted`) means the edge cannot satisfy the gate, and the claim fails to compile.
- An edge whose faithfulness is `insufficient-passage` is a valid edge but an open item, never a
  satisfied one: the claim was degraded to abstract level and was never actually checked against the
  source text (D11). It does not fail the compile, but it does not pass it either.
- An `inconclusive` identity verdict is never refusal-grade (D9). It is surfaced for review and does
  not accuse anyone.
- A supported, full-text external edge, or a clean internal edge, satisfies the gate for its claim.

## Experiment manifests

A manifest records what produced a number:

```
{manifest_version, run_id, code_commit, dirty_worktree,
 data_hashes: [...], environment_lockfile_hash, seed,
 metric_definitions: [{name, formula_or_ref}],
 artifact_hashes: [{path, hash, produced_at}], command_line, ts}
```

The `manifest_hash` is the content hash of this whole record. An internal edge points at it. The
`artifact_hashes` are how a hand-edited generated number is caught: the edit changes the artifact's
content without updating the recorded hash, so the C002 mismatch is detectable. `dirty_worktree` and
`code_commit` feed the C006 artifact-code-drift check. `ts` is caller-supplied (D19), so a manifest
hashes identically on replay.

## How the compile gate uses the graph

`researcher compile` walks the claim nodes, follows their edges, re-checks the current axis verdicts
against the recorded `source_version`, and emits a diagnostic per defect: C001 orphan claim (no edge),
C002 altered number (artifact hash mismatch), C003 stale evidence (snapshot superseded or status
flipped), C004 qualifier mismatch, C005 retraction, C006 artifact-code drift. A `source_error` during
a re-check yields `inconclusive`, never a C003 or C005, because a downed index is not evidence of
anything (D9). The report is replayable and appends a `gate` event to the ledger;
`/researcher:submit-ready` refuses a ready verdict unless the derived gate state is a pass.
