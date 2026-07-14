---
description: Parse reviewer comments into a prioritized revision roadmap and save artifacts to manuscript/revisions
argument-hint: "<round: R1|R2|R3>"
---

# /researcher:revise

Start revision workflow from reviewer comments.

## Inputs (gathered conversationally)
- Round: R1, R2, or R3 (default: R1). State it in your message or Claude asks.
- Comments source: paste, file, or Word doc. State how you'll provide reviewer comments or Claude asks.

## Behavior
1. Parses reviewer comments into structured format
2. Creates revision roadmap (categorized, prioritized)
3. Routes to the revision-management skill for tracked changes
4. Routes to the response-to-reviewers skill for the response document
5. Saves all artifacts to manuscript/revisions/R{n}/
