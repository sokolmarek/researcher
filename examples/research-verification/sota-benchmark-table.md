# Example: State-of-the-Art Benchmark Table

| Field | Value |
|---|---|
| Skill | sota-finder |
| Command | /researcher:sota |
| Trigger phrase | "What's the state of the art for deep learning on the PTB-XL ECG benchmark and related SSL results?" |
| Connectors used | OpenAlex, Crossref, arXiv; Scite MCP for verification |
| Generated | 2026-07-12, every numeric entry traced to the source paper's own reporting |

## Invocation

> What is the state of the art for deep learning on the PTB-XL ECG benchmark, and how do the self-supervised results compare? Give me a comparison table I can put in a related-work section, and be honest about what is and is not directly comparable.

## Input

None. The skill retrieves candidate papers and reads each source's reported metrics before entering any number into the table.

## Output

### Reading note before the table

Numbers below are copied from each paper's own abstract or reported results and attributed to that source. **They are not mutually comparable across rows**: the studies use different datasets (PTB-XL, CODE, a proprietary wearable corpus), different label sets, and different metrics (macro-AUROC vs. F1 vs. relative improvement). A single "leaderboard number" across these would be misleading, so the table keeps the benchmark and metric columns explicit. Rows are flagged **Verified** when the reported figure was read back from the source this session, and **Unverified** when a figure circulates on leaderboards but could not be traced to a specific published number.

### Comparison table

| Method (paper) | Year | Benchmark / task | Reported metric (as stated by source) | Type | Verified |
|---|---|---|---|---|---|
| Supervised CNNs, resnet/inception (Strodthoff et al.) | 2021 | PTB-XL, all statement tasks | resnet- and inception-based CNNs "show the strongest performance across all tasks" (exact macro-AUROC in paper tables) | Journal | ✓ (qualitative claim); ✗ (exact AUROC not read from abstract) |
| Contrastive predictive coding, SSL (Mehari & Strodthoff) | 2022 | PTB-XL, linear evaluation | linear-eval "only 0.5% below supervised"; fine-tuned "roughly 1%" above supervised | Journal | ✓ |
| PCLR, patient-contrastive SSL (Diamant et al.) | 2022 | 4 clinical tasks, large private cohort | "51% performance increase, on average" over from-scratch across 6 training-set sizes and 4 tasks | Journal | ✓ |
| 12-lead supervised DNN (Ribeiro et al.) | 2020 | CODE test set, 6 abnormalities | F1 "above 80%" and specificity "over 99%" | Journal | ✓ |
| Single-lead supervised DNN (Hannun et al.) | 2019 | Ambulatory single-lead, 12 rhythm classes | "cardiologist-level" detection and classification | Journal | ✓ (qualitative); exact ROC-AUC in paper |
| SSL at scale (Lai et al.) | 2023 | Wearable 12-lead, 60 diagnostic terms | average AUROC 0.975 and average F1 0.575 (offline test) | Journal | ✓ |
| "xresnet1d101 ~0.94 macro-AUROC on PTB-XL" (leaderboard claim) | n/a | PTB-XL, all | circulates on public leaderboards; could not be traced to a specific peer-reviewed number this session | Leaderboard | ✗ Unverified |

### Notes appended to the table

- The Strodthoff et al. benchmark is the reference point for PTB-XL: it establishes the tasks and the supervised ceiling that the SSL rows (Mehari & Strodthoff) are measured against. Those two rows *are* comparable to each other because both use PTB-XL.
- The PCLR, Ribeiro, Hannun, and Lai rows use different datasets and metrics; they characterize the broader landscape, not a single ranking.
- The final row is included to show the flag in action: a number seen on a leaderboard is not admitted to the table as fact until it is traced to a source. It stays marked Unverified.

### References

- Diamant, N., et al. (2022). Patient contrastive learning. *PLOS Computational Biology, 18*(2), e1009862. https://doi.org/10.1371/journal.pcbi.1009862
- Hannun, A. Y., et al. (2019). Cardiologist-level arrhythmia detection and classification in ambulatory electrocardiograms using a deep neural network. *Nature Medicine, 25*(1), 65-69. https://doi.org/10.1038/s41591-018-0268-3
- Lai, J., et al. (2023). Practical intelligent diagnostic algorithm for wearable 12-lead ECG via self-supervised learning on large-scale dataset. *Nature Communications, 14*, 3741. https://doi.org/10.1038/s41467-023-39472-8
- Mehari, T., & Strodthoff, N. (2022). Self-supervised representation learning from 12-lead ECG data. *Computers in Biology and Medicine, 141*, 105114. https://doi.org/10.1016/j.compbiomed.2021.105114
- Ribeiro, A. H., et al. (2020). Automatic diagnosis of the 12-lead ECG using a deep neural network. *Nature Communications, 11*, 1760. https://doi.org/10.1038/s41467-020-15432-4
- Strodthoff, N., Wagner, P., Schaeffter, T., & Samek, W. (2021). Deep Learning for ECG Analysis: Benchmarks and Insights from PTB-XL. *IEEE Journal of Biomedical and Health Informatics, 25*(5), 1519-1528. https://doi.org/10.1109/jbhi.2020.3022989

## What this demonstrates

- Every number in the table is attributed to the source that reported it, in that source's own metric, rather than being harmonized into a single misleading ranking.
- The skill refuses to enter a leaderboard figure it cannot trace to a published number, and marks it Unverified instead of quietly including it.
- Cross-dataset non-comparability is stated up front, which is the methodological honesty a related-work table should model.
- Verified and Unverified flags make the provenance of each row auditable.
