---
description: Run a pre-submission compliance checklist and report pass or fail with fix instructions
---

# /researcher:submit-ready

Pre-submission compliance check.

## Inputs (gathered conversationally)
Takes no arguments. Claude reads manuscript/config.yaml for the manuscript path and the target journal.
- Target journal: only asked for if config.yaml does not declare one, since the formatting and word count checks need it.

## Behavior
Runs checklist:
1. Evidence-lineage compile gate passes (see below): every claim traces to clean evidence
2. All \cite{} keys resolve in library.bib
3. All bib entries have DOIs or URLs
4. Formatting matches target journal requirements
5. Word count within limits
6. All required sections present (including data availability, COI)
7. Figures in correct format and resolution
8. Cover letter exists
9. Response to reviewers exists (if revision)

Outputs pass/fail report with specific fix instructions for each failure.

## The compile gate is a hard refusal

Submit-ready NEVER reports ready without a passing compile. It runs, when core is available:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core compile --manuscript manuscript/ --json
```

and reads the derived gate state. The gate state is DERIVED from the ledger's `gate` event stream,
never a stored `compiled: true` flag, and it counts only from a compile no older than the newest
manuscript content hash. If the report's verdict is `fail`, or there is no lineage graph and no gate
event, submit-ready reports NOT ready and lists the diagnostics (C001 orphan claim, C002 altered
number, C003 stale evidence, C004 qualifier mismatch, C005 retraction, C006 artifact-code drift)
with their remediation hints. It does not let the other checklist items override this: a manuscript
that is beautifully formatted but cites a retracted paper is not ready.

Only refusal-grade diagnostics block. An `inconclusive` line item (a source that could not be
re-checked) and an `open` item (a claim with only abstract-level evidence, verdict
`insufficient-passage`) are surfaced for the author's attention but are never treated as a
fabrication and never, on their own, the reason for a refusal (D9, D11).

If core is not installed, submit-ready says so plainly and falls back to the citation and formatting
checks it can run with the stdlib tooling, rather than claiming a compile it did not perform.
