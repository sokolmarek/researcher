# Example: Journal Recommendation Report

| Field | Value |
|---|---|
| Skill | journal-finder |
| Command | /find-journal |
| Trigger phrase | "Recommend target journals for my SSL-for-ECG methods paper" |
| Connectors used | `references/journal-database.md`; journal scope pages |
| Generated | 2026-07-12 |

## Invocation

> Recommend target journals for my methods paper on self-supervised contrastive pretraining for ECG arrhythmia classification, evaluated on PTB-XL. I want fit rationale and format notes. Rank them.

## Input

- Manuscript scope: methods contribution, biomedical signal processing, deep learning, evaluated on a public clinical ECG benchmark.
- Preferences elicited: open to hybrid or gold open access; prefers venues that publish reproducible deep-learning-on-physiological-signals work.

## Output

### Handling of volatile metrics

Impact factors and article processing charges change and are not fabricated here. Each volatile figure is marked **[confirm at source, as of 2026-07-12]** with the page to check. Scope, publisher, document class, and citation style are stable and stated directly.

### Ranked shortlist

**1. IEEE Journal of Biomedical and Health Informatics (JBHI): strongest fit**

- **Why:** The PTB-XL benchmark that this manuscript is evaluated against was itself published here (Strodthoff et al., 2021, 10.1109/jbhi.2020.3022989). The journal's scope centers on informatics and machine learning for health data, including physiological signals. Reviewers will know the benchmark.
- **Format:** `IEEEtran` (journal option), numbered IEEE citations, `IEEEtran.bst`. Typical length 10-14 pages. Index Terms required.
- **Access / cost:** hybrid open access; APC applies only for the OA option. **[confirm current APC and impact factor at ieee.org JBHI page, as of 2026-07-12]**

**2. Computers in Biology and Medicine (Elsevier): very strong fit**

- **Why:** Published the closest methodological predecessor (Mehari & Strodthoff, self-supervised representation learning from 12-lead ECG, 2022, 10.1016/j.compbiomed.2021.105114) and the transformer-arrhythmia work (Hu et al., 2022). Explicitly welcomes computational methods on biomedical signals.
- **Format:** `elsarticle` (`3p` option), numbered citations, Highlights (3-5 bullets, max 85 chars) and a Data Availability Statement required, CRediT contributions.
- **Access / cost:** hybrid; gold OA optional. **[confirm current APC and CiteScore at journal homepage, as of 2026-07-12]**

**3. npj Digital Medicine (Nature Portfolio): high impact, broader framing needed**

- **Why:** Published SSL-at-scale ECG work (Lai et al., 2023) and generalization-in-medical-AI work (Ong Ly et al., 2024). Prestigious and fully open access. Caveat: favors clinical impact and validation over pure methods, so the manuscript would need a stronger deployment or external-validation angle to fit.
- **Format:** Nature-family style, numbered superscript citations, ~3000-word main text with Methods after references, mandatory Data and Code Availability.
- **Access / cost:** gold open access, APC required. **[confirm current APC at nature.com/npjdigitalmed, as of 2026-07-12]**

**4. IEEE Transactions on Biomedical Engineering (TBME): strong fit, more engineering-leaning**

- **Why:** Long-standing venue for ECG signal-processing methods; audience overlaps with JBHI but skews toward biomedical engineering fundamentals. Good second-choice IEEE option.
- **Format:** `IEEEtran`, numbered citations. Typical length 8-11 pages.
- **Access / cost:** hybrid. **[confirm APC and impact factor at ieee.org TBME page, as of 2026-07-12]**

**5. Physiological Measurement (IOP Publishing): solid, more specialized fit**

- **Why:** Focused on measurement and analysis of physiological signals, including ECG; a natural home for a signal-representation contribution, though lower general visibility than the IEEE Transactions.
- **Format:** IOP article class, numbered citations (Vancouver-like).
- **Access / cost:** hybrid; gold OA optional. **[confirm APC at iopscience.iop.org, as of 2026-07-12]**

### Recommendation

Submit to **IEEE JBHI** first: the benchmark match, the receptive audience, and the `IEEEtran` scaffold already generated in the manuscript-setup example make it the lowest-friction, best-fit target. Hold **Computers in Biology and Medicine** as the immediate fallback (same community, method-friendly). Reserve **npj Digital Medicine** for a version with external validation.

### Sources

- Strodthoff, N., et al. (2021). *IEEE JBHI, 25*(5), 1519-1528. https://doi.org/10.1109/jbhi.2020.3022989
- Mehari, T., & Strodthoff, N. (2022). *Computers in Biology and Medicine, 141*, 105114. https://doi.org/10.1016/j.compbiomed.2021.105114
- Lai, J., et al. (2023). *Nature Communications, 14*, 3741. https://doi.org/10.1038/s41467-023-39472-8 (authors' related npj work referenced for scope)
- Format details: `references/journal-database.md`

## What this demonstrates

- Fit is argued from evidence (which target venue published the manuscript's actual predecessors and benchmark), not from generic prestige.
- Volatile metrics (impact factor, APC) are never fabricated; each is tagged for confirmation at a named source with the access date, per the grounding protocol.
- Format facts that are stable (document class, citation style, required sections) are stated directly and match `references/journal-database.md`.
- The top recommendation (IEEE JBHI) is the journal targeted by the manuscript-setup and cover-letter examples, keeping the publishing set consistent.
