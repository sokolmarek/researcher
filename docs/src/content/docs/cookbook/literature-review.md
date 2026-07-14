---
title: Literature review and fact-check
description: Run a systematic multi-source literature search with a PRISMA flow, then fact-check a claim against the sources you found.
sidebar:
  label: Literature review
  order: 1
---

Two moves make up most of a related-work section: find the papers, then check that what you are about to write about them is actually true. This recipe does both, back to back, on the running scenario of self-supervised learning for ECG arrhythmia classification evaluated on PTB-XL. The papers, DOIs, quotes, and four (genuinely disagreeing) fact-check verdicts below are all real and were retrieved. The hit counts and PRISMA counts are illustrative, not retrieved, and are labeled as such where they appear.

## 1. Search

Type this to trigger the `literature-search` skill (no slash command needed, the phrasing matches):

> Do a systematic literature search on self-supervised learning for ECG arrhythmia classification. I want a PRISMA-style flow, deduplicated results across databases, and the top papers ranked by relevance. This is for the introduction and related-work of a methods paper.

During elicitation the skill agrees on a scope before it dispatches anything: three concept groups (self-supervised OR contrastive OR representation learning; ECG OR electrocardiogram; classification OR arrhythmia OR diagnosis), a 2019 to 2026 window, English only, and five sources (OpenAlex, Crossref, Semantic Scholar, arXiv, PubMed).

What the multi-source flow produces:

- Per-source query strings and raw hit counts, not one opaque web search. The illustrative counts here sit on the order of 214 hits on OpenAlex, 88 on Semantic Scholar, 63 on arXiv, 57 on Crossref, and 41 on PubMed.
- Deduplication by DOI first, then by normalized-title similarity at or above 0.90, so the same paper indexed three ways collapses to one record.
- A PRISMA flow whose counts reconcile end to end, identification through inclusion (illustrative counts, not retrieved):

```
Identification
  Records identified across 5 sources ............... 463
  Duplicate records removed (by DOI, then title) .... 171
Screening
  Records screened (title + abstract) ............... 292
  Records excluded (off-topic, no ECG, no SSL) ...... 241
Eligibility
  Full-text / abstract assessed for eligibility ..... 51
  Excluded (no downstream classification task) ...... 34
Included
  Studies included in synthesis ..................... 17
```

- A machine-readable provenance record written to `manuscript/provenance.json` storing every count and the dedup method, which is enough to redraw the PRISMA flow and enough for `/researcher:submit-ready` to check it later. Volatile hit counts live there, not in prose that would silently go stale. It is an aggregate summary and not yet a replayable record: it holds no record identifiers, no response snapshots, and no per-record screening decisions, so a reader cannot reproduce the search from it. The per-record event ledger that would make a run replayable is planned, not implemented (see the [roadmap](/researcher/reference/roadmap/)).

:::caution[Provenance: those counts are illustrative]
The per-source hit counts and the PRISMA counts above were **not retrieved**. They show the shape of the flow and the arithmetic it has to satisfy (each stage reconciles with the one before it), at a plausible scale. Your own run produces its own numbers, and index churn makes them drift between runs. Everything else on this page, every paper, DOI, quote, and reported figure, was retrieved and verified. The [worked example](https://github.com/sokolmarek/researcher/blob/main/examples/research-verification/literature-search-prisma.md) labels each number the same way.
:::

A couple of the top real papers from the ranked included set:

- Mehari and Strodthoff (2022), *Self-supervised representation learning from 12-lead ECG data*, Computers in Biology and Medicine, [10.1016/j.compbiomed.2021.105114](https://doi.org/10.1016/j.compbiomed.2021.105114). The first comprehensive SSL assessment on clinical 12-lead ECG, and the direct methods baseline for our scenario.
- Wagner et al. (2020), *PTB-XL, a large publicly available ECG dataset*, Scientific Data, [10.1038/s41597-020-0495-6](https://doi.org/10.1038/s41597-020-0495-6). The dataset (21,837 records, 18,885 patients) that this manuscript evaluates on, and the most common benchmark in the included set. It is not universal: several included works report on CODE, on private clinical cohorts, or on single-lead ambulatory data instead.
- Kiyasseh, Zhu and Clifton (2021), *CLOCS: Contrastive Learning of Cardiac Signals*, ICML, [arXiv:2005.13249](https://arxiv.org/abs/2005.13249). Foundational patient, space, and time contrastive objective.

Every included paper carries a resolvable identifier, and the included set becomes the shared bibliography for the writing steps later in the pipeline.

## 2. Fact-check

Now stress-test the claims you are tempted to write. Type:

> /researcher:fact-check these four claims about self-supervised ECG models against the literature. For each, give a verdict, the evidence, and your confidence.
>
> 1. Self-supervised pretraining on unlabeled ECG can reach classification performance within about one percent of fully supervised training.
> 2. Contrastive self-supervised pretraining consistently outperforms supervised training across ECG tasks.
> 3. Deep neural networks match cardiologist-level performance for arrhythmia detection from the ECG.
> 4. Self-supervised ECG models remove the need for any labeled data to achieve clinical-grade arrhythmia diagnosis.

The point of four claims is that they resolve to four different verdicts. The skill separates supporting from contrasting evidence, quotes the actual reported numbers, and refuses to invent a source to prop up a false statement.

**Supported (Claim 1, confidence High).** Mehari and Strodthoff report that on clinical 12-lead ECG classification their best self-supervised method reaches linear-evaluation performance "only 0.5% below supervised performance," and that fine-tuning yields improvements of "roughly 1%" over purely supervised training (Mehari and Strodthoff, 2022, [10.1016/j.compbiomed.2021.105114](https://doi.org/10.1016/j.compbiomed.2021.105114)). The numeric bound matches the primary source directly, on the relevant data type and task, and is corroborated by Diamant et al.

**Contested (Claim 2, confidence High).** The word "consistently" is what fails. Diamant et al. show patient-contrastive pretraining beating from-scratch training on most tasks, but they report significant benefits in only "three out of four tasks," explicitly not all (Diamant et al., 2022, [10.1371/journal.pcbi.1009862](https://doi.org/10.1371/journal.pcbi.1009862)). The literature supports "competitive with, and often modestly better than" supervised training, not a universal win.

**Partially Supported (Claim 3, confidence Medium).** Hannun et al. report cardiologist-level detection of 12 rhythm classes from single-lead ambulatory ECG (Hannun et al., 2019, [10.1038/s41591-018-0268-3](https://doi.org/10.1038/s41591-018-0268-3)), and Ribeiro et al. report a 12-lead DNN with F1 above 80% and specificity over 99% (Ribeiro et al., 2020, [10.1038/s41467-020-15432-4](https://doi.org/10.1038/s41467-020-15432-4)). Both are scoped to specific classes, acquisition settings, and comparison groups, so the unqualified blanket version overreaches.

**Contradicted (Claim 4, confidence High).** The retrieved evidence directly opposes the claim rather than merely failing to speak to it. Every self-supervised ECG method examined still relies on a labeled fine-tuning or linear-evaluation stage: Lai et al., operating at large scale, annotate 164,538 of their ECGs and report performance on that labeled evaluation (Lai et al., 2023, [10.1038/s41467-023-39472-8](https://doi.org/10.1038/s41467-023-39472-8)). Self-supervision reduces the quantity of labels needed, not the need for labels. Note the verdict boundary the skill holds to: Unsupported is reserved for claims where the search returns no evidence either way, whereas this one is Contradicted because the evidence base actively points the other direction. Either way, no citation is invented to prop up the claim or to fill a gap.

## Next steps

- The [Research and Discovery guide](/researcher/guides/research-and-discovery/) covers the full discovery pipeline these two skills belong to.
- The complete worked examples, with per-source query strings, the full ranked set, and the provenance JSON, live in the [research-verification example folder](https://github.com/sokolmarek/researcher/tree/main/examples/research-verification) on GitHub.
