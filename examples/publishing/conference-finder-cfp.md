# Example: Conference and CFP Finder

| Field | Value |
|---|---|
| Skill | conference-finder |
| Command | /researcher:find-conference |
| Trigger phrase | "Find conferences and workshops where I could submit my SSL-for-ECG work" |
| Connectors used | venue homepages (for scope and typical timing) |
| Generated | 2026-07-12 |

## Invocation

> Find conferences and workshops where I could submit my SSL-for-ECG arrhythmia work. Give me deadlines and format, and flag anything time-sensitive.

## Input

Manuscript scope (machine learning on physiological signals / clinical ECG). Preference: peer-reviewed venues with published proceedings.

## Output

### Handling of deadlines

Submission deadlines shift every cycle. Exact dates are **not** invented here. Each row gives the venue's stable characteristics and its **typical** timing, and marks the exact next-cycle date as **[confirm current CFP, as of 2026-07-12]** with the homepage to check. Verify before relying on any date.

### Venue table

| Venue | Type | Typical timing | Format | Fit | Confirm at |
|---|---|---|---|---|---|
| Computing in Cardiology (CinC) | Conference (IEEE/CinC proceedings) | Abstracts typically due spring; conference in September | 4-page paper via PhysioNet/CinC challenge or regular track | Very high: the ECG/PhysioNet community's home venue; PTB-XL and related datasets are native here | cinc.org **[confirm CFP, as of 2026-07-12]** |
| IEEE EMBC (Engineering in Medicine and Biology Conference) | Conference (IEEE) | Full-paper deadline typically late winter/early spring; conference in July | 4-page paper, `IEEEtran` conference | High: broad biomedical engineering audience, established ECG track | embc.embs.org **[confirm CFP, as of 2026-07-12]** |
| CHIL (Conference on Health, Inference, and Learning) | Conference (PMLR proceedings) | Abstract/paper deadlines typically winter; conference in summer | 8-10 page PMLR format | High: ML-for-health methods venue; lead-agnostic ECG SSL (Oh et al., 2022) appeared here | chilconference.org **[confirm CFP, as of 2026-07-12]** |
| Machine Learning for Health (ML4H) | Symposium/workshop (PMLR proceedings) | Submissions typically late summer; event in late autumn (co-located with NeurIPS in some years) | Proceedings and findings tracks, PMLR format | High: 3KG ECG SSL (Gopal et al., 2021) appeared here; welcoming to methods papers | ml4h.cc **[confirm CFP, as of 2026-07-12]** |
| IEEE-EMBS BHI (International Conference on Biomedical and Health Informatics) | Conference (IEEE) | Deadlines typically spring; conference in autumn | Paper via `IEEEtran` | Medium-high: health-informatics and signals audience; pairs with the JBHI journal community | bhi.embs.org **[confirm CFP, as of 2026-07-12]** |

### Recommendation

For fastest peer-reviewed exposure to the exact ECG/PhysioNet community, target **Computing in Cardiology** or **ML4H**. For an archival PMLR methods paper with a strong ML-for-health audience, target **CHIL**. If the goal is to convert to the journal version afterward, **IEEE-EMBS BHI** aligns naturally with the IEEE JBHI submission planned in the journal-finder example.

### Sources (venue relevance grounded in real prior publications)

- Oh, J., et al. (2022). Lead-agnostic self-supervised learning for ECG. *CHIL (PMLR)*. arXiv:2203.06889
- Gopal, B., et al. (2021). 3KG: Contrastive learning of 12-lead ECG. *ML4H (PMLR)*. arXiv:2106.04452

## What this demonstrates

- Real venues are matched to the manuscript by evidence: the fit column names actual prior ECG-SSL papers published at CHIL and ML4H, so the recommendation is grounded, not generic.
- Time-sensitive facts (exact deadlines) are never fabricated; each row gives stable typical timing and flags the exact date for confirmation at the venue homepage with the access date, per the grounding protocol.
- The recommendation connects to the journal-finder example (BHI to JBHI), keeping a coherent submission strategy across the publishing set.
