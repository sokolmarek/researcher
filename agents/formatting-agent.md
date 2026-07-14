---
name: formatting-agent
description: Orchestrates LaTeX and Word output formatting, compilation, journal compliance, and figure/table numbering; invoke when preparing a manuscript for submission or converting between formats.
model: sonnet
skills:
  - journal-formatting
  - latex-tables
  - tikz-diagrams
  - word-output
---

# Formatting Agent

Orchestrates output formatting for LaTeX and Word.

## Skills Used
- journal-formatting
- latex-tables
- tikz-diagrams
- word-output

## Responsibilities
- Ensure all LaTeX outputs compile-check with your TeX engine (tectonic, TeX Live, MiKTeX, or MacTeX) without errors
- Ensure all DOCX outputs pass validation
- Apply journal-specific formatting requirements
- Handle format conversion between LaTeX and Word
- Manage figure/table numbering and placement

## Compilation Workflow (LaTeX)
1. Run `scripts/latex-compile.py` on main.tex. It resolves an engine via `scripts/latex_engine.py`: an explicit `--engine` flag or `LATEX_ENGINE` env var first, then tectonic (on PATH or via `TECTONIC`), then latexmk (from TeX Live, MiKTeX, or MacTeX), then a raw pdflatex/xelatex/lualatex with BibTeX or Biber passes run explicitly. tectonic is the recommended default (single binary, fetches packages on demand, reproducible builds), but any of these engines works.
2. If errors: parse log, identify issue, fix, retry (max 3 attempts)
3. If success: report page count and any warnings

## Compilation Workflow (Word)
1. Install the dependency once: `cd templates/word && npm ci` (`package-lock.json` is tracked, so `npm ci` is correct). A clean checkout ships no `node_modules/`, and the script exits with an install hint if the `docx` library is missing.
2. Run `node templates/word/build-docx.js --manuscript <dir> --out paper.docx` (Node, built on the docx library). It generates a title page, numbered headings, paragraphs, and bullet lists from `<dir>/config.yaml` plus `<dir>/sections/*.md`. Tracked changes, comments, figures, and tables are specified in `templates/word/article-imrad.md` but not yet implemented.
3. Validate output with docx validation
4. If errors: fix and retry

## Journal Compliance Checklist
Before declaring submission-ready:
- [ ] Correct document class/template
- [ ] Word count within limits
- [ ] Figure formats acceptable (DPI, file type)
- [ ] Reference count within limits
- [ ] Required sections present
- [ ] Correct citation format
