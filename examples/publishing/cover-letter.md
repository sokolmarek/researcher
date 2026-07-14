# Example: Submission Cover Letter

| Field | Value |
|---|---|
| Skill | cover-letter |
| Command | n/a |
| Trigger phrase | "Write a cover letter for my JBHI submission" |
| Connectors used | none |
| Generated | 2026-07-12; compiles with any TeX engine (tectonic, TeX Live, MiKTeX, MacTeX), verified with tectonic on this date |

## Invocation

> Write a submission cover letter to IEEE JBHI for my SSL-for-ECG manuscript. Use the standard template, state the fit, and keep the results out of it since they belong in the paper.

## Input

- Target journal: IEEE Journal of Biomedical and Health Informatics (the top pick from the journal-finder example)
- Manuscript title and scope: from the manuscript-setup and drafting examples
- Template: `templates/latex/cover-letter.tex`

Author identity and affiliation are `(synthetic, for demonstration)`. The letter deliberately does not assert specific empirical results.

## Output

Compiles with any TeX engine (tectonic, TeX Live, MiKTeX, MacTeX) using the `letter` class. Verified: compiled with `tectonic cover-letter.tex` on 2026-07-12.

```latex
\documentclass[11pt,a4paper]{letter}

\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=1in]{geometry}
\usepackage{hyperref}
\hypersetup{colorlinks=true, urlcolor=blue}

\signature{
    A. Novak\\
    \small Dept. of Biomedical Engineering, Example University\\
    \small Example City, Country\\
    \small \href{mailto:a.novak@example.edu}{a.novak@example.edu}
}

\address{
    A. Novak\\
    Dept. of Biomedical Engineering\\
    Example University\\
    Example City, Country
}

\date{\today}

\begin{document}

\begin{letter}{
    The Editor-in-Chief\\
    IEEE Journal of Biomedical and Health Informatics\\
}

\opening{Dear Editor,}

We are pleased to submit our manuscript entitled ``Self-Supervised Contrastive
Pretraining for Label-Efficient ECG Arrhythmia Classification'' for
consideration for publication in \textit{IEEE Journal of Biomedical and Health
Informatics}.

Diagnostic annotation of the electrocardiogram is expensive and rare conditions
are underrepresented, which limits supervised deep learning for ECG analysis. In
this work we pretrain an ECG encoder on unlabeled 12-lead recordings using a
contrastive objective with physiologically grounded augmentations, then
fine-tune on the public PTB-XL benchmark under its standardized evaluation
protocol. We report a controlled label-efficiency study isolating the
contribution of pretraining from the evaluation protocol, and an ablation of
augmentation families. (Specific results are reported in the manuscript.)

We believe this manuscript is well suited for \textit{IEEE Journal of Biomedical
and Health Informatics} because the journal defined the PTB-XL benchmarking
protocol against which our method is measured, and its readership works directly
on machine learning for physiological signals. Our emphasis on reproducible,
protocol-matched evaluation speaks to that audience.

This manuscript has not been published elsewhere and is not under consideration
by any other journal. All authors have read and approved the final manuscript,
and we declare no conflicts of interest. All code and the derived data splits
supporting this study will be made available in a public repository upon
acceptance; PTB-XL is publicly available from its original providers.

\closing{Sincerely,}

\end{letter}
\end{document}
```

## What this demonstrates

- The letter follows `templates/latex/cover-letter.tex`: submission statement, contribution summary, journal-fit paragraph, originality and exclusivity, conflict-of-interest, and data-availability, all in the `letter` class.
- The fit paragraph gives a concrete, verifiable reason (JBHI defined the PTB-XL benchmark the paper uses) rather than flattery.
- It deliberately withholds specific numeric results, keeping unproven synthetic figures out of the letter, and marks the authorship as synthetic.
- Facts (title, journal, method, data availability) are consistent with the manuscript-setup, drafting, and journal-finder examples, and the file compiles with any TeX engine (tectonic, TeX Live, MiKTeX, MacTeX); verified with tectonic.
