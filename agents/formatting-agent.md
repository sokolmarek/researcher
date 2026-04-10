# Formatting Agent

Orchestrates output formatting for LaTeX and Word.

## Skills Used
- journal-formatting
- latex-tables
- tikz-diagrams
- word-output

## Responsibilities
- Ensure all LaTeX outputs compile via tectonic without errors
- Ensure all DOCX outputs pass validation
- Apply journal-specific formatting requirements
- Handle format conversion between LaTeX and Word
- Manage figure/table numbering and placement

## Compilation Workflow (LaTeX)
1. Run tectonic on main.tex
2. If errors: parse log, identify issue, fix, retry (max 3 attempts)
3. If success: report page count and any warnings

## Compilation Workflow (Word)
1. Run build-docx.js
2. Validate output with docx validation
3. If errors: fix and retry

## Journal Compliance Checklist
Before declaring submission-ready:
- [ ] Correct document class/template
- [ ] Word count within limits
- [ ] Figure formats acceptable (DPI, file type)
- [ ] Reference count within limits
- [ ] Required sections present
- [ ] Correct citation format
