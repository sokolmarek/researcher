# Example: Fact-Checking Report

| Field | Value |
|---|---|
| Skill | fact-checking |
| Command | /researcher:fact-check |
| Trigger phrase | "Fact-check these four claims about self-supervised ECG models against the literature" |
| Connectors used | Scite MCP (Smart Citations), OpenAlex, Crossref |
| Generated | 2026-07-12, all cited DOIs verified on this date |

## Invocation

> Fact-check these four claims about self-supervised ECG models against the literature. For each, give a verdict, the evidence, and your confidence.
>
> 1. Self-supervised pretraining on unlabeled ECG can reach classification performance within about one percent of fully supervised training.
> 2. Contrastive self-supervised pretraining consistently outperforms supervised training across ECG tasks.
> 3. Deep neural networks match cardiologist-level performance for arrhythmia detection from the ECG.
> 4. Self-supervised ECG models remove the need for any labeled data to achieve clinical-grade arrhythmia diagnosis.

## Input

Four claims (above). No manuscript attached; claims checked against retrieved literature only.

## Output

### Verdict summary

| # | Claim (abbreviated) | Verdict | Confidence |
|---|---|---|---|
| 1 | SSL reaches within ~1% of supervised | **Supported** | High |
| 2 | Contrastive SSL consistently beats supervised on ECG | **Contested** | High |
| 3 | DNNs match cardiologist-level arrhythmia detection | **Partially Supported** | Medium |
| 4 | SSL removes need for any labeled data for clinical diagnosis | **Contradicted** | High |

---

### Claim 1: Supported

> Self-supervised pretraining on unlabeled ECG can reach classification performance within about one percent of fully supervised training.

**Evidence.** Mehari and Strodthoff report that, on a clinical 12-lead ECG classification task, their best self-supervised method (an adaptation of contrastive predictive coding) reaches a linear-evaluation performance "only 0.5% below supervised performance," and that fine-tuning the self-supervised representation yields "improvements in downstream performance of roughly 1% compared to purely supervised performance" (Mehari & Strodthoff, 2022). Diamant et al. independently report large label-efficiency gains from patient-contrastive pretraining relative to training from scratch (Diamant et al., 2022).

**Reasoning.** The claim's numeric bound (about one percent) matches the primary source directly, on the relevant data type (clinical 12-lead) and task (multi-label ECG statement classification). A second independent study supports the direction.

**Confidence: High.** Direct quantitative match from a peer-reviewed source, corroborated.

---

### Claim 2: Contested

> Contrastive self-supervised pretraining consistently outperforms supervised training across ECG tasks.

**Supporting evidence.** Diamant et al. show patient-contrastive pretraining beating from-scratch training on most tasks studied (Diamant et al., 2022).

**Contrasting evidence.** The word "consistently" fails. Mehari and Strodthoff find fine-tuned improvements of only "roughly 1%" over supervised, and a linear-evaluation gap that is *below* supervised performance rather than above it, indicating the benefit is small and task-dependent rather than uniform (Mehari & Strodthoff, 2022). Diamant et al. themselves report significant benefits in only "three out of four tasks," explicitly not all (Diamant et al., 2022).

**Reasoning.** The literature supports that contrastive SSL is *competitive with, and often modestly better than,* supervised training, and is most valuable in low-label regimes, but the universal "consistently outperforms across ECG tasks" framing is contradicted by the same sources.

**Confidence: High** that the strong universal claim is contested.

---

### Claim 3: Partially Supported

> Deep neural networks match cardiologist-level performance for arrhythmia detection from the ECG.

**Evidence for.** Hannun et al. report cardiologist-level detection and classification of 12 rhythm classes from single-lead ambulatory ECG using a deep neural network (Hannun et al., 2019). Ribeiro et al. report a 12-lead DNN that outperformed cardiology residents on 6 abnormality types, with F1 scores above 80% and specificity over 99% (Ribeiro et al., 2020).

**Why only partial.** Both results are scoped: specific rhythm or abnormality classes, specific acquisition settings (single-lead ambulatory in one, a particular 12-lead telehealth cohort in the other), and specific comparison groups. Neither establishes cardiologist-level parity across all arrhythmias or all populations, and generalization to external data remains a documented concern for medical ECG models (Ong Ly et al., 2024). The unqualified claim overreaches the evidence.

**Confidence: Medium.** Strong evidence for the scoped version; the blanket version is not established.

---

### Claim 4: Contradicted

> Self-supervised ECG models remove the need for any labeled data to achieve clinical-grade arrhythmia diagnosis.

**Contrasting evidence.** Every self-supervised ECG method retrieved still relies on a labeled fine-tuning or linear-evaluation stage to reach its reported performance, so the evidence base directly opposes the claim rather than merely failing to address it: Mehari and Strodthoff evaluate via linear probing and fine-tuning on labeled data (Mehari & Strodthoff, 2022); Diamant et al. train linear models on labeled tasks atop frozen representations (Diamant et al., 2022); Lai et al., operating at large scale, annotate 164,538 of their ECGs and report diagnostic performance on that labeled evaluation (Lai et al., 2023). Self-supervision reduces the *quantity* of labels needed, not the need for labels.

**Reasoning.** This is a Contradicted verdict, not an Unsupported one: Unsupported means the search returned no evidence either way, whereas here multiple retrieved sources provide counter-evidence through their own experimental design. No source is cited *for* the claim, because none exists in the retrieved literature, and none is invented to fill the gap.

**Confidence: High** that the claim as stated is contradicted by the evidence base.

---

### References

- Diamant, N., Reinertsen, E., Song, S., Aguirre, A. D., & Stultz, C. M. (2022). Patient contrastive learning: A performant, expressive, and practical approach to electrocardiogram modeling. *PLOS Computational Biology, 18*(2), e1009862. https://doi.org/10.1371/journal.pcbi.1009862
- Hannun, A. Y., Rajpurkar, P., Haghpanahi, M., Tison, G. H., Bourn, C., et al. (2019). Cardiologist-level arrhythmia detection and classification in ambulatory electrocardiograms using a deep neural network. *Nature Medicine, 25*(1), 65-69. https://doi.org/10.1038/s41591-018-0268-3
- Lai, J., Tan, H., Wang, J., Ji, L., et al. (2023). Practical intelligent diagnostic algorithm for wearable 12-lead ECG via self-supervised learning on large-scale dataset. *Nature Communications, 14*, 3741. https://doi.org/10.1038/s41467-023-39472-8
- Mehari, T., & Strodthoff, N. (2022). Self-supervised representation learning from 12-lead ECG data. *Computers in Biology and Medicine, 141*, 105114. https://doi.org/10.1016/j.compbiomed.2021.105114
- Ong Ly, C., Unnikrishnan, B., Tadic, T., Patel, T., et al. (2024). Shortcut learning in medical AI hinders generalization. *npj Digital Medicine, 7*, 124. https://doi.org/10.1038/s41746-024-01118-4
- Ribeiro, A. H., Ribeiro, M. H., Paixão, G. M. M., Oliveira, D. M., Gomes, P. R., et al. (2020). Automatic diagnosis of the 12-lead ECG using a deep neural network. *Nature Communications, 11*, 1760. https://doi.org/10.1038/s41467-020-15432-4

## What this demonstrates

- Four claims resolve to four different verdicts, including an honest **Contradicted** where the retrieved evidence opposes the claim and no source is invented to prop up a false statement. The verdict labels follow the fact-checking skill's definitions exactly: Contradicted means counter-evidence exists, whereas Unsupported is reserved for claims where the search returned nothing either way.
- Each verdict separates supporting from contrasting evidence and quotes the actual reported numbers (0.5% linear-eval gap, "three out of four tasks", F1 > 80%) rather than paraphrasing from memory.
- The distinction between a scoped true claim and an overreaching blanket claim (Claim 3) is made explicit, which is the common failure mode in related-work sections.
- Every cited DOI resolves; the reference list uses APA and matches the shared example bibliography.
