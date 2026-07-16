---
name: journal-finder
description: "Recommend which journal to submit a finished manuscript to, weighing topic fit, scope, impact factor, APC, and review turnaround. Triggers: find journal, recommend journal, where to publish, where should I submit this paper, which journal, journal suggestion, best journal for, submit where, target journal, journal match, journal impact factor, fast review turnaround. Chooses the venue only: typesetting the paper into a publisher house style is journal-formatting, and conference or workshop venues are conference-finder."
---

# Journal Finder

Journal recommendation engine that analyzes paper content and returns a ranked list of best-fit journals with detailed metadata and reasoning.

## CRITICAL INTEGRITY RULE
**NEVER fabricate journal metrics.** Impact factors, quartile rankings, acceptance rates, and APCs must come from verifiable sources (SCImago, Clarivate, journal websites). If a metric is unavailable, state "not available" rather than guessing.

## Workflow

1. **Analyze paper profile**: read title, abstract, keywords from `manuscript/config.yaml` or user input
2. **Extract dimensions**: determine field, subfield, methodology type, scope (theoretical/empirical/applied), interdisciplinarity level
3. **Query journal sources**: search across available connectors and databases:
   - `references/journal-database.md`: local curated journal list
   - SCImago Journal Rank (via web search): quartile rankings, SJR scores
   - Clarivate / Journal Citation Reports (via web search): impact factors
   - DOAJ (via API or web search): open access journal directory
   - Scite (if MCP connector available): journal-level citation context
   - CrossRef (via API): journal metadata, ISSN resolution
4. **Apply user filters**: respect constraints on quartile, OA status, indexing, IF threshold, APC budget
5. **Score and rank**: weight scope match highest, then prestige, then practical factors
6. **Present recommendations** with reasoning for each

## Input Modes

### From Manuscript
When a `manuscript/` folder exists, automatically read `config.yaml`, `abstract.tex`, and keywords to build the paper profile.

### From Description
User provides a text description of the paper topic, and optionally:
- Target field or discipline
- Preferred open access status
- Budget constraints for APCs
- Minimum impact factor or quartile
- Required indexing databases

### From Bibliography
Analyze the journals already cited in `library.bib` to identify the community the paper belongs to and recommend journals that publish similar work.

## Recommendation Format

Return 5-10 journals, ranked by overall fit:

```
[1] Journal of Machine Learning Research (JMLR)
    Publisher:      MIT Press
    Impact Factor:  6.8 (2025) | CiteScore: 12.4
    Quartile:       Q1 (Computer Science, AI)
    Indexing:       Scopus, Web of Science, DBLP
    Open Access:    Yes (Gold OA, no APC)
    APC:            None
    Acceptance Rate: ~25%
    Avg Review Time: 3-6 months
    Scope Match:    HIGH: publishes theoretical and empirical ML work;
                    strong fit for papers on novel learning algorithms
                    with convergence analysis.
    Notes:          Requires reproducible experiments with public code.
```

## Scoring Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Scope match | 35% | How well the paper topic fits the journal's aims and scope |
| Prestige / IF | 20% | Impact factor, CiteScore, community reputation |
| Quartile rank | 15% | SCImago quartile (Q1 > Q2 > Q3 > Q4) |
| Indexing coverage | 10% | Scopus, Web of Science, PubMed, DOAJ |
| Practical factors | 10% | Review timeline, acceptance rate, submission complexity |
| OA / APC alignment | 10% | Match with user's open access and budget preferences |

## User Filters

Support these filter parameters, applied as hard constraints before ranking:

- `--quartile Q1` or `--quartile Q1,Q2`: restrict to specific quartiles
- `--oa-only`: only open access journals
- `--indexed-in scopus,wos`: require specific indexing
- `--if-min 3.0`: minimum impact factor threshold
- `--apc-max 2000`: maximum APC in USD
- `--field "computer science"`: override auto-detected field
- `--exclude predatory`: cross-check against Beall's list and known predatory indicators

## Predatory Journal Detection

For every recommended journal, run predatory indicators check:
- Listed on known predatory journal databases
- Suspiciously fast peer review claims (<2 weeks)
- No real editorial board or board members unaware of their listing
- Aggressive email solicitation patterns
- Missing or fake ISSN
- No indexing in reputable databases

Flag any journal with predatory indicators and exclude from default results.

## Comparison Mode

When the user is choosing between specific journals, provide a side-by-side comparison table:

```
| Criterion        | Journal A     | Journal B     | Journal C     |
|------------------|---------------|---------------|---------------|
| Impact Factor    | 4.2           | 6.8           | 3.1           |
| Quartile         | Q1            | Q1            | Q2            |
| Open Access      | Hybrid        | Gold OA       | Subscription  |
| APC              | $3,450        | $0            | N/A           |
| Review Time      | 2-4 months    | 3-6 months    | 1-3 months    |
| Acceptance Rate  | ~30%          | ~25%          | ~45%          |
| Scope Fit        | HIGH          | HIGH          | MEDIUM        |
```

## Integration with Other Skills

- **journal-formatting**: once a journal is selected, hand off to apply its formatting requirements
- **cover-letter**: uses journal metadata to tailor the cover letter
- **literature-search**: journals publishing the most cited related work score higher
- **citation-management**: analyzes `library.bib` to identify the author's publication community

## References

Cross-reference `references/journal-database.md` for curated journal metadata. Use web search to supplement with current impact factors and submission guidelines.
