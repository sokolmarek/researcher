---
title: Roadmap
description: Where Researcher is headed, what is planned versus shipped, and the projects that inspire the direction.
sidebar:
  label: Roadmap
  order: 4
---

This page is an honest sketch of where Researcher is going, not a changelog of what already works. Everything below is **planned, not shipped**. Treat it as a statement of intent you can hold us to, not a feature list you can rely on today. If a section makes you excited, good. If it makes you want to file an issue, even better.

One thing that will not change: the **plugin stays the primary experience**. Everything on this page is about making the plugin more trustworthy and more portable, not about replacing it with some other product. You should still be able to type "review my paper" at 3 AM and get sensible help.

## The direction in one sentence

Move retrieval off ad-hoc web search and onto a deterministic, multi-source engine that returns canonical records, then wrap every citation and claim in verifiable, reproducible checks.

Today, a lot of discovery leans on general web search. That is flexible, but it is also non-deterministic: ask twice, get two different answers, and neither one hands you a clean DOI. The plan is to make retrieval boring in the best possible way, so the same query returns the same canonical records every time.

## Deterministic multi-source retrieval

The foundation is a retrieval engine that queries real scholarly infrastructure directly rather than scraping search-result pages. The intended sources:

- **OpenAlex** for the works graph and metadata
- **Crossref** for registered DOIs and publisher records
- **Semantic Scholar** for citation-graph data and TLDRs
- **arXiv** for preprints
- **PubMed / Europe PMC** for biomedical coverage
- **Unpaywall** for open-access full-text locations

The engine deduplicates across these sources (the same paper shows up in three of them under three slightly different titles) and returns a single deduplicated, canonical record per work. Deterministic in, deterministic out.

## A four-state citation-existence gate

Once a record is canonical, the next planned layer is a gate that answers a deceptively simple question: does this citation actually exist, and does it say what the draft claims it is? Rather than a binary yes/no, the plan is four honest states:

- **Verified**: the reference resolves to a real record whose metadata matches the citation
- **Mismatch**: a record exists, but authors, year, title, or venue disagree with what was cited
- **Unresolvable**: no matching record could be found in any source
- **Inconclusive**: the sources disagree or coverage is too thin to decide

Alongside the gate, the engine is planned to run **retraction checks** against Retraction Watch data, so a citation to a withdrawn paper gets flagged before it reaches a reviewer instead of after.

## Claim-faithfulness anchoring

Existence is necessary but not sufficient. A paper can be real and still not support the sentence that cites it. The planned claim-faithfulness layer anchors each in-text claim against the **open full text** of its source, checking whether the cited passage actually backs the assertion. When the full text is open, the anchor points at the specific supporting span. When it is not, the tool says so plainly rather than pretending.

This is the difference between "this DOI is valid" and "this DOI supports what you wrote." Both matter. The second is harder.

## An append-only provenance ledger

For any of this to be trustworthy, you have to be able to reconstruct how a conclusion was reached. The plan is an **append-only provenance ledger**: every query, every source hit, every gate decision, every claim anchor gets recorded in an immutable log. Nothing is overwritten; corrections are new entries.

The target is **PRISMA-grade reproducibility**, meaning a systematic-review workflow can export a defensible record of exactly which searches ran, what they returned, and why each item was included or excluded. If a reviewer asks "how did you find these 47 papers," the ledger is the answer.

## Packaging: pip install and an MCP server

The retrieval-and-verification core is the part most worth sharing, so once it is stable the plan is to expose it two ways:

- A **pip-installable package**, so the deterministic engine can be scripted and used in pipelines that have nothing to do with Claude.
- An **MCP server**, so non-Claude tools and other agents can call the same retrieval, gating, and provenance machinery through a standard interface.

The point is that verification should not be locked inside one assistant. If the checks are good, other tools should be able to use them.

## Heavier items, further out

Some things are genuinely hard and deliberately later:

- **Verified RAG over full text with embeddings.** Retrieval-augmented answering grounded in the actual full text of open papers, with embedding-based retrieval and reranking, so answers cite specific passages rather than gesturing at whole papers. This is the most ambitious item here and the least certain.
- **Multi-provider model routing.** Routing different subtasks to different models based on the job, extending today's Opus-for-reasoning, Sonnet-for-code split into something configurable across providers.

These are on the horizon, not around the corner. Listing them is a promise about direction, not a delivery date.

## What this does not change

To restate the important part: the plugin is the product. The roadmap makes the plugin's retrieval more deterministic, its citations more verifiable, and its core more portable. It does not turn Researcher into a black box, and it does not relax the constraints you already rely on. Researcher stays an assistant, never a co-author, and it never fabricates citations or invents data. If anything, the whole point of this work is to make that promise mechanically enforceable instead of merely stated.

## Standing on other people's shoulders

None of this direction is invented from scratch. It is shaped by projects that got there first, and it is worth naming them:

- **PaperQA2** for the reference design of deterministic, verified retrieval over scientific full text.
- **STORM / Co-STORM** for multi-perspective question-asking to grounded long-form synthesis.
- **Elicit** for systematic screening and structured evidence extraction.
- **Scite** for Smart Citations and supporting/contrasting/mentioning classification.
- **academic-research-skills** for the shape of a human-in-the-loop, integrity-first research assistant.

The full accounting, including data sources, dependencies, and the licensing terms under which ideas were re-implemented as original code, lives in [CREDITS.md](https://github.com/sokolmarek/researcher/blob/main/CREDITS.md). Credit is cheap and gratitude is free, unlike journal APCs.
