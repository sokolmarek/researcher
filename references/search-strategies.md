# Literature Search Strategies

Loaded by literature-search skill. Best practices for academic literature discovery.

## Query Construction

### From Research Question to Search Terms

1. **Identify key concepts**: break the question into 2-4 core concepts
2. **Find synonyms and variants** for each concept (e.g., "machine learning" → "deep learning", "neural network", "artificial intelligence")
3. **Add MeSH terms** (PubMed) or domain-specific keywords
4. **Combine with Boolean operators:**
   - AND: narrows results (all terms must appear)
   - OR: broadens results (any synonym matches)
   - NOT: excludes irrelevant topics

### Example

Research question: "How does federated learning improve privacy in medical imaging?"

```
("federated learning" OR "distributed learning" OR "collaborative learning")
AND
("medical imaging" OR "radiology" OR "pathology" OR "clinical imaging")
AND
("privacy" OR "differential privacy" OR "data protection" OR "HIPAA")
```

## Search Strategy by Database

### PubMed
- Use MeSH terms for precision: `"Machine Learning"[MeSH]`
- Filter by publication type: `AND (Review[pt] OR Systematic Review[pt])`
- Date range: `AND ("2020"[Date - Publication] : "2024"[Date - Publication])`
- Free full text: `AND free full text[Filter]`

### Semantic Scholar
- Keyword-based, no Boolean support in basic search
- Use `fields` parameter to get citation counts for ranking
- Use citation graph for forward/backward chasing
- `fieldsOfStudy` filter for domain scoping

### arXiv
- Search by category: `cat:cs.LG AND all:"federated learning"`
- Sort by `submittedDate` for latest preprints
- Combine with `abs:` for abstract-only search

### Google Scholar (via web search)
- Phrase search: `"exact phrase"`
- Site restriction: `site:arxiv.org`
- Author search: `author:"Smith"`
- Date range: use custom range in Google Scholar settings

### CrossRef
- Best for DOI resolution and metadata validation
- Use for verifying reference accuracy
- `filter=from-pub-date:2020` for date filtering

## Search Modes

### Scoping Search
- Goal: understand the landscape, identify key papers and gaps
- Approach: broad queries across multiple databases, skim titles and abstracts
- Output: 50-100 papers, categorized by theme

### Targeted Search
- Goal: find specific evidence for a claim or method
- Approach: narrow queries with precise terms, read abstracts carefully
- Output: 5-20 highly relevant papers

### Systematic Search (PRISMA)
- Goal: comprehensive, reproducible coverage of a topic
- Steps:
  1. Define inclusion/exclusion criteria before searching
  2. Document every query, database, and date
  3. Track: identified → duplicates removed → screened → eligible → included
  4. Generate PRISMA flow diagram
  5. Export search log

### Citation Chasing
- **Forward:** find papers that cite a known key paper (Semantic Scholar, Google Scholar)
- **Backward:** check reference lists of key papers for missed works
- **Snowball:** repeat forward/backward from newly discovered papers

## Deduplication

1. Match by DOI (exact)
2. Match by title similarity (Jaccard > 0.9 on lowercased word sets)
3. Match by author + year + first significant title word
4. Keep the version with most metadata (DOI > PMID > arXiv ID)

## Ranking Heuristics

| Signal | Weight | Notes |
|--------|--------|-------|
| Query term match in title | High | Direct relevance indicator |
| Recency (within 5 years) | Medium | Prioritize recent work |
| Citation count | Medium | Weighted by field norms |
| Journal impact | Low | Supplementary signal |
| Full text available | Low | Accessibility bonus |

## Common Pitfalls

- **Too broad:** Returns thousands of irrelevant papers. Fix: add more AND terms or use phrase search.
- **Too narrow:** Returns 0-5 papers. Fix: use OR with synonyms, broaden date range, check spelling.
- **Database bias:** PubMed favors biomedical; arXiv favors CS/physics. Always search multiple sources.
- **Publication bias:** Published papers skew positive. Check preprint servers for negative results.
- **Recency bias:** Don't ignore foundational papers. Check seminal works via backward citation chasing.
- **Language bias:** English-language databases miss non-English research. Note this limitation.
