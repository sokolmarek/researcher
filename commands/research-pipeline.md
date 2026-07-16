---
description: Run the staged research pipeline from planning through formatting, with a compile gate before format and a human checkpoint at every stage
argument-hint: "<research question>"
---

# /researcher:research-pipeline

The end-to-end research pipeline, built around the evidence-lineage compile gate.

## Inputs (gathered conversationally)
- Research question: the question or working title to build the manuscript around. State it in your message, or Claude asks.
- Manuscript folder: defaults to manuscript/. Claude asks only if more than one is present.
- Starting stage: defaults to Plan. State a later stage (for example Draft) to resume an in-progress manuscript.

## Behavior
Routes to the research-pipeline skill, which runs the stages in order:

Plan, Retrieve, Synthesize, Draft, Review, Compile, Format.

A human checkpoint follows EVERY stage by default: the pipeline presents the stage output and waits
for the author before moving on. Format is reachable only from a passing Compile; a failing compile
routes back to Draft or Review with the diagnostics, and no stage rewrites a prior ledger record
(the ledger is append-only). Automation flags between stages are documented in the skill but stay
disabled, so the human-in-the-loop default holds.
