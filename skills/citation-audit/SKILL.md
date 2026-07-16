---
name: citation-audit
description: "Audit every citation in a manuscript for existence and for faithfulness. Triggers when user says: 'audit my citations', 'verify all citations', 'check every reference', 'citation integrity check', 'do my sources exist', 'are my citations real', 'audit the bibliography', 'verify citations before submission', 'citation audit'. Runs a two-level check: an existence gate (does each reference resolve, and is it retracted) and a claim-faithfulness audit (does each cited passage actually support the claim). Use this for a whole-manuscript integrity pass; for one claim, use fact-checking; for cleaning a .bib, use citation-management."
---

# Citation Audit

The integrity workhorse. It answers two questions about a manuscript's citations, in order: do the
sources exist, and do they say what the manuscript claims they say. It refuses to mark a manuscript
clean on any refusal-grade finding, and every verdict it reports names the layer it was verified
against.

Invoked as `/researcher:verify-citations`. It is also what the compile gate's C004 and C005 checks
call into for re-verification.

## CRITICAL INTEGRITY RULE

The worst thing this system can do is tell an honest author that a real citation they read and cited
correctly does not exist. So the four-state identity verdict is consumed here, never a boolean (D9),
and only two identity states are refusal-grade: `unresolvable` (every queried source returned a clean
negative) and `mismatch` (a resolving source disagrees on the metadata). `inconclusive` is NEVER
refusal-grade: it means a source was rate-limited, or only one index holds the paper, and neither is
evidence of fabrication. On the status axis, `retracted` is refusal-grade; on the faithfulness axis,
`contradicted` is. Everything else is surfaced for the author, not used to accuse them.

Canonical copy: `references/integrity-constraints.md`.

## Level 1: the existence gate

For every entry in the manuscript's `.bib`, run the core verify-bib and status commands:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-bib manuscript/references/library.bib --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core status manuscript/references/library.bib --json
```

Read, per entry:

- `verify-bib`: the axis (a) identity verdict (`verified` / `mismatch` / `unresolvable` /
  `inconclusive`) with its per-source outcomes, plus the axis (b) status and axis (d) accessibility
  fields.
- `status`: the axis (b) verdict (`current` / `corrected` / `retracted` / `expression-of-concern`).

An entry is refusal-grade only if its identity is `unresolvable` or `mismatch`, or its status is
`retracted`. Report those as blocking. Report `inconclusive` entries and `expression-of-concern`
entries as open items for the author to review; they do not block by themselves.

## Level 2: the claim-faithfulness audit

For each claim that cites a source, anchor the claim against the source's actual text through the M2
passage index, with three layers of anchor:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages index <doi> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core faithfulness "<claim>" --doc <doi> --json
```

The three anchors, all of which a clean pairing carries:

1. A supporting quote: the exact passage text the verdict rests on.
2. A passage locator: the stable passage id (and page coordinates) so the quote can be found again.
3. A retrieved-metadata match: the source the passage came from is the source the claim cites.

The faithfulness verdict is `supported`, `partial`, `contradicted`, or `insufficient-passage`. Only
`contradicted` is refusal-grade. `insufficient-passage` (the source has no retrievable full text, so
the claim degraded to abstract level) is an OPEN ITEM, never clean and never a refusal (D11), and the
report says the claim was verified at abstract level, not full text.

Be honest about the layer: axis (c) is a lexical baseline (measured coverage 0.750). It can call an
overstatement `supported`, so a `supported` verdict here is a floor, not a proof, and the report says
so. A human confirms the borderline pairings.

## The verdict

The manuscript is marked clean only when there are zero refusal-grade findings at either level:
zero `unresolvable`, zero `mismatch`, zero `retracted`, zero `contradicted`. Open items
(`inconclusive`, `expression-of-concern`, `insufficient-passage`) are listed for the author but do
not by themselves prevent a clean verdict; the report states how many are outstanding.

Every claim verdict states the layer it was verified against (abstract vs full-text), and every
refusal names the specific entry and the reason.

## Standing regression case

The seeded fake in `examples/research-verification/citation-audit.md` (guarded by the
`expect-unresolvable` marker, D8) must always come back `unresolvable`. If it ever resolves, the
audit is broken, not the example.

## Degradation (D3)

Without `uv` or `core/`, the audit falls back to `scripts/bib-validator.py` for the existence gate
(the stdlib brace-aware parser plus CrossRef checks) and states plainly that the faithfulness audit
needs core and was not run, rather than reporting a clean bill it did not earn. Scite MCP, when
connected, enriches the existence gate with smart-citation context.
