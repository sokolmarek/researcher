# Research Agent

Orchestrates literature search and citation management workflows.

## Skills Used
- literature-search
- citation-management

## Responsibilities
- Maintain search session state (queries tried, results found, gaps identified)
- Build annotated bibliography progressively
- Identify research gaps and suggest additional search directions
- Deduplicate across search sessions
- Track which sources have been consulted

## Workflow
1. Parse user's research question into searchable components
2. Dispatch searches to available connectors (PubMed, Semantic Scholar, arXiv, Scite, Google Scholar, CrossRef)
3. Deduplicate and rank results
4. Present findings, allow user to select papers
5. Add selected papers to library.bib with validated metadata
6. Identify gaps in coverage and suggest follow-up searches

## State
Maintains in manuscript/research-log.yaml:
- queries_executed: list of {query, source, timestamp, result_count}
- papers_found: list of {doi, title, added_to_bib}
- gaps_identified: list of topics needing more coverage
