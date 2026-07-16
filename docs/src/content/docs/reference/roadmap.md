---
title: Roadmap
description: Where Researcher is headed, what is planned versus shipped, and the projects that inspire the direction.
sidebar:
  label: Roadmap
  order: 4
---

This page is an honest sketch of where Researcher is going, organized as versioned milestones. Milestones 1 and 2 have **shipped**; everything after them is **planned, not shipped**. Treat the later milestones as a statement of intent you can hold us to, not a feature list you can rely on today. If a section makes you excited, good. If it makes you want to file an issue, even better.

One thing that will not change: the **plugin stays the primary experience**. Everything on this page is about making the plugin more trustworthy and more portable, not about replacing it with some other product. You should still be able to type "review my paper" at 3 AM and get sensible help.

## The direction in one sentence

Move retrieval off ad-hoc web search and onto a deterministic, multi-source engine that returns canonical records, then wrap every citation and claim in verifiable, reproducible checks.

Today, a lot of discovery leans on general web search. That is flexible, but it is also non-deterministic: ask twice, get two different answers, and neither one hands you a clean DOI. The plan is to make retrieval boring in the best possible way, so the same query returns the same canonical records every time.

Just as important is what the direction is not: a larger skill count. The goal is a measured, trustworthy core. From Milestone 2 onward, every new capability lands with its own benchmark and ships only when that benchmark is green. A feature that cannot prove itself waits.

## Milestone 1 (0.2.0, shipped): release correctness

The current release is not about new surface area. It is about making what already exists correct and honestly described:

- **Namespaced commands.** Installed plugin commands always carry the plugin prefix: `/researcher:review-paper`, `/researcher:fact-check`, `/researcher:submit-ready`, and the rest. The bare forms are not valid for an installed plugin.
- **Honest capability docs.** The documentation now says what actually runs. External model reviewers (OpenAI, Gemini, Ollama) in the peer-review skill are documented integration points with no dispatch code yet. The scholar scraper fetches metadata and abstracts from Semantic Scholar; full-text style metrics need files you provide locally.
- **A real brace-aware BibTeX parser** in place of regex guessing.
- **A commit-tree citation guard** that blocks commits containing dangling `\cite` keys.
- **Working journal lookup.** `scripts/journal-lookup.py` searches the bundled database of 16 journal profiles and prints a suggestion on a miss. It does not search the web.
- **Corrected example statistics** in the worked examples.
- **The shipped `build-docx.js`.** A Node script built on the docx library that generates headings, paragraphs, and lists from `sections/*.md`. Tracked changes, comments, and table emission are specified but not implemented yet.
- **Figure style presets** (default, nature, ieee) in `references/figure-styles.md`, plus the new image-prompt-crafting skill, which brings the skill count to 29.
- **Hardened CI.**

## Milestone 2 (0.3.0, shipped): the evaluation-first evidence kernel

The deterministic core (`core/`) is real. It was built evaluation-first: the benchmarks landed with the code, and they are published in [`evals/BENCHMARKS.md`](https://github.com/sokolmarek/researcher/blob/main/evals/BENCHMARKS.md) with the weak axis and the red gate left in.

Installing it is **optional**. Without it, the plugin behaves exactly as it did in 0.2.0. See [Installation](/researcher/start/installation/).

The foundation is a retrieval engine that queries real scholarly infrastructure directly rather than scraping search-result pages, with **response snapshots** so every run replays deterministically. Eight sources ship:

- **OpenAlex** for the works graph and metadata
- **Crossref** for registered DOIs, publisher records, and update notices
- **DataCite** for datasets, software, and other non-article research outputs
- **Semantic Scholar** for citation-graph data and TLDRs
- **arXiv** for preprints
- **PubMed** for biomedical coverage
- **Unpaywall** for open-access full-text locations
- **OpenCitations** for citation-graph edges

The engine deduplicates across these sources (the same paper shows up in three of them under three slightly different titles) and returns a single canonical record per work. On 210 labeled pairs it made no merge or split errors.

On top of retrieval sit **four independent verification axes**. They are reported side by side and never folded into one verdict, because a paper can be entirely real and also retracted:

- **Reference identity**: does the reference resolve to a real record whose metadata matches? Not a binary yes/no, but four honest states: **verified**, **mismatch** (a record exists, but the metadata disagrees), **unresolvable** (no matching record in any source), and **inconclusive** (a source errored, or coverage is too thin to decide).
- **Publication status**: **current**, **corrected**, **retracted**, or **expression-of-concern**, derived from Crossref's `update-to` notices cross-checked against OpenAlex's retraction flag. Accuracy 121/121 on the gold set.
- **Claim faithfulness**: a paper can be real and still not support the sentence that cites it. This axis anchors each claim against the open full text of its source. **It ships as a lexical baseline and it is weak** (see below). The honest version of this axis is the hardest thing on this page.
- **Accessibility**: can the cited source be reached, and at what depth? When the full text is not open, the tool says so plainly rather than pretending.

**The number that matters most is zero.** Only `unresolvable` and `mismatch` can accuse anyone of a bad citation; `inconclusive` never does. On 100 real references, the kernel accused **none** of them (95% Wilson [0.000, 0.037]), while still catching every one of the 25 invented references. That asymmetry is deliberate: telling an honest author that a paper they read and cited correctly does not exist is the worst thing this system can do, so thin or dirty evidence always falls to `inconclusive` rather than to a refusal.

**Where it is weak, said plainly.** Claim faithfulness is BM25 plus overlap heuristics, and a lexical method cannot read: it scores 12 of 26 overstatements as fully supported, because an overstatement reuses nearly all the words of the passage it overstates. It answers 75% of claims and abstains correctly on every document with no open full text. That measured rate is precisely the trigger condition for the deferred semantic layer below. The retrieval axis is also short of its gate: a daily OpenAlex search budget ran out during snapshot recording, so 22 of 55 known-item queries are reported as skipped and the benchmark runner exits non-zero rather than going green over a half-measured set.

Two more pieces round out the kernel. **Lexical passage retrieval** locates the supporting span inside open full text and gives every verdict a stable passage ID to point at. And **hardened provenance** records every query and every decision in an append-only ledger where nothing is overwritten, with PRISMA counts derived by aggregation rather than stored. If a reviewer asks "how did you find these 47 papers," the ledger is the answer.

## Milestone 3 (0.4.0): the evidence-lineage compiler

Once the kernel can verify evidence, the next step is to make manuscripts compile from it. In this milestone, every claim and every number in a draft traces to one of two origins: a span in an external source, or an internal experiment run. A **compile gate** then detects what does not trace:

- **Orphan claims** with no evidence behind them
- **Altered numbers** that no longer match their source or their run
- **Stale evidence** that has been superseded since it was cited
- **Retractions** of works the draft still relies on
- **Artifact drift**, where the code or data behind a result has changed since the result was written down

The output is a **research passport**: an RO-Crate / W3C PROV export of the full evidence lineage, so anyone can reconstruct how each conclusion was reached.

## Milestone 4 (0.5.0): the systematic-review vertical

With verified retrieval and evidence lineage in place, the first full vertical is systematic reviews: **protocol locking** before screening begins, **dual independent screening**, risk-of-bias assessment with **RoB 2**, certainty grading with **GRADE**, **meta-analysis**, and **living reviews** that update as new evidence arrives. **PRISMA 2020** is the reporting layer over all of it, so a review can export a defensible record of exactly which searches ran, what they returned, and why each item was included or excluded.

## Milestone 5 (1.0.0): production completeness

The last milestone before 1.0.0 is everything a production tool owes its users:

- **Private mode** for work that must not leave the machine
- **Prompt-injection defenses** for content fetched from the open web
- **Round-trip format tests** so LaTeX and DOCX output survives editing cycles
- **ORCID, ROR, and CRediT** support for author, institution, and contribution metadata
- **SBOM and signed releases**
- **A pip-installable package on PyPI plus a thin MCP server**, so the deterministic engine can be scripted in pipelines that have nothing to do with Claude, and non-Claude tools can call the same retrieval, gating, and provenance machinery through a standard interface. Verification should not be locked inside one assistant. If the checks are good, other tools should be able to use them.
- **Three-OS CI** (Linux, macOS, Windows)

## Deferred, deliberately

Some things are genuinely hard and intentionally later than any numbered milestone:

- **The semantic RAG layer.** Embeddings, a vector store, and reranking layered on top of Milestone 2's lexical passage index, so answers cite specific passages rather than gesturing at whole papers. This is the most ambitious item here and the least certain. It is deliberately not in the kernel: what the kernel ships is the lexical floor, and this layer's start trigger is the measured faithfulness rate that floor produces, which is now a published number rather than a hunch.
- **Multi-provider model routing.** Routing different subtasks to different models based on the job, extending today's agent-level model pinning (the code, visualization, and formatting agents run on Sonnet) into something configurable across providers.

These are on the horizon, not around the corner. Listing them is a promise about direction, not a delivery date.

## What this does not change

To restate the important part: the plugin is the product, and the goal is a measured, trustworthy core, not a larger skill count. The roadmap makes the plugin's retrieval more deterministic, its citations more verifiable, and its core more portable. It does not turn Researcher into a black box, and it does not relax the constraints you already rely on. Researcher stays an assistant, never a co-author, and it never fabricates citations or invents data. If anything, the whole point of this work is to make that promise mechanically enforceable instead of merely stated.

## Standing on other people's shoulders

None of this direction is invented from scratch. It is shaped by projects that got there first, and it is worth naming them:

- **PaperQA2** for the reference design of deterministic, verified retrieval over scientific full text.
- **STORM / Co-STORM** for multi-perspective question-asking to grounded long-form synthesis.
- **Elicit** for systematic screening and structured evidence extraction.
- **Scite** for Smart Citations and supporting/contrasting/mentioning classification.
- **academic-research-skills** for the shape of a human-in-the-loop, integrity-first research assistant.

The full accounting, including data sources, dependencies, and the licensing terms under which ideas were re-implemented as original code, lives in [CREDITS.md](https://github.com/sokolmarek/researcher/blob/main/CREDITS.md). Credit is cheap and gratitude is free, unlike journal APCs.
