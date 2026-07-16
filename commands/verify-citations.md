---
description: Audit every citation in a manuscript for existence and faithfulness, and refuse a clean verdict on any refusal-grade finding
argument-hint: "<bib file or manuscript path>"
---

# /researcher:verify-citations

Whole-manuscript citation integrity audit.

## Inputs (gathered conversationally)
- Target: a `.bib` file or a manuscript folder. Defaults to manuscript/references/library.bib. State it in your message, or Claude asks.
- Level: existence only, or existence plus faithfulness (default: both). The faithfulness audit needs core and open-access full text.

## Behavior
Routes to the citation-audit skill, which runs two levels:

1. **Existence gate.** Core `verify-bib` and `status` over every entry: the four-state identity
   verdict, the publication status, and the accessibility field. Refusal-grade only on
   `unresolvable`, `mismatch`, or `retracted`.
2. **Claim-faithfulness audit.** Each claim-citation pair anchored against the source's passages
   through the M2 index, with a supporting quote, a passage locator, and a metadata match.
   Refusal-grade only on `contradicted`; `insufficient-passage` is an open item.

The manuscript is marked clean only with zero refusal-grade findings. `inconclusive`,
`expression-of-concern`, and `insufficient-passage` are surfaced as open items but do not, on their
own, block. Every verdict names the layer it was verified against. Without core, the existence gate
falls back to the stdlib bib validator and the faithfulness audit is reported as not run.
