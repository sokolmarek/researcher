---
description: Run a systematic review end to end over the provenance ledger, with a locked protocol, dual screening, and derived PRISMA counts
argument-hint: "<review question or topic>"
---

# /researcher:systematic-review

The end-to-end systematic-review workflow, built on the append-only provenance ledger and PRISMA 2020
as the reporting layer (not the architecture).

## Inputs (gathered conversationally)
- Review question: the question or topic the review answers. State it in your message, or Claude asks.
- Run id: an identifier for this review, reused across every stage. Claude proposes one if you do not
  give one.
- Screeners: the ids of the independent screeners (two by default). Single-screener mode is available
  but is disclosed in the report as a limitation.

## Behavior
Routes to the systematic-review skill, which runs the stages in order over the ledger:

1. Draft the protocol (question, eligibility profile as PICO, PECO, or SPIDER, per-database search
   strategies, planned synthesis) and LOCK it: the lock hashes the content, and no screening starts
   before a lock exists.
2. Execute each database strategy and record its VERBATIM query string as a retrieval event, with
   responses snapshotted.
3. Deduplicate via the kernel and record each collapse.
4. Screen in two independent streams (title-abstract, then full-text) with BLINDED adjudication: the
   adjudicator sees the record and the eligibility profile, never the other screener's vote. Cohen's
   kappa is derived and reported.
5. Optionally prioritize the screening queue (order only, no auto-exclusion), if you opt in.
6. Identity-verify every included reference; an `inconclusive` entry is flagged for review, never
   dropped as fabricated.
7. Hand off to extraction (extraction-tables), appraisal (RoB 2 and GRADE worksheets), and synthesis
   (meta-analysis via statistical-analysis).
8. Report: the PRISMA 2020 flow and checklist, DERIVED from the ledger, plus the full amendment trail
   (PRISMA 2020 item 24b).

Humans make every screening and appraisal decision; the workflow organizes and records them.
Refusal-grade findings (`unresolvable`, `mismatch`, `retracted`, `contradicted`) block; `inconclusive`
and `insufficient-passage` stay open items. Without the `core/` kernel, the workflow degrades to an
author-maintained log and says plainly that the derived counts and the blinding guarantee were not
produced.
