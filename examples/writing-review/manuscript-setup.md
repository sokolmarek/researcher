# Example: New Manuscript Scaffold

| Field | Value |
|---|---|
| Skill | manuscript-setup |
| Command | /researcher:new-manuscript |
| Trigger phrase | "Start a new manuscript" (via the /researcher:new-manuscript form) |
| Connectors used | none |
| Generated | 2026-07-12 |

## Invocation

> /researcher:new-manuscript

Form fields submitted:

| Field | Value |
|---|---|
| title | Self-Supervised Contrastive Pretraining for Label-Efficient ECG Arrhythmia Classification |
| authors | A. Novak, R. Delgado, M. Farah |
| journal | IEEE Journal of Biomedical and Health Informatics |
| format | latex |
| citation_style | ieee |
| paper_type | imrad |

Author names and affiliations here are `(synthetic, for demonstration)`.

## Input

None beyond the form. The skill elicits two clarifications, then scaffolds.

### Elicitation exchange

> **Skill:** IEEE JBHI uses the `IEEEtran` journal class and numbered IEEE citations. Confirm you want `IEEEtran` (yes) or a generic `article` class you convert later (no)?
>
> **User:** Yes, IEEEtran.
>
> **Skill:** Do you want a `figures/` and `tables/` folder pre-created with a placeholder architecture figure input, given this is a methods paper with a model diagram?
>
> **User:** Yes.

## Output

### Generated tree

```
manuscript/
├── main.tex                 # IEEEtran master doc with \input{} includes
├── abstract.tex
├── introduction.tex
├── methods.tex
├── results.tex
├── discussion.tex
├── conclusion.tex
├── acknowledgments.tex
├── config.yaml              # title, authors, journal, style, status
├── terminology.yaml         # consistent-term tracking
├── references/
│   └── library.bib          # empty, ready for literature-search output
├── figures/
│   └── architecture.tex     # placeholder, filled by the plotneuralnet example
└── tables/
    └── results-table.tex    # placeholder, filled by the latex-tables example
```

### `main.tex` (excerpt)

```latex
\documentclass[journal]{IEEEtran}

\usepackage{cite}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{url}

\begin{document}

\title{Self-Supervised Contrastive Pretraining for Label-Efficient\\
ECG Arrhythmia Classification}

\author{A.~Novak, R.~Delgado, and M.~Farah% <-synthetic authors
\thanks{Manuscript submitted July 12, 2026.}}

\markboth{IEEE Journal of Biomedical and Health Informatics}%
{Novak \MakeLowercase{\textit{et al.}}: Self-Supervised Contrastive Pretraining for ECG}

\maketitle

\input{abstract}
\input{introduction}
\input{methods}
\input{results}
\input{discussion}
\input{conclusion}
\input{acknowledgments}

\bibliographystyle{IEEEtran}
\bibliography{references/library}

\end{document}
```

### `config.yaml`

```yaml
title: "Self-Supervised Contrastive Pretraining for Label-Efficient ECG Arrhythmia Classification"
authors:
  - name: "A. Novak"        # synthetic, for demonstration
    affiliation: "Dept. of Biomedical Engineering, Example University"
    corresponding: true
    email: "a.novak@example.edu"
  - name: "R. Delgado"
    affiliation: "Dept. of Biomedical Engineering, Example University"
  - name: "M. Farah"
    affiliation: "Dept. of Cardiology, Example Hospital"
journal: "IEEE Journal of Biomedical and Health Informatics"
document_class: "IEEEtran"
citation_style: "ieee"
paper_type: "imrad"
status: "drafting"
created: "2026-07-12"
```

### `terminology.yaml` (seeded)

```yaml
# Preferred term -> disallowed variants, to keep usage consistent
terms:
  "self-supervised learning": ["self supervised learning", "SSL (spell out on first use)"]
  "electrocardiogram (ECG)": ["EKG", "ecg"]
  "contrastive pretraining": ["contrastive pre-training", "contrastive pre training"]
  "PTB-XL": ["PTB XL", "PTBXL"]
  "macro-AUROC": ["macro AUC", "macro-AUC"]
```

## What this demonstrates

- The scaffold matches the structure documented in CLAUDE.md (per-section `.tex` files, `config.yaml`, `terminology.yaml`, `references/library.bib`, `figures/`, `tables/`).
- Journal choice drives concrete decisions: IEEE JBHI selects the `IEEEtran` class and `IEEEtran` bibliography style, wired into `main.tex` automatically.
- `terminology.yaml` is seeded with the paper's key terms so later drafting stays internally consistent, which the post-draft integrity hook checks.
- The empty `library.bib` is the drop target for the literature-search example's included set, and the figure and table placeholders are filled by the visualization and LaTeX examples, keeping the whole example set internally consistent.
