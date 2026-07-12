# Example: Drafted Introduction Section

| Field | Value |
|---|---|
| Skill | paper-drafting |
| Command | /draft-section |
| Trigger phrase | "Draft the introduction for my SSL-for-ECG methods paper" |
| Connectors used | none (cites the library.bib produced by the literature-search example) |
| Generated | 2026-07-12; all \cite keys resolve to the shared `references/library.bib` built from the literature-search example's included set (`examples/research-verification/literature-search-prisma.md`); the citation-audit example verifies a representative subset |

## Invocation

> Draft the introduction for my methods paper on self-supervised contrastive pretraining for ECG arrhythmia classification. Funnel structure, about 600 words, cite the papers already in my library, and end with explicit contributions.

## Input

- `manuscript/config.yaml` (from the manuscript-setup example)
- `manuscript/references/library.bib` (the verified included set from the literature-search example)
- Target length: ~600 words; style: IEEE, numbered citations

The prose below is `(synthetic, for demonstration)`: it is written to show drafting behavior, and the empirical contributions it states are illustrative, not real results.

## Output

### `introduction.tex`

```latex
\section{Introduction}

Automated interpretation of the electrocardiogram (ECG) has advanced rapidly
with deep learning. Deep neural networks now detect and classify arrhythmias
from single-lead ambulatory recordings at a level comparable to
cardiologists~\cite{hannun2019cardiologist}, and 12-lead models trained on
large clinical corpora recognize multiple abnormality classes with high
specificity~\cite{ribeiro2020automatic}. The release of PTB-XL, a freely
available clinical 12-lead dataset of 21{,}837 records from 18{,}885
patients~\cite{wagner2020ptbxl}, together with standardized benchmarking
protocols~\cite{strodthoff2021benchmark}, has made these systems directly
comparable for the first time.

Despite this progress, supervised ECG models remain constrained by label
scarcity. Diagnostic annotation requires expert cardiologists, rare conditions
are underrepresented, and models trained on one cohort often fail to generalize
to another~\cite{ongly2024shortcut}. These constraints motivate methods that
learn from the large volumes of \emph{unlabeled} ECG that clinical systems
already record.

Self-supervised learning (SSL) offers such a route. By constructing a pretext
task from the signal itself, SSL learns representations without diagnostic
labels, which are then adapted to downstream classification with far fewer
annotations. Contrastive objectives have been particularly effective on
physiological signals: CLOCS contrasts cardiac signals across space, time, and
patients~\cite{kiyasseh2021clocs}; 3KG introduces physiologically inspired
augmentations for 12-lead data~\cite{gopal20213kg}; patient-contrastive
pretraining yields expressive, label-efficient
representations~\cite{diamant2022pclr}; and lead-agnostic pretraining captures
both local and global ECG structure~\cite{oh2022leadagnostic}. On clinical
12-lead data, a systematic assessment found that the best self-supervised
representation reached linear-evaluation performance within roughly one percent
of fully supervised training, with consistent gains in label
efficiency~\cite{mehari2022ssl}. At scale, SSL has been deployed on hundreds of
thousands of wearable recordings spanning dozens of diagnostic
terms~\cite{lai2023practical}. A recent systematic review catalogs the rapid
growth of contrastive learning for medical time series and the fragmentation of
its evaluation protocols~\cite{liu2023review}.

Two gaps remain. First, augmentation design for ECG is still largely inherited
from computer vision or chosen ad hoc, despite the signal's distinct
physiological structure. Second, comparisons across studies are confounded by
differing datasets, label sets, and metrics, which obscures how much of the
reported benefit is method and how much is protocol. This paper addresses both
on the standardized PTB-XL benchmark.

\smallskip
\noindent\textbf{Contributions.} % illustrative, synthetic
\begin{enumerate}
    \item A contrastive pretraining scheme with physiologically grounded ECG
    augmentations, evaluated end to end on the PTB-XL benchmark under the
    protocol of~\cite{strodthoff2021benchmark}.
    \item A controlled label-efficiency study measuring downstream performance
    as a function of the number of labeled records, isolating the pretraining
    contribution from the evaluation protocol.
    \item An ablation of augmentation families that quantifies which
    signal transformations drive representation quality for arrhythmia
    classification.
\end{enumerate}
```

### Claim-to-citation mapping (what the drafting skill tracks)

| Sentence claim | Citation(s) | Basis |
|---|---|---|
| DNNs reach cardiologist-level arrhythmia detection (single-lead) | hannun2019cardiologist | Nature Medicine 2019 |
| 12-lead models recognize abnormalities with high specificity | ribeiro2020automatic | F1 > 0.80, spec > 0.99 |
| PTB-XL size (21,837 records / 18,885 patients) | wagner2020ptbxl | dataset paper, exact figures |
| Standardized benchmark protocol | strodthoff2021benchmark | IEEE JBHI 2021 |
| Models fail to generalize across cohorts | ongly2024shortcut | npj Digital Medicine 2024 |
| Contrastive objectives effective on ECG | kiyasseh2021clocs, gopal20213kg, diamant2022pclr, oh2022leadagnostic | method papers |
| SSL within ~1% of supervised on 12-lead | mehari2022ssl | "0.5% below" linear-eval |
| SSL deployed at scale on wearables | lai2023practical | 658k ECGs, 60 terms |
| Subfield growth and protocol fragmentation | liu2023review | PRISMA review |

## What this demonstrates

- A funnel-structured introduction (broad progress, then the specific gap, then contributions) with every factual claim carrying a `\cite` key that resolves to the verified library.
- Numbers that appear in prose (21,837 records; within one percent) are the source-verified figures from the grounding step, not approximations.
- The claim-to-citation mapping table is the artifact the drafting skill maintains so the post-draft integrity hook and the citation-audit skill can check that each claim is actually supported by its cited source.
- House style is followed: no em dashes, `{,}` thousands separators for LaTeX, terminology consistent with `terminology.yaml`. The empirical contributions are labeled synthetic because no experiment was run.
