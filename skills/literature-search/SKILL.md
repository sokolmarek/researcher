---
name: literature-search
description: "Search academic literature across multiple databases. Triggers when user says: 'search literature', 'find papers', 'literature review', 'what does research say about', 'find related work', 'search PubMed', 'search arXiv', 'find citations', 'related papers', 'prior work on'. Searches PubMed, Semantic Scholar, arXiv, Scite, Google Scholar, and CrossRef. Use this skill whenever the user needs to find, discover, or explore academic papers on any topic."
---

# Literature Search

Multi-source academic literature search with deduplication and ranking.

## CRITICAL INTEGRITY RULE
**NEVER fabricate or hallucinate citations.** Every result must come from an actual search query to a real source. If a search returns no results, say so. Do not invent papers, authors, DOIs, or abstracts under any circumstances.

## Workflow

1. **Parse research question** → extract key concepts, synonyms, MeSH terms
2. **Construct queries** → adapt syntax per source (Boolean for PubMed, keywords for Semantic Scholar)
3. **Dispatch searches** to available sources (in priority order):
   - **Scite (PRIMARY when MCP connected)** — smart citation context, citation tallies, full-text snippets
   - PubMed (via NCBI E-utilities) — biomedical focus
   - Semantic Scholar (via S2 API) — broad CS/science coverage, citation graphs
   - arXiv (via API) — preprints, CS/physics/math
   - Google Scholar (via web search) — broadest coverage
   - CrossRef (via API) — DOI resolution, metadata
4. **Deduplicate** results by DOI, then by title similarity (>0.9 Jaccard)
5. **Rank** by: relevance to query > recency > citation count
6. **Present** results in structured format

## Result Format

For each paper found:
```
[1] Title of the Paper
    Authors: First A., Second B., Third C.
    Year: 2024 | Journal: Nature Machine Intelligence
    Citations: 142 | DOI: 10.1234/example
    Abstract: First 2-3 sentences of abstract...
    Source: Semantic Scholar
    Scite Tallies: 89 supporting | 12 contrasting | 41 mentioning  (when Scite available)
    [Add to bibliography]
```

## Search Modes

### Standard Search
Default mode. Searches all available sources, returns top 10-20 results.

### Systematic Review (PRISMA)
Triggered by: "systematic review", "PRISMA", "comprehensive search"
- Documents search strategy (databases, queries, date ranges)
- Tracks: identified → screened → eligible → included
- Generates PRISMA flow diagram data
- Exports search log for reproducibility

### Citation Chasing
Triggered by: "papers that cite this", "references of this paper"
- Forward citation search (who cites this paper)
- Backward reference search (what does this paper cite)
- Uses Semantic Scholar citation graph

## Connector Usage

Check which connectors are available before searching. Use all available ones. If a connector is unavailable, skip it and note which sources were not searched.

### PubMed API
```
Base URL: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
esearch.fcgi?db=pubmed&term={query}&retmax=20&sort=relevance
efetch.fcgi?db=pubmed&id={pmid_list}&rettype=xml
```

### Semantic Scholar API
```
Base URL: https://api.semanticscholar.org/graph/v1/
paper/search?query={query}&limit=20&fields=title,authors,year,abstract,citationCount,externalIds
```

### arXiv API
```
Base URL: http://export.arxiv.org/api/
query?search_query=all:{query}&max_results=20&sortBy=relevance
```

### CrossRef API
```
Base URL: https://api.crossref.org/works
?query={query}&rows=20&sort=relevance
```

## Deep Scite Integration

> **When the Scite MCP server is connected, this skill gains citation context superpowers.**

When the Scite MCP connector is available, it becomes the PRIMARY search source (not just supplementary). The following enhanced capabilities activate:

### Scite as Primary Search
- Dispatch search queries to Scite FIRST, before other sources
- Use Scite results as the baseline result set; supplement with other sources for coverage
- Scite results carry richer metadata and are preferred when deduplicating

### Citation Tallies
For every paper found (from any source), retrieve Scite citation tallies when available:
- **Supporting citations**: how many papers cite this work in a supporting context
- **Contrasting citations**: how many papers cite this work to disagree or present conflicting findings
- **Mentioning citations**: neutral mentions without supporting or contrasting stance
- Use tallies as an additional ranking signal: papers with high supporting counts and low contrasting counts rank higher for established findings; papers with high contrasting counts are flagged as controversial

### Smart Citation Context
For each result, retrieve Scite smart citation snippets showing HOW the paper is being cited by others:
- Display 2-3 representative citation statements (actual sentences from citing papers)
- Label each statement as supporting, contrasting, or mentioning
- This gives the user immediate insight into a paper's reception and standing in the field

### Citation Landscape Analysis
Triggered by: "citation landscape", "citation network", "how is this paper cited", "map citations"

For a given paper or topic, map the citation network:
1. Start from a seed paper (by DOI or title) or a topic query
2. Retrieve all citing papers via Scite with their citation contexts
3. Classify relationships: which papers support each other vs contradict
4. Identify citation clusters: groups of papers that mutually support the same thesis
5. Identify controversies: pairs or groups of papers that contradict each other
6. Output a structured map:
   - Core papers (most cited within the network)
   - Supporting chains (A supports B, B supports C)
   - Contradiction pairs (A contradicts B)
   - Isolated papers (cited but not well-connected)
7. Suggest which "side" of a controversy has stronger citation support

This analysis helps authors position their work accurately within the existing discourse and avoid misrepresenting the state of consensus.

## Auto-Add to Bibliography

When user selects papers, generate BibTeX entries and append to `manuscript/references/library.bib`. Validate each entry has:
- Unique citation key (format: `authorYear` or `authorYearKeyword`)
- DOI (if available)
- Complete metadata (title, author, year, journal/booktitle)

## References

For advanced search strategies, read `references/search-strategies.md`.
