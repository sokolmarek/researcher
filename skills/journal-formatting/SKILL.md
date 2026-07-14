---
name: journal-formatting
description: "Apply journal-specific formatting requirements. Triggers: format for journal, journal requirements, submission format, style guide. Local database covers 16 publisher and journal profiles; other journals are looked up via web search."
---

# Journal Formatting

Look up and apply journal-specific formatting requirements to manuscripts. `references/journal-database.md` carries 16 publisher and journal profiles (Elsevier, Springer, Nature family, IEEE, ACM, Wiley, Taylor and Francis, PLOS ONE, Science, MDPI, and more); anything not in it is looked up from the publisher's author guidelines via web search.

## Supported Publishers and Document Classes

| Publisher | Document Class | Notes |
|-----------|---------------|-------|
| Elsevier | `elsarticle` | Supports `1p`, `3p`, `5p` column layouts |
| Springer | `svjour3` | Also `svmono`, `svmult` for books |
| IEEE | `IEEEtran` | Conference and journal variants |
| ACM | `acmart` | `sigconf`, `sigplan`, `sigchi`, `tog` formats |
| Wiley | `wiley` | Uses custom `.cls` per journal |
| Taylor & Francis | `interact` | NLM-style markup |
| PLOS | `plos` | Single LaTeX class for all PLOS journals |
| Nature | Custom | Requires Nature `.cls` and `.bst` |
| Science | Custom | AAAS submission template |
| MDPI | `mdpi` | Open-access multidisciplinary journals |

## Journal Requirement Categories

### Document Structure
- Required sections (e.g., Data Availability, Ethics Statement, CRediT Author Statement)
- Section ordering constraints
- Abstract structure (structured vs unstructured)
- Abstract word limit
- Keyword count and format

### Length Limits
- Total word count (e.g., 8000 words for full article)
- Per-section word guidance
- Maximum number of figures and tables
- Maximum number of references
- Page limits for camera-ready versions

### Figure Requirements
- Minimum resolution (typically 300 DPI for print, 150 DPI for web)
- Accepted file formats (EPS, PDF, TIFF, PNG, JPEG)
- Color mode (CMYK for print, RGB for online)
- Maximum figure file size
- Figure width specifications (single-column: 84mm, double-column: 174mm)
- Naming convention (e.g., `Fig1.eps`, `Figure_1.tiff`)

### Figure Style Presets

Map the target journal's publisher family to a figure style preset before generating figures:

- Nature portfolio (Nature, Nature Communications, Scientific Reports, and sibling journals): use the `nature` preset
- IEEE (journal or conference `IEEEtran` targets): use the `ieee` preset
- Everything else (Elsevier, Springer, ACM, Wiley, Taylor and Francis, PLOS, Science, MDPI, and any journal not otherwise matched): use the `default` preset

Presets (fonts, color palettes, line weights, sizing) are defined in `references/figure-styles.md`.

### Reference Format
- Citation style (APA, IEEE, Vancouver, Chicago, numbered, author-year)
- BibTeX style file (`.bst`) to use
- Maximum number of references
- DOI requirement (mandatory or optional)
- URL formatting rules

### Supplementary Material
- Allowed supplementary formats
- Naming conventions
- Separate file or appendix
- Maximum file sizes

## Requirement Lookup Workflow

1. User specifies target journal name
2. Check `references/journal-database.md` for cached requirements
3. Or search that same file from the command line with `scripts/journal-lookup.py "<journal name>"`. The database is its only data source and it makes no web requests, so it can only return a journal already listed there
4. Read the result honestly. The script exits 0 only on a real hit: an exact profile name, or a query and a profile name that contain one another. A profile that merely shares words with the query is a guess, not a hit, and is never presented as one: text output lists such profiles by name under `Closest matches (not exact database entries)`, `--format json` puts them under a separate `suggestions` key (real hits go under `matches`), and a query with no real hit exits 1. Never apply a suggested profile's requirements to the queried journal
5. If there is no hit, use web search to locate the journal's author guidelines
6. Parse and structure requirements into standard format
7. Cache results in `references/journal-database.md` for future use

## Formatting Application

### LaTeX Formatting
1. Read current `main.tex` document class and packages
2. Switch document class to journal-required class (e.g., `\documentclass[review]{elsarticle}`)
3. Update preamble: add required packages, remove conflicting ones
4. Restructure sections to match journal ordering
5. Apply bibliography style (`\bibliographystyle{journal-style}`)
6. Set figure and table formatting to journal specifications
7. Add required boilerplate sections (data availability, conflicts, etc.)

### Word Formatting
1. Download journal Word template if available
2. Apply template styles to existing DOCX
3. Adjust margins, fonts, spacing per requirements
4. Ensure heading styles match template definitions

## Compliance Validation

Run a pre-submission checklist that verifies:

| Check | Rule |
|-------|------|
| Word count | Under journal maximum |
| Abstract length | Under journal limit |
| Figure count | Under journal maximum |
| Figure resolution | Meets minimum DPI |
| Figure format | Accepted file type |
| Reference count | Under journal limit |
| Reference format | Matches required style |
| Required sections | All present |
| Author information | Complete (affiliations, ORCID, corresponding author) |
| Keywords | Correct count and format |
| Title length | Under character/word limit if specified |
| Line numbering | Enabled if required for review |
| Double spacing | Applied if required for review |

### Validation Output

```markdown
# Submission Compliance Report: [Journal Name]

## Status: PASS / FAIL (N issues)

### Passed Checks
- [x] Word count: 7,234 / 8,000 max
- [x] Abstract: 248 / 250 words
- [x] Figures: 5 / 8 max
...

### Failed Checks
- [ ] Missing section: Data Availability Statement
- [ ] Figure 3: resolution 150 DPI (minimum 300 DPI required)
...

### Warnings
- Reference count 48 / 50 max (close to limit)
...
```

## Workflow

1. User provides target journal name (or it is read from `manuscript/config.yaml`)
2. Look up journal requirements via database, script, or web search
3. Display requirements summary for user confirmation
4. Apply formatting changes to manuscript files
5. Run compliance validation
6. Report pass/fail with specific issues to fix
7. Re-validate after user addresses issues

## Integrity constraints

- Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it: never invent a DOI, author list, venue, or year.
- Never invent data: only user-provided or actually computed numbers may appear as results. Anything illustrative must be labeled "(synthetic, for demonstration)".
- Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).
- Compile-check all LaTeX by running `scripts/latex-compile.py` (or `latex-compile.sh` on POSIX) before delivery: it uses whichever TeX engine is installed (tectonic recommended, or latexmk / pdflatex from TeX Live, MiKTeX, or MacTeX).

Canonical copy: `references/integrity-constraints.md`.
