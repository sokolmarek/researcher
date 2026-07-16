---
name: latex-tables
description: "Typeset numbers you already have as a publication-quality LaTeX table. Triggers: create table, format table, results table, comparison table, booktabs table, turn these numbers into a table, bold the best result in each column, multicolumn table from this CSV. Supports multicolumn, significance markers, bold best results. It produces the table code from numbers you supply; finding what those numbers are in the literature is sota-finder."
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

### Word-Compatible Output (planned, not implemented)

DOCX table emission is **planned, not implemented**. The shipped generator,
`templates/word/build-docx.js`, produces a title page, numbered headings, paragraphs, and lists from
`sections/*.md`; it emits no tables. The mapping below is the specification for that work, not a
description of what runs today. Never tell a user a table was written into their DOCX.

- Generate the equivalent table structure with the `docx` library's `Table`
- Map booktabs rules to border styles (top/bottom thick, mid thin; Word has no `\toprule`)
- Preserve bold best results and alignment
- Include table caption and notes as separate paragraphs

Until that ships, deliver the LaTeX table and hand the user this mapping so they can place the table
in Word themselves. `examples/visualization-latex/latex-results-table.md` shows the expected shape of
that hand-off.

## Journal Adaptation

- Read `manuscript/config.yaml` for target journal
- Adjust table width to single-column or double-column as required
- Apply journal-specific font size (e.g., `\small`, `\footnotesize`)
- Respect maximum table count limits if specified
- Use `tabular*` or `tabularx` for full-width tables when journal requires it

## Style Presets

- Named presets (`default`, `nature`, `ieee`) are defined once in `references/figure-styles.md`. This skill does not duplicate those definitions; it reads that file for the concrete values.
- This skill consumes the preset's booktabs conventions, font size, rule weights, and caption placement, applying them to the tabular output generated here.
- Presets resolve in one precedence order, highest first: **explicit `Style:` line > trigger phrase > journal inference from `manuscript/config.yaml` > `default`**.
- Presets restyle only: they never alter data, values, or the "(synthetic, for demonstration)" labeling on placeholder data.

### `Style:` line (accepted input)

The invocation may carry an explicit `Style:` line, which outranks every other selector:

```
Turn results.csv into a results table, bold the best per column.
Style: nature
```

- `Style: nature`, `Style: ieee`: apply that preset.
- `Style: default`, or no `Style:` line at all: the no-op path, exactly the current behavior described above (zero change). An omitted `Style:` line is never an error.
- Any other value: do not guess and do not improvise a preset. Say it is not defined, list the presets that are (`default`, `nature`, `ieee`), and ask which to use.

### Trigger phrases and journal inference

- Trigger phrases that select a non-default preset when no `Style:` line is given: "nature style", "in Nature format", "for submission to <journal>", "IEEE format".
- Journal inference: with neither a `Style:` line nor a trigger phrase, check `manuscript/config.yaml` for the target journal and map it to a preset family (Nature portfolio titles map to `nature`, IEEE titles map to `ieee`, anything else falls back to `default`).
- State which preset was applied and why.

## Workflow

1. Determine table type from user request
2. Collect data (CSV, JSON, inline, or user description)
3. Confirm column headers, alignment, and grouping with user
4. Load `references/figure-styles.md` and resolve the style preset (explicit trigger phrase, or journal named/read from `manuscript/config.yaml`, or `default`); state which preset was applied and why
5. Generate LaTeX code with all required packages noted, styled per the resolved preset
6. Save to `tables/table-<name>.tex`
7. Validate compilation by running `scripts/latex-compile.py` (or `latex-compile.sh` on POSIX), which uses whichever TeX engine is installed (tectonic recommended, or latexmk/pdflatex from TeX Live, MiKTeX, or MacTeX)
8. If Word output is requested, say that DOCX table emission is planned and not implemented (see "Word-Compatible Output" above), then deliver the LaTeX table plus the `docx`-library mapping for the user to apply by hand
