# Common Academic Table Patterns

Loaded by latex-tables skill. Reusable patterns for publication-quality tables.

## Pattern 1: Results Comparison Table

```latex
\begin{table}[htbp]
\centering
\caption{Comparison of methods on benchmark dataset.}
\label{tab:results}
\begin{tabular}{@{}lccc@{}}
\toprule
Method & Accuracy (\%) & F1 Score & Params (M) \\
\midrule
Baseline A        & 85.2          & 0.841    & 12.3 \\
Baseline B        & 87.1          & 0.862    & 24.7 \\
Ours              & \textbf{91.3} & \textbf{0.908} & 15.1 \\
\bottomrule
\end{tabular}
\end{table}
```

## Pattern 2: Statistical Significance

```latex
% Significance markers in table note
\begin{tabular}{@{}lcc@{}}
\toprule
Method & Dataset A & Dataset B \\
\midrule
Ours   & 92.1$^{***}$ & 88.5$^{**}$ \\
Prior  & 89.3         & 86.2 \\
\bottomrule
\end{tabular}
\begin{tablenotes}\small
\item $^{*}$: $p < 0.05$; $^{**}$: $p < 0.01$; $^{***}$: $p < 0.001$
\end{tablenotes}
```

## Pattern 3: Multi-Column Header

```latex
\begin{tabular}{@{}l*{2}{cc}@{}}
\toprule
& \multicolumn{2}{c}{Dataset A} & \multicolumn{2}{c}{Dataset B} \\
\cmidrule(lr){2-3} \cmidrule(lr){4-5}
Method & Prec. & Recall & Prec. & Recall \\
\midrule
Method 1 & 0.91 & 0.88 & 0.87 & 0.85 \\
Method 2 & 0.93 & 0.90 & 0.89 & 0.87 \\
\bottomrule
\end{tabular}
```

## Pattern 4: Multi-Row Groups

```latex
\begin{tabular}{@{}llcc@{}}
\toprule
Category & Method & Metric 1 & Metric 2 \\
\midrule
\multirow{2}{*}{Traditional} & SVM   & 78.2 & 0.76 \\
                              & RF    & 80.1 & 0.79 \\
\midrule
\multirow{2}{*}{Deep Learning} & CNN  & 88.5 & 0.87 \\
                                & LSTM & 87.3 & 0.86 \\
\bottomrule
\end{tabular}
```

## Pattern 5: Ablation Study

```latex
\begin{table}[htbp]
\centering
\caption{Ablation study. Checkmarks indicate included components.}
\label{tab:ablation}
\begin{tabular}{@{}ccc|c@{}}
\toprule
Component A & Component B & Component C & Accuracy (\%) \\
\midrule
            &             &             & 82.1 \\
\checkmark  &             &             & 84.5 \\
\checkmark  & \checkmark  &             & 87.2 \\
\checkmark  & \checkmark  & \checkmark  & \textbf{91.3} \\
\bottomrule
\end{tabular}
\end{table}
```

## Pattern 6: Dataset Statistics

```latex
\begin{tabular}{@{}lrrr@{}}
\toprule
Split & Samples & Avg. Length & Classes \\
\midrule
Train      & 50{,}000  & 128.3 & 10 \\
Validation & 10{,}000  & 127.8 & 10 \\
Test       & 10{,}000  & 129.1 & 10 \\
\midrule
Total      & 70{,}000  & 128.4 & 10 \\
\bottomrule
\end{tabular}
```

## Pattern 7: Landscape Wide Table

```latex
\usepackage{rotating}  % or \usepackage{pdflscape}

\begin{sidewaystable}
\centering
\caption{Comprehensive comparison across all benchmarks.}
\label{tab:full_comparison}
\begin{tabular}{@{}l*{8}{c}@{}}
\toprule
% ... wide table content ...
\bottomrule
\end{tabular}
\end{sidewaystable}
```

## Pattern 8: Longtable (multi-page)

```latex
\usepackage{longtable}

\begin{longtable}{@{}lcp{6cm}@{}}
\caption{Survey of related work.} \label{tab:survey} \\
\toprule
Reference & Year & Key Contribution \\
\midrule
\endfirsthead
\multicolumn{3}{c}{Table~\ref{tab:survey} continued} \\
\toprule
Reference & Year & Key Contribution \\
\midrule
\endhead
\midrule
\multicolumn{3}{r}{Continued on next page} \\
\endfoot
\bottomrule
\endlastfoot
% rows...
\end{longtable}
```

## Formatting Rules

- Always use `booktabs` (`\toprule`, `\midrule`, `\bottomrule`) — never `\hline`
- No vertical rules (`|`) — use column spacing instead
- Use `@{}` to remove outer padding in column specs
- Right-align numbers, left-align text
- Use `\cmidrule(lr)` for partial horizontal rules under multi-column headers
- Bold the best result in each column with `\textbf{}`
- Use `{,}` for thousands separator in numbers (e.g., `50{,}000`)
- Place captions above tables (unlike figures, which have captions below)
