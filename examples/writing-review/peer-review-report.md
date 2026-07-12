# Example: Multi-Persona Peer Review Report

| Field | Value |
|---|---|
| Skill | peer-review |
| Command | /review-paper |
| Trigger phrase | "Review my manuscript with a full reviewer panel and give me scores" |
| Connectors used | OpenAlex, Crossref (to verify any literature a reviewer invokes) |
| Generated | 2026-07-12 |

## Invocation

> Review my SSL-for-ECG manuscript with a full reviewer panel. I want an editor summary, individual reviewers, a devil's advocate, rubric scores, and a decision recommendation.

## Input

The manuscript from the writing examples (introduction drafted, methods and results as a synthetic skeleton). All reviewer comments below are `(synthetic reviewer content)`. Any paper a reviewer says the authors "should cite" is a real, resolvable reference.

## Output

### Rubric scores (0-100 per dimension)

| Dimension | EIC | Methodology | Domain Expert | Writing | Weight |
|---|---|---|---|---|---|
| Novelty | 62 | 58 | 65 | - | 0.25 |
| Technical soundness | - | 55 | 60 | - | 0.30 |
| Clarity | 74 | - | - | 78 | 0.15 |
| Reproducibility | - | 48 | - | - | 0.15 |
| Significance | 68 | - | 70 | - | 0.15 |
| **Weighted overall** | | | | | **59 / 100** |

Decision mapping: 70+ minor revision, 50-69 major revision, below 50 reject. **Overall 59 maps to Major Revision.**

---

### Editor-in-Chief summary

*(synthetic reviewer content)*

The manuscript proposes a contrastive pretraining scheme with physiologically grounded augmentations, evaluated on PTB-XL. The topic is timely and the benchmark choice is appropriate. The panel is broadly positive on framing and clarity but raises substantive concerns about reproducibility of the augmentation ablation and about whether the novelty is sufficiently delineated from prior contrastive-ECG work. I recommend **Major Revision**, contingent on the authors addressing the methodology reviewer's reproducibility points and the domain expert's request for a fair supervised baseline.

---

### Reviewer 1: Methodology

*(synthetic reviewer content)*

1. **Reproducibility (major).** The augmentation ablation reports relative improvements but does not specify random-seed handling, number of runs, or confidence intervals. Given that the reported SSL-over-supervised margin in this area is often around one percent (Mehari & Strodthoff, 2022), single-run differences are within plausible noise. Please report mean and standard deviation over at least five seeds.
2. **Baseline fairness (major).** The supervised baseline must use the same backbone and training budget as the fine-tuned SSL model, following the benchmarking protocol of Strodthoff et al. (2021). As written, it is unclear the comparison is matched.
3. **Missing detail (minor).** Specify the linear-evaluation protocol (frozen encoder, linear head) versus fine-tuning, since the two give different conclusions.

Score: technical soundness 55, reproducibility 48.

---

### Reviewer 2: Domain Expert (cardiology / ECG)

*(synthetic reviewer content)*

1. **Clinical framing (moderate).** The introduction claims cardiologist-level performance as motivation; please scope this to the specific settings where it holds (single-lead ambulatory in Hannun et al., 2019; six abnormality classes in Ribeiro et al., 2020) rather than as a blanket capability.
2. **Generalization (moderate).** The paper evaluates only on PTB-XL. Shortcut learning and cross-cohort failure are documented risks for ECG models (Ong Ly et al., 2024). At minimum, discuss external-validation limitations.
3. **Related work (minor).** The lead-agnostic pretraining approach of Oh et al. (2022) is closely related to the proposed augmentations and should be compared, not just cited.

Score: novelty 65, significance 70.

---

### Reviewer 3: Writing and Presentation

*(synthetic reviewer content)*

The manuscript is clearly written and well organized. The funnel introduction is effective. Two issues: (1) several figures are referenced before they are introduced; fix the ordering. (2) The contributions list mixes method and evaluation contributions; consider separating them. No concerns about language or structure otherwise.

Score: clarity 78.

---

### Devil's Advocate

*(synthetic reviewer content)*

The strongest case against acceptance: the central result may be a protocol artifact rather than a method advance. The related-work synthesis itself notes that evaluation protocols in contrastive medical-time-series learning are fragmented (Liu et al., 2023), and the reported margins over supervised training in this subfield are small (Mehari & Strodthoff, 2022). If the ablation is not run over multiple seeds with matched baselines, the paper's core claim is not yet supported by its own evidence. This is not fatal, but it is the difference between Major Revision and Reject, and it should be the authors' first priority.

---

### Consolidated action list for authors

| Priority | Item | Raised by |
|---|---|---|
| 1 | Multi-seed ablation with mean/SD and CIs | Methodology, Devil's Advocate |
| 2 | Matched supervised baseline (same backbone/budget) | Methodology |
| 3 | Scope the cardiologist-level claim | Domain Expert |
| 4 | Add external-validation / generalization discussion | Domain Expert |
| 5 | Direct comparison to lead-agnostic pretraining | Domain Expert |
| 6 | Fix figure ordering; separate contribution types | Writing |

### References invoked by reviewers (all real)

- Hannun, A. Y., et al. (2019). *Nature Medicine, 25*(1), 65-69. https://doi.org/10.1038/s41591-018-0268-3
- Liu, Z., et al. (2023). *Sensors, 23*(9), 4221. https://doi.org/10.3390/s23094221
- Mehari, T., & Strodthoff, N. (2022). *Computers in Biology and Medicine, 141*, 105114. https://doi.org/10.1016/j.compbiomed.2021.105114
- Oh, J., et al. (2022). Lead-agnostic self-supervised learning for ECG. *CHIL (PMLR)*. arXiv:2203.06889
- Ong Ly, C., et al. (2024). *npj Digital Medicine, 7*, 124. https://doi.org/10.1038/s41746-024-01118-4
- Ribeiro, A. H., et al. (2020). *Nature Communications, 11*, 1760. https://doi.org/10.1038/s41467-020-15432-4
- Strodthoff, N., et al. (2021). *IEEE JBHI, 25*(5), 1519-1528. https://doi.org/10.1109/jbhi.2020.3022989

## What this demonstrates

- Five distinct personas (Editor-in-Chief, Methodology, Domain Expert, Writing, Devil's Advocate) produce non-overlapping, dimension-specific critiques rather than one generic review.
- Rubric scores per dimension aggregate to a weighted overall that maps deterministically to a decision (59 to Major Revision).
- Reviewer opinions are synthetic and labeled, but every paper a reviewer cites as relevant literature is a real, resolvable reference, so the "you should compare to X" comments are actionable and checkable.
- The consolidated action list is what the response-to-reviewers example answers point by point.
