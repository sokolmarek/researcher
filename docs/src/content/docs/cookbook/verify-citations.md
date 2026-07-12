---
title: "Cookbook: Verify the citations"
description: Audit a bibliography for existence and retractions, then admit only SOTA numbers traced back to the source paper.
sidebar:
  label: Verify citations
  order: 3
---

A fabricated citation is the one mistake that turns a good paper into a retraction notice, and it is exactly the mistake a fluent language model is happy to make on your behalf. Researcher treats citation integrity as a gate, not a suggestion. This recipe runs two checks on the running scenario (self-supervised learning for ECG arrhythmia classification, evaluated on PTB-XL): an existence-plus-retraction audit over the whole bibliography, and a state-of-the-art table that refuses to print a number it cannot trace to a real paper.

Everything below comes from the worked examples in [`examples/research-verification/`](https://github.com/sokolmarek/researcher/tree/main/examples/research-verification).

## Audit the bibliography for existence

> Verify every reference in `references/library.bib` actually exists in the literature, flag anything that cannot be resolved, and check for retractions.

The input is a 10-entry `library.bib`. Nine are the real papers from the shared example. One, `kessler2021cmae`, is a synthetic entry planted deliberately so the gate has something to reject. It is labeled `(synthetic, for demonstration)` in the source and is the only invented reference anywhere in the examples.

Each reference is checked against up to four independent indexes (OpenAlex, Crossref, Semantic Scholar, arXiv). A verdict of `verified` requires confirmation by at least two of them, with title similarity of 0.70 or better and a matching year and first author.

| Key | Verdict | Confirmed by |
|---|---|---|
| mehari2022ssl | verified | OpenAlex, Crossref, S2 |
| diamant2022pclr | verified | OpenAlex, Crossref, S2 |
| wagner2020ptbxl | verified | OpenAlex, Crossref, S2 |
| strodthoff2021benchmark | verified | OpenAlex, Crossref |
| ribeiro2020automatic | verified | OpenAlex, Crossref, S2 |
| hannun2019cardiologist | verified | OpenAlex, Crossref, S2 |
| lai2023practical | verified | OpenAlex, Crossref |
| liu2023review | verified | OpenAlex, Crossref |
| sarkar2022ssl | verified | OpenAlex, Crossref |
| **kessler2021cmae** | **unresolvable** | none |

The nine real entries clear the gate cleanly. The planted fake does not: its DOI `10.1109/TBME.2021.3098765` does not resolve in Crossref, and no title match appears in any index. Verdict, `unresolvable`, likely fabricated.

**Gate result: 9 verified, 0 mismatch, 1 unresolvable.**

:::caution[An unresolvable reference is refusal-grade]
The audit will not certify this bibliography as clean while `kessler2021cmae` remains. A real run stops here and asks you to supply a genuine source or delete the citation. This is the human-in-the-loop stop, and it is deliberately not overridable by a confident-sounding model.
:::

## Sweep for retractions and corrections

The same pass checks OpenAlex `is_retracted` and Crossref `update-to` metadata on the verified entries. The point here is to tell a genuine retraction apart from the routine post-publication housekeeping that panics people who conflate the two.

| Key | Retracted? | On record |
|---|---|---|
| all 9 verified entries | No | two routine corrections, noted below |

Two of the real papers carry corrections. `hannun2019cardiologist` has a Publisher Correction (*Nature Medicine*, 2019, `10.1038/s41591-019-0359-9`), and `ribeiro2020automatic` has an Author Correction (*Nature Communications*, 2020, `10.1038/s41467-020-16172-1`). Neither is a retraction. Both are ordinary errata, so they are noted for your awareness and not flagged as problems.

**Sweep result: 0 retractions, 2 routine corrections noted.**

### Audit verdict

> **NOT CLEAN.** 1 of 10 references is unresolvable (`kessler2021cmae`) and must be resolved or removed before this bibliography can be certified. No retractions found. Two corrections noted.

That single verdict line is the whole product. A green checkmark you cannot trust is worse than no checkmark, so the tool would rather say "not clean" than launder a fake into your reference list.

## Verify the SOTA numbers before you cite them

The second half of integrity is the numbers you quote, not just the papers you cite. Ask for a state-of-the-art comparison and the `sota-finder` skill reads each source's own reported metric before any figure enters the table.

> What is the state of the art for deep learning on the PTB-XL ECG benchmark, and how do the self-supervised results compare? Give me a comparison table for a related-work section, and be honest about what is and is not directly comparable.

| Method (paper) | Year | Benchmark / task | Reported metric (as stated by source) | Verified |
|---|---|---|---|---|
| Supervised CNNs (Strodthoff et al.) | 2021 | PTB-XL, all statement tasks | resnet/inception CNNs "show the strongest performance across all tasks" | partial |
| Contrastive predictive coding, SSL (Mehari and Strodthoff) | 2022 | PTB-XL, linear evaluation | linear-eval "only 0.5% below supervised"; fine-tuned "roughly 1%" above | yes |
| PCLR, patient-contrastive SSL (Diamant et al.) | 2022 | 4 clinical tasks, large private cohort | "51% performance increase, on average" over from-scratch | yes |
| 12-lead supervised DNN (Ribeiro et al.) | 2020 | CODE test set, 6 abnormalities | F1 "above 80%" and specificity "over 99%" | yes |
| Single-lead supervised DNN (Hannun et al.) | 2019 | Ambulatory single-lead, 12 rhythm classes | "cardiologist-level" detection and classification | yes |
| SSL at scale (Lai et al.) | 2023 | Wearable 12-lead, 60 diagnostic terms | average AUROC 0.975, average F1 0.575 (offline test) | yes |
| "xresnet1d101 ~0.94 macro-AUROC on PTB-XL" | n/a | PTB-XL, all | circulates on public leaderboards; not traced to a specific published number | **unverified** |

Two habits make this table trustworthy. First, every number is copied from the source's own abstract or reported results in that source's own metric, so no row is silently harmonized into a single misleading ranking. The studies use different datasets (PTB-XL, CODE, a proprietary wearable corpus) and different metrics (macro-AUROC vs. F1 vs. relative improvement), and only the two PTB-XL rows are actually comparable to each other. Second, the last row exists to show the flag working: a number seen on a leaderboard is not admitted as fact until it is traced to a real source, so it stays marked **unverified** rather than quietly promoted to a citation.

:::note[Provenance is the feature]
Verified rows were read back from the source this session. The unverified row could not be. Making that distinction visible is the entire methodological point, because a related-work table that hides its provenance is just a rumor with a border.
:::

## What you get

- A bibliography audit that confirms real references across multiple independent indexes and refuses to certify the set while any entry is unresolvable.
- A retraction sweep that separates genuine retractions (none here) from routine corrections and errata (present, noted calmly).
- A SOTA table where each figure is attributed to the paper that reported it, cross-dataset non-comparability is stated up front, and untraceable claims are flagged rather than included.

## Keep going

- For where these checks sit in the wider pipeline (literature search, gaps, SOTA, fact-checking), see the [research and discovery guide](/researcher/guides/research-and-discovery/).
- The full source for both worked examples lives in [`examples/research-verification/`](https://github.com/sokolmarek/researcher/tree/main/examples/research-verification).
