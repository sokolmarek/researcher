---
description: Run a pre-submission compliance checklist and report pass or fail with fix instructions
---

# /researcher:submit-ready

Pre-submission compliance check.

## Inputs (gathered conversationally)
Takes no arguments. Claude reads manuscript/config.yaml for the manuscript path and the target journal.
- Target journal: only asked for if config.yaml does not declare one, since the formatting and word count checks need it.

## Behavior
Runs checklist:
1. All \cite{} keys resolve in library.bib
2. All bib entries have DOIs or URLs
3. Formatting matches target journal requirements
4. Word count within limits
5. All required sections present (including data availability, COI)
6. Figures in correct format and resolution
7. Cover letter exists
8. Response to reviewers exists (if revision)

Outputs pass/fail report with specific fix instructions for each failure.
