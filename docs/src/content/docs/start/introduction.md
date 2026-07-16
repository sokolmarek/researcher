---
title: Introduction
description: What Researcher is, what it refuses to do, and the philosophy behind it.
sidebar:
  order: 1
---

The academic writing workflow is too long, too fragmented, and too lonely. You have a research question on Monday, a literature review due on Friday, a methods section that will not write itself, reviewer comments that question your existence, and a formatting guide that was clearly written by someone who hates you.

Researcher is the assistant that absolutely does not understand what you are going through (it is, after all, just an AI that has never once cried in the library stacks), but it will still help you claw your way out.

## What it is

A Claude Code and Cowork plugin that covers the full research pipeline:

```
Brainstorm -> Literature Search -> Research Gaps -> Experiment Design
    -> Statistical Planning -> Implementation -> Manuscript Drafting
    -> Visualization -> Citation Management -> Peer Review -> Revision
    -> Journal Selection -> Formatting -> Submission
```

It ships **35 skills**, **9 orchestration agents**, and **15 slash commands**, plus connectors to the major bibliographic sources. Output is LaTeX-first and Word-compatible.

## What it refuses to do

- **It will not fabricate citations.** Every reference must come from an actual source and resolve.
- **It will not invent data.** Results describe only actual results; illustrative data is always labeled.
- **It will not use em dashes** in generated academic text.
- **It will not pretend** to understand your domain better than you do.

## Philosophy

1. **Assistant, not author.** It guides, assists, and handles logistics. It does not replace your expertise or your judgment. Every claim needs your verification.
2. **Integrity first.** What runs today: a citation commit guard that blocks commits with dangling `\cite` keys, DOI validation and retraction flags, LaTeX compile checks before delivery, and refusal-grade constraints inlined in every skill that produces cited content. Multi-index reference verification (the four-state identity gate) shipped in 0.3.0 and is measured in `evals/BENCHMARKS.md`; the evidence-lineage compiler (0.4.0) and the systematic-review vertical (0.5.0) are built on top of it.
3. **Your voice, amplified.** Style calibration learns how *you* write, so drafts sound like a better-rested version of you, not a robot.
4. **LaTeX-first, Word-compatible.** Because some of us chose suffering and some of us had it chosen for us by our collaborators.
5. **Token-smart.** Code and formatting tasks route to a smaller model; research thinking and writing use the larger one. Your budget goes further.

Ready? Head to [Installation](/researcher/start/installation/).
