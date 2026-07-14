---
name: latex-tables
description: "Create publication-quality LaTeX tables. Triggers: create table, format table, results table, comparison table, booktabs table. Supports multicolumn, significance markers, bold best results."
---

# LaTeX Tables

Create publication-quality tables using `booktabs` conventions for academic manuscripts.

## Table Style Rules

- **No vertical rules.** Use `\toprule`, `\midrule`, `\bottomrule` from `booktabs` only.
- **Proper spacing.** Use `\addlinespace` for logical row grouping, never `\\[6pt]` hacks.
- **Left-align text columns, right-align numeric columns.** Use `S` columns from `siunitx` for decimal alignment.
- **Minimal ink.** Remove all unnecessary lines and borders.

## Supported Table Types

### Results Table
- Rows = methods/models, columns = metrics
- Bold the best result per column (`\textbf{}`)
- Statistical significance markers: `*` (p<0.05), `**` (p<0.01), `***` (p<0.001)
- Add table footnote explaining marker meaning via `\tnote{}`

### Comparison Table
- Side-by-side feature or property comparison
- Checkmarks (`\checkmark`) and dashes (`---`) for binary features
- Grouped column headers via `\multicolumn{}`

### Summary Statistics Table
- Descriptive stats: mean, SD, median, range, N
- Use `siunitx` `S` column type for aligned decimals
- Horizontal grouping with `\cmidrule{}`

### Multi-Page Table
- Uses `longtable` package for tables exceeding one page
- Repeated header row on each page with `\endhead`
- Continued footer with `\endfoot`

### Landscape Table
- Uses `sidewaystable` from `rotating` package for wide tables
- Automatically rotates 90 degrees on the page

## Multi-Column and Multi-Row Support

- `\multicolumn{n}{alignment}{content}` for spanning columns
- `\multirow{n}{width}{content}` for spanning rows (requires `multirow` package)
- Combine with `\cmidrule{start-end}` for partial horizontal rules under grouped headers

## Data Ingestion

### From CSV
1. User provides path to `.csv` file
2. Parse headers and rows automatically
3. Detect numeric vs text columns for alignment
4. Apply booktabs formatting
5. Place output in `tables/` directory

### From JSON
1. Accept array-of-objects JSON format
2. Keys become column headers
3. Values populate rows
4. Same auto-detection and formatting as CSV

### From Inline Data
1. User describes data in natural language or pastes raw text
2. Parse into structured rows/columns
3. Confirm structure with user before generating LaTeX

## Required LaTeX Packages

```latex
\usepackage{booktabs}       % Professional table rules
\usepackage{multirow}       % Row spanning
\usepackage{siunitx}        % Decimal-aligned columns
\usepackage{rotating}       % sidewaystable
\usepackage{longtable}      % Multi-page tables
\usepackage{threeparttable} % Table notes and footnotes
```

## Output Format

### LaTeX Output
```latex
\begin{table}[htbp]
  \centering
  \caption{Comparison of model performance on benchmark dataset.}
  \label{tab:results}
  \begin{threeparttable}
    \begin{tabular}{l S[table-format=2.1] S[table-format=2.1] S[table-format=1.3]}
      \toprule
      {Method} & {Accuracy (\%)} & {F1 (\%)} & {p-value} \\
      \midrule
      Baseline   & 78.3 & 75.1 & 0.042\tnote{*} \\
      Our Method & \textbf{85.7} & \textbf{83.2} & {---} \\
      \bottomrule
    \end{tabular}
    \begin{tablenotes}
      \item[*] p < 0.05 compared to Our Method.
    \end{tablenotes}
  \end{threeparttable}
\end{table}
```

### Word-Compatible Output
- Generate equivalent table structure for `docx-js`
- Map booktabs rules to border styles (top/bottom thick, mid thin)
- Preserve bold best results and alignment
- Include table caption and notes as separate paragraphs

## Journal Adaptation

- Read `manuscript/config.yaml` for target journal
- Adjust table width to single-column or double-column as required
- Apply journal-specific font size (e.g., `\small`, `\footnotesize`)
- Respect maximum table count limits if specified
- Use `tabular*` or `tabularx` for full-width tables when journal requires it

## Style Presets

- Named presets (`default`, `nature`, `ieee`) are defined once in `references/figure-styles.md`. This skill does not duplicate those definitions; it reads that file for the concrete values.
- This skill consumes the preset's booktabs conventions, font size, rule weights, and caption placement, applying them to the tabular output generated here.
- Trigger phrases that select a non-default preset: "nature style", "in Nature format", "for submission to <journal>", "IEEE format".
- Journal inference: if the user names a journal instead of a preset, check `manuscript/config.yaml` for the target journal and map it to a preset family (Nature portfolio titles map to `nature`, IEEE titles map to `ieee`, anything else falls back to `default`).
- No style mentioned means the `default` preset, which is exactly the current behavior described above (zero change).
- Presets restyle only: they never alter data, values, or the "(synthetic, for demonstration)" labeling on placeholder data.

## Workflow

1. Determine table type from user request
2. Collect data (CSV, JSON, inline, or user description)
3. Confirm column headers, alignment, and grouping with user
4. Load `references/figure-styles.md` and resolve the style preset (explicit trigger phrase, or journal named/read from `manuscript/config.yaml`, or `default`); state which preset was applied and why
5. Generate LaTeX code with all required packages noted, styled per the resolved preset
6. Save to `tables/table-<name>.tex`
7. Validate compilation via tectonic
8. If Word output requested, generate docx-js equivalent
