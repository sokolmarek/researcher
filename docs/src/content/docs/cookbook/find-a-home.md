---
title: Find a home for the paper
description: A cookbook recipe for shortlisting a journal, scouting conferences, and drafting the cover letter without inventing a single impact factor.
sidebar:
  label: Find a home
  order: 5
---

The manuscript compiles, the figures are honest, and now the paper needs somewhere to live. This recipe walks the running scenario (self-supervised contrastive pretraining for ECG arrhythmia classification, evaluated on PTB-XL) through three steps: rank target journals, scout conferences, and write the cover letter to the top pick.

One rule threads all three steps. Volatile facts (impact factors, article processing charges, submission deadlines) drift every cycle, so the assistant never fabricates them. Each one is tagged `[confirm at source, as of <date>]` with the page to check. Stable facts (scope, publisher, document class, citation style, required sections) are stated directly. If you remember only one thing from this page, remember that a number without a date is a liability.

## Step 1: Rank the journals

Run `/researcher:find-journal` and describe the contribution, not just the topic. Fit is argued from evidence, meaning which venue actually published your predecessors and your benchmark, rather than from raw prestige.

> Recommend target journals for my methods paper on self-supervised contrastive pretraining for ECG arrhythmia classification, evaluated on PTB-XL. I want fit rationale and format notes. Rank them.

The ranked shortlist for the running scenario:

**1. IEEE Journal of Biomedical and Health Informatics (JBHI): strongest fit.** The PTB-XL benchmark this manuscript is measured against was itself published here (Strodthoff et al., 2021, [10.1109/jbhi.2020.3022989](https://doi.org/10.1109/jbhi.2020.3022989)). Reviewers will already know the benchmark. Format: `IEEEtran` journal option, numbered IEEE citations, `IEEEtran.bst`, Index Terms required, typical length 10 to 14 pages. Access: hybrid open access, APC only for the OA option `[confirm current APC and impact factor at the ieee.org JBHI page, as of 2026-07-12]`.

**2. Computers in Biology and Medicine (Elsevier): very strong fit.** Published the closest methodological predecessor (Mehari and Strodthoff, self-supervised representation learning from 12-lead ECG, 2022, [10.1016/j.compbiomed.2021.105114](https://doi.org/10.1016/j.compbiomed.2021.105114)) and welcomes computational methods on biomedical signals. Format: `elsarticle` `3p` option, numbered citations, Highlights (3 to 5 bullets, max 85 chars), Data Availability Statement, and CRediT contributions. Access: hybrid, gold OA optional `[confirm current APC and CiteScore at the journal homepage, as of 2026-07-12]`.

**3. npj Digital Medicine (Nature Portfolio): high impact, broader framing needed.** Sibling Nature Portfolio journals publish SSL-at-scale ECG work (Lai et al., 2023, in *Nature Communications*), and npj Digital Medicine published generalization-in-medical-AI work (Ong Ly et al., 2024). Prestigious and fully open access, but it favors clinical impact and external validation over pure methods, so the paper would need a stronger deployment angle. Format: Nature-family style, numbered superscript citations, roughly 3000-word main text with Methods after references, mandatory Data and Code Availability. Access: gold open access, APC required `[confirm current APC at nature.com/npjdigitalmed, as of 2026-07-12]`.

**4. IEEE Transactions on Biomedical Engineering (TBME): strong fit, more engineering-leaning.** A long-standing venue for ECG signal-processing methods; audience overlaps with JBHI but skews toward biomedical engineering fundamentals. Format: `IEEEtran`, numbered citations, typical length 8 to 11 pages. Access: hybrid `[confirm APC and impact factor at the ieee.org TBME page, as of 2026-07-12]`.

**5. Physiological Measurement (IOP Publishing): solid, more specialized fit.** Focused on measurement and analysis of physiological signals including ECG, a natural home for a signal-representation contribution, though lower general visibility than the IEEE Transactions. Format: IOP article class, numbered citations (Vancouver-like). Access: hybrid, gold OA optional `[confirm APC at iopscience.iop.org, as of 2026-07-12]`.

**Recommendation:** submit to **IEEE JBHI** first. The benchmark match, the receptive audience, and the `IEEEtran` scaffold already in place make it the lowest-friction, best-fit target. Hold **Computers in Biology and Medicine** as the immediate fallback (same community, method-friendly). Reserve **npj Digital Medicine** for a version with external validation.

Notice every impact factor and APC carries a date and a source. Scope and format do not, because they do not change between coffee breaks.

## Step 2: Scout the conferences

Maybe you want peer-reviewed exposure before the journal cycle finishes, or an archival proceedings paper alongside it. Run `/researcher:find-conference`.

> Find conferences and workshops where I could submit my SSL-for-ECG arrhythmia work. Give me deadlines and format, and flag anything time-sensitive.

Deadlines shift every cycle, so exact dates are never invented. Each row gives stable characteristics and *typical* timing, then flags the exact next-cycle date for confirmation at the homepage.

| Venue | Type | Typical timing | Format | Fit | Confirm at |
|---|---|---|---|---|---|
| Computing in Cardiology (CinC) | Conference (IEEE/CinC proceedings) | Abstracts typically due spring; conference in September | 4-page paper, PhysioNet/CinC challenge or regular track | Very high: the ECG/PhysioNet community's home venue; PTB-XL is native here | cinc.org `[confirm CFP, as of 2026-07-12]` |
| IEEE EMBC | Conference (IEEE) | Full-paper deadline typically late winter to early spring; conference in July | 4-page paper, `IEEEtran` conference | High: broad biomedical engineering audience, established ECG track | embc.embs.org `[confirm CFP, as of 2026-07-12]` |
| CHIL (Health, Inference, and Learning) | Conference (PMLR proceedings) | Abstract/paper deadlines typically winter; conference in summer | 8 to 10 page PMLR format | High: ML-for-health methods venue; lead-agnostic ECG SSL (Oh et al., 2022) appeared here | chilconference.org `[confirm CFP, as of 2026-07-12]` |
| Machine Learning for Health (ML4H) | Symposium/workshop (PMLR proceedings) | Submissions typically late summer; event in late autumn | Proceedings and Findings tracks, PMLR format | High: 3KG ECG SSL (Gopal et al., 2021) appeared here; welcoming to methods papers | ml4h.cc `[confirm CFP, as of 2026-07-12]` |
| IEEE-EMBS BHI | Conference (IEEE) | Deadlines typically spring; conference in autumn | Paper via `IEEEtran` | Medium-high: health-informatics and signals audience; pairs with the JBHI community | bhi.embs.org `[confirm CFP, as of 2026-07-12]` |

**Recommendation:** for fastest peer-reviewed exposure to the exact ECG/PhysioNet community, target **Computing in Cardiology** or **ML4H**. For an archival PMLR methods paper, target **CHIL**. If the goal is to convert to the journal version afterward, **IEEE-EMBS BHI** aligns naturally with the planned JBHI submission, since the same community reads both.

The fit column names real prior papers (Oh et al., 2022, arXiv:2203.06889; Gopal et al., 2021, arXiv:2106.04452), so the match is grounded rather than a vibe.

## Step 3: Write the cover letter

With JBHI as the top pick, the cover letter states the fit in one verifiable sentence and keeps the results in the paper where they belong.

> Write a submission cover letter to IEEE JBHI for my SSL-for-ECG manuscript. Use the standard template, state the fit, and keep the results out of it since they belong in the paper.

The output compiles with `tectonic cover-letter.tex` using the `letter` class. The body:

> Dear Editor,
>
> We are pleased to submit our manuscript entitled "Self-Supervised Contrastive Pretraining for Label-Efficient ECG Arrhythmia Classification" for consideration for publication in *IEEE Journal of Biomedical and Health Informatics*.
>
> Diagnostic annotation of the electrocardiogram is expensive and rare conditions are underrepresented, which limits supervised deep learning for ECG analysis. In this work we pretrain an ECG encoder on unlabeled 12-lead recordings using a contrastive objective with physiologically grounded augmentations, then fine-tune on the public PTB-XL benchmark under its standardized evaluation protocol. We report a controlled label-efficiency study isolating the contribution of pretraining from the evaluation protocol, and an ablation of augmentation families. (Specific results are reported in the manuscript.)
>
> We believe this manuscript is well suited for *IEEE Journal of Biomedical and Health Informatics* because the journal defined the PTB-XL benchmarking protocol against which our method is measured, and its readership works directly on machine learning for physiological signals. Our emphasis on reproducible, protocol-matched evaluation speaks to that audience.
>
> This manuscript has not been published elsewhere and is not under consideration by any other journal. All authors have read and approved the final manuscript, and we declare no conflicts of interest. All code and the derived data splits supporting this study will be made available in a public repository upon acceptance; PTB-XL is publicly available from its original providers.
>
> Sincerely,

Three things this letter does on purpose. The fit paragraph gives a concrete reason (JBHI defined the PTB-XL protocol the paper uses) instead of flattery. It withholds specific numeric results, keeping unproven figures out of a document that is not the paper. And it covers the editor's checklist: submission statement, contribution summary, fit, originality and exclusivity, conflict of interest, and data availability. Author identity is synthetic, for demonstration.

## The through-line

The three steps chain into one coherent strategy: BHI (conference) feeds JBHI (journal), and the cover letter reuses the exact fit argument from the journal shortlist. Nothing volatile crosses your desk without a date and a source next to it. The assistant is picking a home for your paper, not co-authoring it, and it will not guess an impact factor to save you a click.

## Keep going

- The full workflow, with the grounding protocol and format database, lives in the [publishing and formatting guide](/researcher/guides/publishing-and-formatting/).
- The complete example files (journal report, CFP table, cover letter source) are in the [publishing examples on GitHub](https://github.com/sokolmarek/researcher/tree/main/examples/publishing).
