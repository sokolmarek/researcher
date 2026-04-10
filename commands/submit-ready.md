# /submit-ready

Pre-submission compliance check.

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
