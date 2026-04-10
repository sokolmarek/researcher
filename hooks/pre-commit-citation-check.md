# Pre-Commit Citation Check Hook

## Trigger
Before any git commit that includes files in the  directory.

## Actions
1. Scan all .tex files for \cite{key} references
2. Cross-check every key against manuscript/references/library.bib
3. Flag:
   - CRITICAL: \cite{key} where key does not exist in .bib → block commit
   - WARNING: .bib entries not cited in any .tex file
   - WARNING: .bib entries without DOI or URL
4. Report results; block on CRITICAL, warn on WARNING
