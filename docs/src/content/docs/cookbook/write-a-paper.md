---
title: Write a paper
description: Walk the full writing loop from an empty scaffold to a point-by-point rebuttal, with the exact prompts to type at each step.
sidebar:
  label: Write a paper
  order: 2
---

Drafting a manuscript is a loop, not a single heroic prompt: scaffold the folder, draft a section, invite the reviewers you would rather not meet, then answer them. This recipe walks that loop end to end using the running scenario, a methods paper on self-supervised contrastive pretraining for label-efficient ECG arrhythmia classification, evaluated on PTB-XL.

One honesty note up front, because it matters for how you read the output. The reviewer opinions produced in step 3 are synthetic and clearly labeled as such, and the illustrative empirical contributions in the draft are labeled too, because no experiment was actually run here. Every piece of literature that gets invoked, on the other hand, is real: the papers a reviewer tells you to cite resolve to actual DOIs, and the citation keys in your introduction resolve to a real library. Researcher will label a fabricated opinion; it will not fabricate a citation.

## Step 1: Scaffold the manuscript

Start with the folder, not the prose. Run the command:

```
/researcher:new-manuscript
```

The command starts a short conversation and asks for the details it needs: title, authors, target journal, format, citation style, and paper type. For the running scenario, the answers look like this:

| Field | Value |
|---|---|
| title | Self-Supervised Contrastive Pretraining for Label-Efficient ECG Arrhythmia Classification |
| authors | A. Novak, R. Delgado, M. Farah (synthetic, for demonstration) |
| journal | IEEE Journal of Biomedical and Health Informatics |
| format | latex |
| citation_style | ieee |
| paper_type | imrad |

The skill elicits two clarifications before writing anything: whether to use the `IEEEtran` journal class (yes, since the target is IEEE JBHI) and whether to pre-create `figures/` and `tables/` folders with placeholders (yes, this is a methods paper with a model diagram). Answer both, and it scaffolds:

```
manuscript/
├── main.tex                 # IEEEtran master doc with \input{} includes
├── abstract.tex
├── introduction.tex
├── methods.tex
├── results.tex
├── discussion.tex
├── conclusion.tex
├── acknowledgments.tex
├── config.yaml              # title, authors, journal, style, status
├── terminology.yaml         # consistent-term tracking
├── references/
│   └── library.bib          # empty, ready for literature-search output
├── figures/
│   └── architecture.tex     # placeholder
└── tables/
    └── results-table.tex     # placeholder
```

Two files do quiet but important work. `config.yaml` records the journal choice, which is why `main.tex` already loads `IEEEtran` and sets `\bibliographystyle{IEEEtran}`: the class was not a guess, it followed from the target venue. And `terminology.yaml` is seeded with the paper's key terms so later drafting stays consistent:

```yaml
terms:
  "self-supervised learning": ["self supervised learning", "SSL (spell out on first use)"]
  "electrocardiogram (ECG)": ["EKG", "ecg"]
  "contrastive pretraining": ["contrastive pre-training", "contrastive pre training"]
  "PTB-XL": ["PTB XL", "PTBXL"]
  "macro-AUROC": ["macro AUC", "macro-AUC"]
```

The empty `library.bib` is the drop target for your literature search. If you have not built a library yet, see the research recipe first; the cite keys in the next step assume it is populated.

## Step 2: Draft the introduction

With the scaffold and a populated library in place, draft a section. The introduction is the natural first one because it is where citations do the heaviest lifting. Type:

```
Draft the introduction for my methods paper on self-supervised
contrastive pretraining for ECG arrhythmia classification. Funnel
structure, about 600 words, cite the papers already in my library,
and end with explicit contributions.
```

What comes back is a funnel: broad progress (deep learning reaches cardiologist-level arrhythmia detection, `hannun2019cardiologist`; 12-lead models recognize abnormalities with high specificity, `ribeiro2020automatic`; PTB-XL provides 21,837 records from 18,885 patients, `wagner2020ptbxl`), narrowing to the specific gap (augmentation design is inherited ad hoc from vision, and cross-study comparisons are confounded by differing protocols), and closing with an explicit, enumerated contributions list.

The load-bearing property is that **every factual claim carries a `\cite` key that resolves to your `references/library.bib`**. The drafting skill maintains a claim-to-citation mapping alongside the prose so nothing floats free:

| Sentence claim | Citation | Basis |
|---|---|---|
| DNNs reach cardiologist-level arrhythmia detection | hannun2019cardiologist | Nature Medicine 2019 |
| PTB-XL size (21,837 records / 18,885 patients) | wagner2020ptbxl | dataset paper, exact figures |
| SSL within ~1% of supervised on 12-lead | mehari2022ssl | linear-eval margin |
| Subfield growth and protocol fragmentation | liu2023review | PRISMA review |

Numbers that appear in the prose (21,837 records; within one percent of supervised) are the source-verified figures, not round approximations. The contributions block is labeled synthetic because it describes an experiment that was not run. This mapping is exactly what the post-draft integrity hook and the citation-audit skill check later, so keep it.

## Step 3: Convene the reviewer panel

Now hand the manuscript to the panel you would rather avoid. Run:

```
/researcher:review-paper
```

or, more explicitly:

```
Review my SSL-for-ECG manuscript with a full reviewer panel. I want
an editor summary, individual reviewers, a devil's advocate, rubric
scores, and a decision recommendation.
```

You get five distinct personas, each critiquing a different axis rather than five copies of one generic take:

- **Editor-in-Chief**: overall framing and the decision recommendation.
- **Reviewer 1, Methodology**: reproducibility and baseline fairness (asks for a five-seed ablation with mean and SD, and a supervised baseline matched on backbone and budget).
- **Reviewer 2, Domain Expert**: clinical scoping and external validity (scope the cardiologist-level claim; discuss cross-cohort generalization).
- **Reviewer 3, Writing**: figure ordering, contribution-list structure.
- **Devil's Advocate**: the strongest case for rejection, that the headline result may be a protocol artifact rather than a method advance.

Each persona scores the dimensions it is qualified to judge on the canonical six-dimension, 0 to 100 rubric, and those aggregate to a weighted overall that maps deterministically to a decision:

| Dimension | Weight | Mean score |
|---|---|---|
| Novelty & Significance | 0.20 | 62.7 |
| Methodology | 0.25 | 57.5 |
| Results & Analysis | 0.20 | 55.0 |
| Writing Quality | 0.15 | 76.0 |
| Literature & Context | 0.10 | 68.0 |
| Reproducibility | 0.10 | 48.0 |
| **Weighted overall** | | **60.9 / 100 → Major Revision** |

The decision mapping is fixed (80+ accept, 65 to 79 minor revision, 50 to 64 major revision, below 50 reject), so the 60.9 is not a vibe, it is a computation that lands in the 50 to 64 band. The reviewer text is synthetic and labeled `(synthetic reviewer content)`, but when the Domain Expert says to compare directly to lead-agnostic pretraining (Oh et al., 2022) or the Methodology reviewer invokes the roughly one percent margin from Mehari and Strodthoff (2022), those are real, resolvable references verified against OpenAlex and Crossref. The panel closes with a consolidated, prioritized action list, which is the input to the final step.

## Step 4: Answer point by point

Turn the action list into a rebuttal. Type:

```
Draft a point-by-point response to the reviewer comments on my
SSL-for-ECG paper. Be respectful, say exactly what changed and where,
and where I disagree, back it with evidence.
```

The response quotes each comment in italics, answers it, and names the manuscript location that changed, following the `response-to-reviewers.tex` template. Three moments are worth watching:

- **A candid concession.** After re-running the ablation over five seeds, two of the three previously positive augmentation effects fall inside the baseline confidence interval and are reclassified as inconclusive rather than defended. That is what an honest revision looks like.
- **A matched baseline.** The supervised comparison is rebuilt on the identical backbone, optimizer, and epoch budget (Strodthoff et al., 2021), and the SSL margin shrinks accordingly, consistent with the roughly one percent range in the literature.
- **A respectful disagreement, evidence-backed.** For the request to reproduce lead-agnostic pretraining head to head, the response declines and says why: a fair reproduction needs the original pipeline and pretraining corpus, and Liu et al. (2023) document exactly how fragmented these protocols are, so an under-specified reproduction would misrepresent the method. It adds a qualitative comparison instead and states that choice plainly.

Every paper cited in the rebuttal is real and resolvable, and every answer threads back to a specific item on the panel's action list, which keeps the whole loop internally consistent from scaffold to response.

## Where to go next

- The [Writing and revision guide](/researcher/guides/writing-and-revision/) covers the underlying skills (manuscript-setup, paper-drafting, peer-review, revision-management, response-to-reviewers, cover-letter) in depth.
- The full worked artifacts for every step live in [examples/writing-review](https://github.com/sokolmarek/researcher/tree/main/examples/writing-review).
