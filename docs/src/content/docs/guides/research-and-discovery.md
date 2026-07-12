---
title: "Guide: Research & Discovery"
description: The six skills that find, verify, and situate the literature.
sidebar:
  label: Research & Discovery
  order: 1
---

Six skills cover everything from "what has been done" to "where the gap is", and every one of them insists on real, resolvable citations.

## literature-search

Multi-source search across OpenAlex, Crossref, Semantic Scholar, arXiv, PubMed, and Scite. Deduplicates by DOI then by title, ranks by relevance and citation count, and (in systematic mode) records a PRISMA flow with a reproducible search-provenance record.

**Trigger it:** "Do a systematic literature search on X", "Find recent papers on Y".

## research-convergence

Not just finding papers, but converging on an argument. Three modes: Socratic (interactive), Full Research (deep, multi-round), and Flash (a quick scan).

## fact-checking

Verifies a claim against the literature and returns a verdict (Supported, Contested, Partially Supported, or Unsupported) with the evidence behind it. It will return **Unsupported** rather than invent a source.

**Trigger it:** "`/fact-check <claim>`".

## sota-finder

Tracks state-of-the-art results for a benchmark. Every number in the table is traced to the paper that reported it; leaderboard claims that cannot be traced are marked unverified.

**Trigger it:** "`/sota <benchmark>`".

## research-gaps

Systematically identifies methodological, empirical, and theoretical gaps, and ranks them by impact potential, backing each with the searches that failed to find prior work.

## citation-context

Classifies how a paper is cited (supporting, contrasting, or mentioning) and audits your manuscript for sources you may have misrepresented.

## See it in action

The [literature review recipe](/researcher/cookbook/literature-review/) runs a systematic search and a fact-check end to end, and the [`examples/research-verification/`](https://github.com/sokolmarek/researcher/tree/main/examples/research-verification) folder has the full worked output.
