---
name: research-pipeline
description: "Run the full research pipeline as staged, checkpointed work. Triggers when user says: 'run the pipeline', 'research pipeline', 'end to end paper', 'take this from question to submission', 'full workflow', 'plan to draft to review', 'orchestrate the whole paper', 'staged manuscript build'. Moves a manuscript through Plan, Retrieve, Synthesize, Draft, Review, Compile, and Format, pausing for the author after every stage and refusing to format until the evidence-lineage compile gate passes. Use this to drive a manuscript end to end; for a single stage, use that stage's own skill."
---

# Research Pipeline

A staged pipeline that turns a research question into a submission-ready manuscript, with the
evidence-lineage compile gate standing between the writing and the formatting. Every claim that
reaches the page has to compile from either a qualified source span or an experiment run before the
manuscript can be formatted for submission.

This skill orchestrates other skills; it does not replace them. Each stage routes to the skill that
owns it, records what it did into the append-only provenance ledger (D19), and stops for the author.

## The stages

The pipeline runs these in order, with a human checkpoint after EVERY one:

1. **Plan.** Clarify the question, scope, and any protocol notes. Route to `brainstorming` and
   `experiment-design` as needed. Output: a short plan the author confirms.
2. **Retrieve.** Fan out across sources through the core CLI, dedupe, and rank. Route to
   `literature-search`. Retrieval, dedup, and record-lineage events land in the ledger; PRISMA
   counts are derived, never stored.
3. **Synthesize.** Build an outline and propose evidence-edge candidates: for each claim the outline
   will make, which passage or run backs it. Claude proposes the qualifiers (population,
   intervention or exposure, outcome); the author confirms; core records the edges.
4. **Draft.** Write the sections. Route to `paper-drafting`. As each section lands, its claims are
   extracted as claim nodes and anchored to the proposed edges.
5. **Review.** Route to `peer-review`. Review findings are appended as `review` events.
6. **Compile.** Run the gate (below). A `gate` event is appended with the verdict.
7. **Format.** Route to `journal-formatting` or `word-output`. Reachable ONLY from a passing compile.

A failing compile routes back to Draft or Review with the diagnostics. No stage rewrites a prior
ledger record: the ledger is append-only, so the history of the manuscript's evidence stays intact.

## The compile gate

Between Review and Format, run:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core compile --manuscript manuscript/ --json
```

Read the `verdict`. It fails on any of the six defect classes:

- **C001 orphan claim**: a claim with no evidence edge.
- **C002 altered number**: a generated number whose artifact hash no longer matches its manifest.
- **C003 stale evidence**: a cited source's snapshot was superseded, or its status flipped.
- **C004 qualifier mismatch**: the claim's population, intervention, or outcome does not match the
  source's.
- **C005 retraction**: a cited source is now retracted or under an expression of concern.
- **C006 artifact-code drift**: a run's commit is not in the current history, or its worktree was dirty.

Present the diagnostics with their remediation hints and route back. Do not proceed to Format on a
`fail`.

## Refusal-grade behavior (inlined; canonical copy `references/integrity-constraints.md`)

The four-state identity verdict is consumed, never a boolean (D9). Refusal-grade behavior fires ONLY
on `unresolvable`, `mismatch`, `retracted`, or `contradicted`. `inconclusive` is NEVER refusal-grade:
it means a source was rate-limited or only one index holds a paper, and accusing an honest author of
fabricating a real citation is the worst failure this system can have. An `insufficient-passage`
verdict (a claim with only abstract-level evidence) is an open item, never clean and never a refusal
(D11). Every stage that reports a verdict names the layer it verified against (abstract vs full-text).

A `source_error` during the compile's status re-check yields an `inconclusive` line item, not a C003
or C005 defect. The gate fails only on clean-evidence defects.

## Human-in-the-loop by default

The checkpoint after every stage is not optional in this release. Automation flags (`--auto` between
selected stages) are named here for forward compatibility but are disabled: the pipeline always waits
for the author. This is deliberate. The gate metrics that would justify automating a stage are
measured per D17, and until a stage's metric holds, a human confirms it.

## Degradation (D3)

Without `uv` or `core/`, the pipeline still runs its Claude-side stages (Plan, Synthesize, Draft,
Review) and says so in the output, but it cannot run the deterministic Retrieve fan-out or the
Compile gate. In that mode it does not claim a compile it did not perform, and Format stays gated
behind the checks it can actually run. Install core to get the gate.

## Notes

- Heavy CLI detail lives in `references/core-cli.md`; this skill links there rather than inlining it.
- The pipeline reads ledger events, not full stage transcripts, so a long manuscript does not
  overflow context: each stage summarizes into the ledger and later stages read the summary.
