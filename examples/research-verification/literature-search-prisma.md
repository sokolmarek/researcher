# Example: Systematic Literature Search with PRISMA Flow

| Field | Value |
|---|---|
| Skill | literature-search |
| Command | n/a (skill triggered by phrasing) |
| Trigger phrase | "Do a systematic literature search on self-supervised learning for ECG arrhythmia classification" |
| Connectors used | Search sources: OpenAlex, Crossref, Semantic Scholar, arXiv, PubMed (direct APIs). Scite MCP for citation tallies (rate-limited at authoring, so the tallies shown are illustrative, not retrieved) |
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

### Provenance key (read this before the numbers)

This example uses exactly two provenance labels, and each means one thing only:

- **Verified.** Retrieved while authoring and checked against the index named. Every paper, year, venue, DOI, and arXiv ID in the ranked set below is verified, and every identifier resolves.
- **Illustrative.** Not retrieved. The value is there to show the shape of the field and what a real run puts in it. Illustrative values are excluded from the verified citation record, and an executed search overwrites them.

Illustrative in this example: the per-source raw hit counts, the PRISMA counts computed from them, and the Scite supporting/contrasting/mentioning tallies (the Scite MCP was rate-limited at authoring). Everything else is verified.

### Search strategy (per source)

| Source | Query string | Raw hits |
|---|---|---|
| OpenAlex | `(self-supervised OR contrastive) AND (ECG OR electrocardiogram) AND (classification OR arrhythmia)` | 214 |
| arXiv | `abs:(self-supervised electrocardiogram) OR abs:(contrastive ECG)` | 63 |
| PubMed | `(self-supervised[tiab] OR contrastive[tiab]) AND (electrocardiogram[tiab] OR ECG[tiab])` | 41 |
| Semantic Scholar | `self-supervised contrastive ECG representation learning` | 88 |
| Crossref | `self-supervised electrocardiogram representation learning` | 57 |

**Provenance: illustrative.** The query strings are the ones this skill builds for the agreed scope, but the raw hit counts were not retrieved. They stand in for what a run of this scope returns, at a plausible scale. On a real run the skill writes its own counts here and into the provenance record below, and those counts drift between runs as the indexes update.

### PRISMA flow (counts illustrative, not retrieved)

The block below is the PRISMA flow the skill emits: it traces every record from identification across the five sources, through deduplication, title-and-abstract screening, and eligibility assessment, down to the studies included in the synthesis.

**Provenance: illustrative.** These counts were not retrieved. They show the shape of a PRISMA flow and the arithmetic it must satisfy, namely that each stage reconciles with the one before it (214 + 63 + 41 + 88 + 57 = 463 identified; 463 - 171 duplicates = 292 screened; 292 - 241 excluded = 51 assessed; 51 - 34 excluded = 17 included). An executed search produces its own counts, which must reconcile the same way.

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

Ranking is a composite of query relevance, citation count, and recency. Every paper, year, venue, and identifier in this table is **verified**: the DOIs and arXiv IDs were resolved against Crossref and OpenAlex on 2026-07-12 and all of them resolve.

The one exception is the Scite column, which shows supporting / contrasting / mentioning tallies. The Scite MCP was rate-limited during authoring, so those values are **illustrative**: they mark where the tallies appear, they were not retrieved, and they are excluded from the verified citation record. When the Scite connector is available, this skill populates the column from actual Smart Citations and records them in the provenance JSON.

| # | Paper | Year | Venue | DOI / arXiv | Scite (S/C/M, illustrative) | Why included |
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
| 10 | Wagner et al., PTB-XL, a large publicly available ECG dataset | 2020 | Scientific Data | 10.1038/s41597-020-0495-6 | 140 / 1 / 380 | The dataset (21,837 records, 18,885 patients) this manuscript evaluates on, and the most common benchmark in the included set. Several included works evaluate elsewhere (CODE, private cohorts, single-lead ambulatory data), which is exactly why the SOTA example flags cross-dataset comparisons as not directly comparable |
| 11 | Ribeiro et al., Automatic diagnosis of the 12-lead ECG using a DNN | 2020 | Nature Communications | 10.1038/s41467-020-15432-4 | 96 / 5 / 190 | Supervised 12-lead ceiling; F1 > 0.80, specificity > 0.99 |
| 12 | Hannun et al., Cardiologist-level arrhythmia detection | 2019 | Nature Medicine | 10.1038/s41591-018-0268-3 | 210 / 8 / 640 | Single-lead cardiologist-level benchmark; motivates label efficiency |

Full included set adds: Hu et al. 2022 (transformer arrhythmia detection, 10.1016/j.compbiomed.2022.105325), Weimann & Conrad 2021 (transfer learning for ECG, 10.1038/s41598-021-84374-8), Petmezas et al. 2022 (deep-learning-on-ECG systematic review, 10.2196/38454), Hicks et al. 2021 (explainability, 10.1038/s41598-021-90285-5), Ong Ly et al. 2024 (shortcut learning and generalization, 10.1038/s41746-024-01118-4).

### Search-provenance record (written to `manuscript/provenance.json`)

This is the record the skill writes next to the manuscript. Two separate caveats apply to it, and it
is worth keeping them apart.

**Provenance: illustrative.** The numbers below are the illustrative ones from the tables above, so
the record shown here is illustrative too. An executed search writes its own counts in this shape.

**Shape: aggregate-only.** Even on a real run, this record holds counts and the dedup method, which
is enough to redraw the PRISMA flow but not enough to reproduce the search. It carries no raw record
identifiers, no pagination state, no response snapshots, no deduplication clusters, and no per-record
screening decisions, so a reader cannot replay the run from it. The append-only per-record event
ledger that makes a run replayable (retrieval, record_lineage, dedup_decision, and
screening_decision events, with response hashes and PRISMA counts derived by aggregation) is planned,
not implemented; when it lands, this block is regenerated from it.

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

This record is what the systematic-review skill and the PRISMA flow diagram read from today. Both
caveats above hold: it summarizes a run, it does not make one replayable.

## What this demonstrates

- Multi-source dispatch with per-source query strings, followed by deduplication (DOI first, then normalized-title similarity) rather than a single opaque web search.
- A complete PRISMA flow (identification, screening, eligibility, inclusion) whose counts reconcile stage by stage, plus a machine-readable provenance record that is explicit about what it does and does not capture (aggregate counts today; a per-record event ledger is planned, not implemented).
- Every included paper carries a real, resolvable identifier (DOI or arXiv ID); the included set becomes the shared bibliography for the writing examples in `examples/writing-review/`.
- One provenance vocabulary applied consistently: every number is labeled either verified (retrieved and checked) or illustrative (not retrieved). The counts and the Scite tallies here are illustrative and say so at each point of use, so no reader mistakes them for retrieved figures.
