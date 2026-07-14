# Post-Draft Integrity Report

Prints a short consistency report after Claude writes or edits a `.tex` file. It is informational
only and never blocks: the script always exits 0.

| Property | Value |
|---|---|
| Trigger | PostToolUse on `Write\|Edit` (registered in `hooks/hooks.json`); the script exits silently unless the edited file ends in `.tex` |
| Script | `scripts/draft-integrity-hook.py` (stdlib-only, Windows-safe) |
| Exit codes | always 0; internal errors are printed and swallowed |
| Disable | remove the PostToolUse entry from `hooks/hooks.json` |

## What it checks

1. Locates the manuscript root by walking up from the edited file to the nearest directory containing
   `main.tex` or `config.yaml` (falls back to the file's own directory).
2. Scans every `.tex` file under that root (comments stripped) and every `.bib` file.
3. Reports:
   - citation keys used vs. dangling (`\cite` family with no matching `.bib` entry),
   - cross-references vs. dangling (`\ref`, `\eqref`, `\autoref`, `\cref`, `\pageref` with no matching `\label`),
   - labels defined but never referenced (informational).

## What it does not do

It does not resolve DOIs, detect hallucinated references, or score the draft. Those checks live in
`scripts/bib-validator.py` (CrossRef resolution, retraction flags) and the citation-management skill.
Claim-level faithfulness checking is planned work (see the fact-checking and citation-context skills).
