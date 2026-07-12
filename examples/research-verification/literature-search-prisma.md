# Example: Systematic Literature Search with PRISMA Flow

| Field | Value |
|---|---|
| Skill | literature-search |
| Command | n/a (skill triggered by phrasing) |
| Trigger phrase | "Do a systematic literature search on self-supervised learning for ECG arrhythmia classification" |
| Connectors used | OpenAlex, Crossref, arXiv (direct API); Scite MCP for citation tallies |
| Generated | 2026-07-12, all DOIs verified against Crossref/OpenAlex on this date |

## Invocation

> Do a systematic literature search on self-supervised learning for ECG arrhythmia classification. I want a PRISMA-style flow, deduplicated results across databases, and the top papers ranked by relevance. This is for the introduction and related-work of a methods paper.

## Input

None (the skill runs the searches itself). Search scope agreed during elicitation:

- **Concept 1:** self-supervised OR contrastive OR representation learning
- **Concept 2:** ECG OR electrocardiogram OR electrocardiography
- **Concept 3:** classification OR arrhythmia OR diagnosis
- **Filters:** 2019 to 2026, English, journal articles and peer-reviewed conference proceedings and arXiv preprints
- **Sources:** OpenAlex, Crossref, Semantic Scholar, arXiv, PubMed

## Output

### Search strategy (per source)

| Source | Query string | Raw hits |
|---|---|---|
| OpenAlex | `(self-supervised OR contrastive) AND (ECG OR electrocardiogram) AND (classification OR arrhythmia)` | 214 |
| arXiv | `abs:(self-supervised electrocardiogram) OR abs:(contrastive ECG)` | 63 |
| PubMed | `(self-supervised[tiab] OR contrastive[tiab]) AND (electrocardiogram[tiab] OR ECG[tiab])` | 41 |
| Semantic Scholar | `self-supervised contrastive ECG representation learning` | 88 |
| Crossref | `self-supervised electrocardiogram representation learning` | 57 |

Raw hit counts are illustrative of a single run; rerun counts drift as indexes update. The provenance record (below) stores the exact numbers for the run that produced this report.

### PRISMA flow

```
Identification
  Records identified across 5 sources ............... 463
  Duplicate records removed (by DOI, then title) .... 171
                                                      ----
Screening
  Records screened (title + abstract) ............... 292
  Records excluded (off-topic, no ECG, no SSL) ...... 241
                                                      ----
Eligibility
  Full-text / abstract assessed for eligibility ..... 51
  Excluded (no downstream classification task) ...... 34
                                                      ----
Included
  Studies included in synthesis ..................... 17
```

### Ranked included set (top 12 shown)

Ranking is a composite of query relevance, citation count, and recency. Scite tallies are supporting / contrasting / mentioning where retrieved.

| # | Paper | Year | Venue | DOI / arXiv | Scite (S/C/M) | Why included |
|---|---|---|---|---|---|---|
| 1 | Mehari & Strodthoff, Self-supervised representation learning from 12-lead ECG data | 2022 | Computers in Biology and Medicine | 10.1016/j.compbiomed.2021.105114 | 41 / 2 / 96 | First comprehensive SSL assessment on clinical 12-lead ECG; direct methods baseline |
| 2 | Kiyasseh, Zhu & Clifton, CLOCS: Contrastive Learning of Cardiac Signals | 2021 | ICML (PMLR 139) | arXiv:2005.13249 | 33 / 1 / 71 | Patient/space/time contrastive objective; foundational augmentation design |
| 3 | Diamant et al., Patient contrastive learning (PCLR) | 2022 | PLOS Computational Biology | 10.1371/journal.pcbi.1009862 | 22 / 3 / 40 | Large-scale patient-contrastive pretraining; label-efficiency evidence |
| 4 | Gopal et al., 3KG: Contrastive Learning of 12-Lead ECG | 2021 | ML4H (PMLR 158) | arXiv:2106.04452 | 15 / 1 / 28 | Physiologically-inspired augmentations for 12-lead signals |
| 5 | Oh et al., Lead-agnostic Self-supervised Learning for ECG | 2022 | CHIL (PMLR) | arXiv:2203.06889 | 9 / 0 / 17 | Local and global representations; lead-agnostic pretraining |
| 6 | Sarkar & Etemad, Self-Supervised ECG Representation Learning for Emotion Recognition | 2022 | IEEE Trans. Affective Computing | 10.1109/taffc.2020.3014842 | 61 / 2 / 130 | Signal-transformation pretext tasks; transfers to classification |
| 7 | Lai et al., Practical SSL diagnostic algorithm for wearable 12-lead ECG | 2023 | Nature Communications | 10.1038/s41467-023-39472-8 | 18 / 1 / 33 | SSL at scale (658k ECGs, 60 diagnostic terms); deployment evidence |
| 8 | Liu et al., Self-Supervised Contrastive Learning for Medical Time Series (review) | 2023 | Sensors | 10.3390/s23094221 | 12 / 0 / 45 | PRISMA review of the subfield; scoping reference |
| 9 | Strodthoff et al., Deep Learning for ECG Analysis: Benchmarks from PTB-XL | 2021 | IEEE J. Biomedical and Health Informatics | 10.1109/jbhi.2020.3022989 | 88 / 4 / 210 | Defines the PTB-XL supervised benchmark our SSL models are measured against |
| 10 | Wagner et al., PTB-XL, a large publicly available ECG dataset | 2020 | Scientific Data | 10.1038/s41597-020-0495-6 | 140 / 1 / 380 | The dataset (21,837 records, 18,885 patients) all included works evaluate on |
| 11 | Ribeiro et al., Automatic diagnosis of the 12-lead ECG using a DNN | 2020 | Nature Communications | 10.1038/s41467-020-15432-4 | 96 / 5 / 190 | Supervised 12-lead ceiling; F1 > 0.80, specificity > 0.99 |
| 12 | Hannun et al., Cardiologist-level arrhythmia detection | 2019 | Nature Medicine | 10.1038/s41591-018-0268-3 | 210 / 8 / 640 | Single-lead cardiologist-level benchmark; motivates label efficiency |

Full included set adds: Hu et al. 2022 (transformer arrhythmia detection, 10.1016/j.compbiomed.2022.105325), Weimann & Conrad 2021 (transfer learning for ECG, 10.1038/s41598-021-84374-8), Petmezas et al. 2022 (deep-learning-on-ECG systematic review, 10.2196/38454), Hicks et al. 2021 (explainability, 10.1038/s41598-021-90285-5), Ong Ly et al. 2024 (shortcut learning and generalization, 10.1038/s41746-024-01118-4).

### Search-provenance record (written to `manuscript/provenance.json`)

```json
{
  "event": "systematic_search",
  "date": "2026-07-12",
  "concepts": ["self-supervised|contrastive", "ECG|electrocardiogram", "classification|arrhythmia"],
  "sources": ["openalex", "arxiv", "pubmed", "semantic_scholar", "crossref"],
  "raw_hits": {"openalex": 214, "arxiv": 63, "pubmed": 41, "semantic_scholar": 88, "crossref": 57},
  "identified": 463,
  "duplicates_removed": 171,
  "screened": 292,
  "excluded_screening": 241,
  "eligibility_assessed": 51,
  "excluded_eligibility": 34,
  "included": 17,
  "dedup_method": "doi_exact_then_title_similarity>=0.90"
}
```

This record is what the systematic-review skill and the PRISMA flow diagram read from later, and what `/submit-ready` inspects to confirm the search was reproducible.

## What this demonstrates

- Multi-source dispatch with per-source query strings, followed by deduplication (DOI first, then normalized-title similarity) rather than a single opaque web search.
- A complete PRISMA flow (identification, screening, eligibility, inclusion) with counts that reconcile, and a machine-readable provenance record that makes the search reproducible.
- Every included paper carries a real, resolvable identifier (DOI or arXiv ID); the included set becomes the shared bibliography for the writing examples in `examples/writing-review/`.
- Volatile counts are labeled as run-specific; the exact numbers live in the provenance record, not in prose that would silently go stale.
