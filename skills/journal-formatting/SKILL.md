---
name: journal-formatting
description: "Apply journal-specific formatting requirements. Triggers: format for journal, journal requirements, submission format, style guide. Supports 50+ journals."
---

# Journal Formatting

Look up and apply journal-specific formatting requirements to manuscripts.

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
3. If not found, run `scripts/journal-lookup.py` to search publisher websites
4. If still not found, use web search to locate author guidelines
5. Parse and structure requirements into standard format
6. Cache results in `references/journal-database.md` for future use

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
# Submission Compliance Report — [Journal Name]

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
