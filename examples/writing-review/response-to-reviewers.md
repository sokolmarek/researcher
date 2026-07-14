# Example: Response to Reviewers

| Field | Value |
|---|---|
| Skill | response-to-reviewers |
| Command | /researcher:revise |
| Trigger phrase | "Draft a point-by-point response to these reviewer comments" |
| Connectors used | OpenAlex, Crossref (to verify any paper cited in a rebuttal) |
| Generated | 2026-07-12 |

## Invocation

> Draft a point-by-point response to the reviewer comments on my SSL-for-ECG paper. Be respectful, say exactly what changed and where, and where I disagree, back it with evidence.

## Input

The consolidated action list from the peer-review example. Manuscript edits described below are `(synthetic, for demonstration)`. The response follows the conventions of `templates/latex/response-to-reviewers.tex` (quoted comment, then response, then location of change).

## Output

We thank the editor and reviewers for their careful reading. Reviewer comments are quoted in italics; our responses follow. Manuscript locations refer to the revised version; changed text is shown in blue in the tracked-changes PDF.

---

### Reviewer 1 (Methodology)

> *Comment 1.1: The augmentation ablation reports relative improvements but does not specify random-seed handling, number of runs, or confidence intervals.*

**Response.** We agree. We re-ran the full ablation over five random seeds and now report, for each augmentation, the 95% confidence interval of the *paired* difference against the matched baseline (the difference computed seed by seed, not the overlap of two marginal error bars). By this test our physiological augmentation improves over the contrastive baseline at the 1% labeled fraction (paired difference +0.018, 95% CI [+0.001, +0.035]), but the differences at 10% and 100% include zero (+0.008, 95% CI [-0.012, +0.028] and +0.003, 95% CI [-0.006, +0.012]) and are now described as inconclusive rather than as improvements. **Changes: Section IV-C, Table 3 (now with mean ± SD), and the last paragraph of Section IV-C.**

> *Comment 1.2: The supervised baseline must use the same backbone and training budget as the fine-tuned SSL model.*

**Response.** Agreed and corrected. The supervised baseline now uses the identical backbone, optimizer, and epoch budget as the fine-tuned model, matching the protocol of Strodthoff et al. (2021). Under the matched comparison, the fine-tuned SSL model improves over supervised by a smaller margin than originally reported, consistent with the roughly one percent range documented by Mehari and Strodthoff (2022). **Changes: Section III-D and Table 2.**

> *Comment 1.3: Specify the linear-evaluation versus fine-tuning protocol.*

**Response.** Done. Section III-C now states explicitly which results use a frozen encoder with a linear head and which use end-to-end fine-tuning. **Change: Section III-C.**

---

### Reviewer 2 (Domain Expert)

> *Comment 2.1: Scope the cardiologist-level claim to the settings where it holds.*

**Response.** We have narrowed the claim. The introduction now attributes cardiologist-level performance specifically to single-lead ambulatory detection (Hannun et al., 2019) and to six abnormality classes on a 12-lead telehealth cohort (Ribeiro et al., 2020), rather than stating it as a general capability. **Change: Introduction, paragraph 1.**

> *Comment 2.2: Discuss external-validation limitations.*

**Response.** Added. A new limitations paragraph discusses cross-cohort generalization and shortcut learning as documented risks (Ong Ly et al., 2024), and states plainly that our evaluation is confined to PTB-XL. **Change: Section V, new final paragraph.**

> *Comment 2.3: Compare directly to lead-agnostic pretraining (Oh et al., 2022), not just cite it.*

**Response (respectful disagreement, evidence-backed).** We have added a qualitative comparison and a discussion of the methodological differences, and we cite Oh et al. (2022) accordingly. We respectfully did not add a head-to-head re-implementation benchmark. A fair reproduction would require the authors' lead-agnostic pretraining pipeline and their pretraining corpus, and the systematic review by Liu et al. (2023) documents exactly how fragmented and non-comparable pretraining protocols in this subfield are, so an under-specified reproduction would risk misrepresenting their method. We believe the added qualitative comparison serves the reader better than an unfair quantitative one, and we have said so explicitly in the text. **Change: Section II, new paragraph; Section V discussion.**

---

### Reviewer 3 (Writing)

> *Comment 3.1: Several figures are referenced before they are introduced.*

**Response.** Fixed. Figure references now follow figure introduction order throughout. **Changes: Sections III and IV.**

> *Comment 3.2: Separate method and evaluation contributions.*

**Response.** The contributions list is now split into a "Method" group and an "Evaluation" group. **Change: Introduction, contributions list.**

---

### Summary of major changes

1. Five-seed ablation with paired-difference confidence intervals; the 10% and 100% effects reclassified as inconclusive, the 1% effect retained.
2. Matched supervised baseline; revised, smaller SSL margin.
3. Scoped clinical claims and a new external-validation limitations paragraph.
4. Added qualitative comparison to lead-agnostic pretraining with a stated rationale for not reproducing it.

### References cited in this response (all real)

- Hannun, A. Y., et al. (2019). *Nature Medicine, 25*(1), 65-69. https://doi.org/10.1038/s41591-018-0268-3
- Liu, Z., et al. (2023). *Sensors, 23*(9), 4221. https://doi.org/10.3390/s23094221
- Mehari, T., & Strodthoff, N. (2022). *Computers in Biology and Medicine, 141*, 105114. https://doi.org/10.1016/j.compbiomed.2021.105114
- Oh, J., et al. (2022). Lead-agnostic self-supervised learning for ECG. *CHIL (PMLR)*. arXiv:2203.06889
- Ong Ly, C., et al. (2024). *npj Digital Medicine, 7*, 124. https://doi.org/10.1038/s41746-024-01118-4
- Ribeiro, A. H., et al. (2020). *Nature Communications, 11*, 1760. https://doi.org/10.1038/s41467-020-15432-4
- Strodthoff, N., et al. (2021). *IEEE JBHI, 25*(5), 1519-1528. https://doi.org/10.1109/jbhi.2020.3022989

## What this demonstrates

- Every reviewer comment is quoted, answered, and tied to a specific manuscript location, matching the response-to-reviewers template.
- The response includes a candid outcome (effects reclassified as inconclusive after proper statistics) rather than defending the original claims, which is what an honest revision looks like. The statistics reason from the paired-difference interval, matching the paired t-test in the results-table example, not from the overlap of marginal error bars.
- Comment 2.3 shows a respectful, evidence-backed disagreement: the authors decline a request and cite a real paper (Liu et al., 2023) to justify why, instead of either capitulating or hand-waving.
- Answers thread directly from the peer-review example's action list, keeping the writing-review example set internally consistent.
