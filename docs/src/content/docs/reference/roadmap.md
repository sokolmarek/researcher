---
title: Roadmap
description: Where Researcher is headed, what is planned versus shipped, and the projects that inspire the direction.
sidebar:
  label: Roadmap
  order: 4
---

This page is an honest sketch of where Researcher has gone and where it is headed, organized as versioned milestones. Milestones 1 through 5 have **shipped**, and the project is now at **1.0.0**. What is left is the **deferred** work below: post-1.0, carrying explicit start triggers rather than dates. Treat that section as a statement of intent you can hold us to, not a feature list you can rely on today. If a section makes you excited, good. If it makes you want to file an issue, even better.

One thing that will not change: the **plugin stays the primary experience**. Everything on this page is about making the plugin more trustworthy and more portable, not about replacing it with some other product. You should still be able to type "review my paper" at 3 AM and get sensible help.

## The direction in one sentence

Move retrieval off ad-hoc web search and onto a deterministic, multi-source engine that returns canonical records, then wrap every citation and claim in verifiable, reproducible checks.

Today, a lot of discovery leans on general web search. That is flexible, but it is also non-deterministic: ask twice, get two different answers, and neither one hands you a clean DOI. The plan is to make retrieval boring in the best possible way, so the same query returns the same canonical records every time.

Just as important is what the direction is not: a larger skill count. The goal is a measured, trustworthy core. From Milestone 2 onward, every new capability lands with its own benchmark and ships only when that benchmark is green. A feature that cannot prove itself waits.

## Milestone 1 (0.2.0, shipped): release correctness

Milestone 1 was not about new surface area. It was about making what already existed correct and honestly described:

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

## Milestone 3 (0.4.0, shipped): the evidence-lineage compiler

The kernel can verify evidence; this milestone makes manuscripts **compile** from it. Every claim and every number in a draft traces to one of two origins: a qualified span in an external source, or an internal experiment run. `researcher compile` walks that lineage graph and fails the gate on anything that does not trace, reporting one diagnostic per defect class:

- **C001 orphan claim**: a claim with no evidence edge behind it
- **C002 altered number**: a generated artifact whose content hash no longer matches its manifest
- **C003 stale evidence**: a source snapshot superseded, or a publication status flipped, since the edge was created
- **C004 qualifier mismatch**: the claim's population, intervention, or outcome does not match the cited source's
- **C005 retraction**: a cited source now retracted or under an expression of concern
- **C006 artifact-code drift**: the code or data behind a result has changed since the result was written down

The asymmetry that governs the kernel governs the gate too: a source that errors during a compile-time re-check is **inconclusive**, never a defect, and a claim with only abstract-level evidence is an open item, never a refusal. Only C001 through C006 on clean evidence are refusal-grade, so a downed index can never fail your build. The gate is replayable: two runs from the same worktree, snapshots, and parser version produce a byte-identical report. A seeded-defect fixture carrying exactly one instance of each of the six classes proves the gate fires all six codes and passes a clean sibling with zero diagnostics.

The output is a **research passport**: a `researcher passport --format ro-crate|prov-jsonld` export of the full evidence lineage, as an RO-Crate 1.1 or W3C PROV-JSON-LD record, so anyone can reconstruct how each conclusion was reached.

This milestone also brought six existing skills onto the deterministic backend (each shipped only because the benchmark gating it is green) and added two new ones: a citation-audit skill and a staged research pipeline that runs Plan through Format with a human checkpoint after every stage and Format reachable only from a passing compile. The observed counts are now **31 skills, 9 agents, and 13 commands** (up from 29 and 11), and the pooled trigger eval holds at 99.4% recall and a 6.5% false-trigger rate with the two new skills added. As always from Milestone 2 onward, those counts are reported after the fact, never targeted.

## Milestone 4 (0.5.0, shipped): the systematic-review vertical

With verified retrieval and evidence lineage in place, the first full vertical is systematic reviews: a workflow you could defend to a methodologist. The load-bearing decision is what **PRISMA 2020** is not. It is not the architecture. The architecture is the append-only event ledger from Milestone 2, and the PRISMA 2020 flow diagram and checklist are **derived** views over it, recomputed by aggregating events and never stored. The proof is blunt: delete one screening event and the derived flow changes. A stored count could not do that.

Four core modules sit on the ledger:

- **Protocol locking** (`protocol lock|amend|check`). Locking hashes the protocol (question, eligibility profile, per-database strategies, planned synthesis) and binds every later event to that hash. A deviation is never an edit: an amendment is its own event that bumps the protocol version, so the ledger keeps the locked original plus the full amendment trail. Editing the protocol file after lock without an amendment is caught as a hash mismatch, which is the check that makes "locked" mean something.
- **Dual independent screening with blinded adjudication** (`screen decide|conflicts|kappa`). Two screening streams. When they disagree, the conflict goes to an adjudicator who sees only the record and the eligibility profile, never the two votes, so the second opinion is genuinely blind. That blinding is verified end to end through the real CLI, not asserted: an integration test inspects the adjudication payload and confirms no vote leaks into it. Cohen's kappa between streams is derived from the ledger, and an optional ranked queue reorders the remaining records without ever auto-excluding one.
- **The PRISMA 2020 reporting layer** (`prisma flow|checklist`). The full flow (identified, deduplicated, screened, excluded with reasons, retrieved, assessed, included) and the checklist, derived purely by aggregating ledger events.
- **Living reviews** (`monitor status`). Saved verbatim searches, a diff of new records against the seen list on rerun, feeding a fresh screening batch under the same locked protocol. That is what makes a review living rather than redone.

Methodology comes from the Cochrane toolkit used alongside PRISMA 2020: **RoB 2** risk-of-bias worksheets per randomized study and **GRADE** certainty grading per outcome, both human-completed with no automated scoring, and both hashed into the ledger so the report can prove which appraisal version fed the conclusions. **Meta-analysis** binds every pooled number to a committed script and its inputs, so a hand-edited estimate fails the Milestone 3 compile gate.

This milestone added four new skills, each gated before it shipped: `systematic-review`, `extraction-tables`, `contradiction-detection`, and `literature-monitoring`, plus two commands (`/researcher:systematic-review` and `/researcher:watch-topic`). The extraction skill is gated by a new benchmark of 147 real labeled cells across six column types: measured location accuracy is 109/119 (0.916, 95% Wilson [0.852, 0.954]), with the weak columns named (population 0.778, metric_name 0.722), a "not reported" precision of 25/30 (0.833), and a fabrication risk of 3/28 (0.107). The benchmark measures core's anchoring floor, not Claude's judgment, and it runs offline with byte-identical repeats. The observed counts are now **35 skills, 9 agents, and 15 commands** (up from 31 and 13), and the pooled trigger eval holds at 95.4% recall and a 5.7% false-trigger rate with all 35 skills. As always from Milestone 2 onward, those counts are reported after the fact, never targeted.

## Milestone 5 (1.0.0, shipped): production completeness

The last milestone is everything a production tool owes its users, and it hardens the boundary around the core rather than growing it. No skills were added by design: the observed counts hold at **35 skills, 9 agents, and 15 commands**, and that is the point.

- **Offline mode** for work that must not leave the machine. `--offline` (or `RESEARCHER_OFFLINE=1`) makes every network-touching command answer exclusively from snapshots and the response cache; a miss is a typed `offline-miss`, never a silent live call. It reuses the Milestone 2 snapshot layer rather than building a second store, so the mechanism that makes the benchmarks replayable makes private work airtight. The disclosure that pairs with it is exact: a per-connector data-egress section names every outbound host and identifier, and manuscript prose never leaves the machine through core.
- **Prompt-injection defenses, verified rather than asserted.** Fetched paper text is untrusted input, so the core sanitizes it and every skill quotes it only inside a labeled untrusted-content fence whose one rule is that instructions inside the fence are data. An injection eval replays payload-carrying fake records through search, verification, and faithfulness and proves two things: the verdicts do not move versus the payload-free twin, and no payload escapes the fence. That certifies the known payload classes, not general immunity, and SECURITY.md invites the ones it does not yet model.
- **Licensing and retention, with a no-redistribution invariant.** The cache expires content by class (open-access locations, extracted full text, and metadata each on their own clock), while the content-addressed eval snapshot store is exempt because it gates the benchmarks. Cached full text stays in the user cache: it never enters a manuscript and never enters a passport, which carries hashes and passage IDs, not article text.
- **Round-trip format tests** so bibliographic output survives editing cycles. CSL-JSON is canonical; RIS, a JATS reference list, and BibTeX are emitters over it, and a round-trip eval publishes a per-format loss table so the gaps are named rather than discovered downstream.
- **ORCID, ROR, and CRediT** support for author, institution, and contribution metadata: validated by checksum, pattern, and the 14-role taxonomy, optional, and never fabricated. An invalid identifier is rejected, not guessed.
- **Accessibility.** Figure alt text describing data content is a required output of every visualization-family skill, shared across preset variants; the DOCX generator writes it into image properties, and the freshness eval checks its presence.
- **SBOM and signed releases.** Every GitHub Release carries CycloneDX SBOMs and Sigstore keyless signatures (OIDC, no stored keys), verifiable with a documented `cosign verify-blob` command.
- **A pip-installable package plus a thin MCP server**, installed from the repo (deliberately not distributed on PyPI: the plugin is the distribution), so the deterministic engine can be scripted in pipelines that have nothing to do with Claude, and non-Claude tools can call the same retrieval, gating, and provenance machinery through a standard interface. Verification should not be locked inside one assistant. If the checks are good, other tools should be able to use them.
- **Three-OS CI** (Linux, macOS, and Windows), with macOS added as a non-gating leg first and promoted once green.

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
