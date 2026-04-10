# Post-Draft Integrity Check Hook

## Trigger
After any section drafting operation completes.

## Actions
1. Scan drafted text for factual claims without citations
2. Check all \cite{key} references resolve in library.bib
3. Validate \ref{label} has matching \label{label} somewhere in manuscript
4. Check for potential hallucinated references (DOI doesn't resolve)
5. Report integrity score (0-100) based on:
   - Claims with citations / total claims
   - Valid references / total references
   - Valid cross-refs / total cross-refs
