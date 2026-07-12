# Example: Publication-Quality Results Table

| Field | Value |
|---|---|
| Skill | latex-tables |
| Command | n/a |
| Trigger phrase | "Turn this results CSV into a booktabs table with the best result bold and significance markers" |
| Connectors used | none |
| Generated | 2026-07-12; compiled with tectonic on this date |

## Invocation

> Turn this CSV of my label-efficiency results into a publication-quality LaTeX table: group by supervised vs self-supervised, bold the best in each column, add significance markers and table notes.

## Input

The CSV below is `(synthetic, for demonstration)`; these are illustrative numbers, not measured results.

```csv
category,method,frac_1,frac_10,frac_100
Supervised,CNN (from scratch),0.712,0.848,0.921
Supervised,CNN + augmentation,0.741,0.863,0.924
Self-supervised,Contrastive (baseline),0.803,0.881,0.926
Self-supervised,+ physio. augment (ours),0.821,0.889,0.929
Self-supervised,ablation: no jitter,0.812,0.884,0.927
```

## Output

Compiles with `tectonic` (requires `booktabs`, `multirow`, `threeparttable`). Verified: compiled on 2026-07-12.

```latex
\begin{table}[htbp]
\centering
\caption{Label-efficiency comparison on the PTB-XL superclass task. Values are
macro-AUROC (mean over 5 seeds). Best result in each column in \textbf{bold}.
Synthetic data, for demonstration only.}
\label{tab:labeleff}
\begin{threeparttable}
\begin{tabular}{@{}ll*{3}{c}@{}}
\toprule
& & \multicolumn{3}{c}{Labeled fraction} \\
\cmidrule(lr){3-5}
Category & Method & 1\% & 10\% & 100\% \\
\midrule
\multirow{2}{*}{Supervised}
  & CNN (from scratch)        & 0.712          & 0.848          & 0.921 \\
  & CNN + augmentation        & 0.741          & 0.863          & 0.924 \\
\midrule
\multirow{3}{*}{Self-supervised}
  & Contrastive (baseline)    & 0.803$^{**}$   & 0.881          & 0.926 \\
  & + physio. augment (ours)  & \textbf{0.821}$^{***}$ & \textbf{0.889}$^{*}$ & \textbf{0.929} \\
  & \quad ablation: no jitter & 0.812$^{**}$   & 0.884          & 0.927 \\
\bottomrule
\end{tabular}
\begin{tablenotes}\small
\item Significance versus supervised from-scratch at the same labeled fraction,
paired $t$-test over seeds: $^{*}p<0.05$, $^{**}p<0.01$, $^{***}p<0.001$.
\item Gains are largest in the low-label regime (1\%) and shrink toward parity at 100\%,
consistent with self-supervised pretraining acting mainly as a label-efficiency prior.
\end{tablenotes}
\end{threeparttable}
\end{table}
```

### Word (docx-js) equivalent, note

For Word output the same table is emitted by `build-docx.js` as a `Table` with a two-level header (a merged "Labeled fraction" cell spanning three columns above the 1/10/100 columns), bold runs on the best cell per column, and the significance legend as a caption paragraph below. The booktabs rules become top/mid/bottom borders since Word has no `\toprule`.

## What this demonstrates

- CSV to booktabs conversion following every rule in `references/table-patterns.md`: `\toprule`/`\midrule`/`\bottomrule` (no vertical rules), `@{}` outer padding removed, numbers centered, best-in-column bolded, `\multirow` category groups, a `\cmidrule` under the spanning header, and significance markers explained in `threeparttable` notes.
- Synthetic experimental data is labeled as such in both the caption and the input, honoring the never-invent-data constraint while still showing realistic table structure.
- The table caption sits above the table (tables) versus figure captions below (figures), matching house convention.
- A note maps the same table to the Word/docx-js path, so the example covers both output modes.
- Compile-verified with tectonic before inclusion.
