---
name: citation-management
description: "Manage bibliography, sync Zotero/Mendeley, validate DOIs, convert citation formats. Triggers: add citation, manage bibliography, sync zotero, import references, check citations, validate bib, convert citations."
---

# Citation Management

Maintains a validated, consistent bibliography in `library.bib` with full lifecycle management: import, validate, convert, audit.

## CRITICAL INTEGRITY RULE
**NEVER fabricate or hallucinate bibliography entries.** Every BibTeX entry must originate from a real source: a user-provided reference, a DOI lookup, a Zotero/Mendeley import, or a literature-search result. If a DOI cannot be resolved, flag the entry rather than guessing metadata.

## Workflow

1. **Locate bibliography** at `manuscript/references/library.bib`. If it does not exist, create it with a header comment block.
2. **Determine operation** from user intent:
   - Add/import entries → go to Import Operations
   - Validate/check entries → go to Validation Pipeline
   - Convert format → go to Format Conversion
   - Audit manuscript → go to Manuscript Audit
3. **Execute operation** and report results with counts and any warnings.

## Citation Key Format

Generate keys in `authorYear` style:
- Single author: `smith2024`
- Two authors: `smithJones2024`
- Three or more: `smithEtAl2024`
- Disambiguation: append lowercase letter (`smith2024a`, `smith2024b`)
- No special characters, no spaces, ASCII only

When a key collision is detected, append a disambiguating keyword from the title: `smith2024attention`.

## Import Operations

### Manual Add (from DOI)
1. User provides a DOI (e.g., `10.1234/example`)
2. Resolve via CrossRef API: `https://api.crossref.org/works/{doi}`
3. Parse response into BibTeX fields: author, title, journal, year, volume, pages, doi, abstract
4. Generate citation key
5. Append to `library.bib`
6. Confirm entry back to user

### Manual Add (from metadata)
1. User provides title, authors, year, and optionally journal/conference
2. Search CrossRef by title to find DOI: `https://api.crossref.org/works?query.bibliographic={title}&rows=3`
3. If match found (title similarity > 0.85), use resolved metadata and DOI
4. If no match, create entry from user-provided data and flag as `% UNVERIFIED: no DOI resolved`
5. Append to `library.bib`

### Zotero Import
Requires Zotero MCP connector.
1. Connect to user's Zotero library
2. List available collections, let user select
3. Fetch items from selected collection
4. Convert each item to BibTeX format
5. Deduplicate against existing `library.bib` entries (match by DOI, then by title similarity)
6. Append new entries, report skipped duplicates

### Mendeley Import
Requires Mendeley MCP connector.
1. Authenticate via Mendeley API
2. List folders/groups, let user select
3. Fetch documents from selected folder
4. Convert each document to BibTeX format
5. Deduplicate against existing `library.bib` entries
6. Append new entries, report skipped duplicates

### Batch Import (from .bib file)
1. User provides path to an external `.bib` file
2. Parse all entries
3. Deduplicate against existing `library.bib`
4. Optionally re-validate each entry via CrossRef
5. Merge new entries into `library.bib`
6. Report: added, skipped (duplicate), flagged (unverified)

## Validation Pipeline

Run validation on all entries in `library.bib` or on a specific subset.

### DOI Resolution Check
For each entry with a `doi` field:
- Resolve via `https://doi.org/{doi}` (expect HTTP 302)
- If resolution fails, flag entry: `% WARNING: DOI does not resolve`
- If entry lacks a DOI, attempt lookup via CrossRef title search

### Metadata Completeness
Flag entries missing required fields:
- `@article`: author, title, journal, year, volume
- `@inproceedings`: author, title, booktitle, year
- `@book`: author/editor, title, publisher, year
- `@phdthesis` / `@mastersthesis`: author, title, school, year
- `@misc` / `@online`: author, title, year, url or doi

### Predatory Journal Detection
Check journal name against known predatory journal indicators:
- Beall's List patterns (if available)
- Suspiciously broad scope titles ("International Journal of All Sciences")
- Missing ISSN or unresolvable ISSN
- Flag with: `% WARNING: Potential predatory journal, verify manually`

### Retraction Check
For entries with DOIs:
- Check against Retraction Watch database (via CrossRef metadata `update-to` field)
- If retracted, flag prominently: `% RETRACTED: do not cite without disclosure`
- Report retraction reason if available

### Batch Validation
Invoke `scripts/bib-validator.py` for full-library validation:
```
python scripts/bib-validator.py manuscript/references/library.bib --check-doi --check-retracted --check-fields
```
Parse output and present summary table of issues found.

## Format Conversion

Convert citation style for in-text citations and reference list formatting. This does NOT change `library.bib` (which is always BibTeX). It changes how citations render in the manuscript.

### Supported Formats

| Format | In-text example | Config |
|--------|----------------|--------|
| APA 7 | (Smith et al., 2024) | `biblatex` with `style=apa` |
| IEEE | [1] | `biblatex` with `style=ieee` |
| Chicago | (Smith 2024) | `biblatex` with `style=chicago-authordate` |
| Vancouver | (1) | `biblatex` with `style=vancouver` |
| MLA | (Smith et al. 42) | `biblatex` with `style=mla` |

### Conversion Procedure
1. Identify current citation style from `manuscript/config.yaml` or `main.tex` preamble
2. Update `\usepackage[style=...]{biblatex}` in `main.tex`
3. Adjust any manual citation commands (`\citep`, `\citet`, `\parencite`, `\textcite`) to match target style package
4. Report changes made

## Manuscript Audit

### Missing Citations
Scan all `.tex` files in `manuscript/` for `\cite{...}`, `\citep{...}`, `\citet{...}`, `\parencite{...}`, `\textcite{...}` commands. Extract all referenced keys. Compare against keys in `library.bib`.
- Report any key referenced in `.tex` but absent from `.bib`: **missing citation**
- Provide count and list of missing keys

### Unused Entries
Compare all keys defined in `library.bib` against all keys referenced across `.tex` files.
- Report any key in `.bib` but never referenced: **unused entry**
- Do not auto-remove; list them and let user decide

### Unsupported Claims
Scan manuscript text for factual statements (sentences containing quantitative claims, comparisons, or assertions about prior work) that lack a nearby `\cite{}` command. Flag these as potentially unsupported. This is a heuristic check: present results as suggestions, not errors.

### Audit Report Format
```
Citation Audit Report
=====================
Total .bib entries: 47
Total \cite keys in manuscript: 42

Missing citations (in .tex but not in .bib): 3
  - \cite{wang2023transformer} in introduction.tex:14
  - \cite{liuEtAl2024} in methods.tex:87
  - \cite{chen2022benchmark} in results.tex:31

Unused entries (in .bib but not in .tex): 8
  - zhang2020survey
  - patel2019deep
  - ...

Validation issues: 2
  - smith2024: DOI does not resolve
  - globalJournal2023: Potential predatory journal

Potentially unsupported claims: 4
  - introduction.tex:22: "Transformers have achieved state-of-the-art..."
  - discussion.tex:15: "Previous studies show a 30% improvement..."
  - ...
```

## Citation Integrity Audit

Triggered by: "citation integrity", "verify citations", "check citation accuracy", "are my citations correct"

Goes beyond checking whether citations exist: it verifies whether each citation is used honestly and accurately in the manuscript.

### Verification Process

For each `\cite{}` in the manuscript, perform the following checks:

#### 1. Claim-Source Alignment
- Extract the claim the manuscript makes when citing the paper
- Retrieve the cited paper's actual content (via Scite smart citations, abstract, or full text when available)
- Assess whether the cited paper actually supports the claim being made
- Flag mismatches: cases where the manuscript says "Smith et al. showed X" but the paper actually showed Y

#### 2. Citation Context Accuracy
- Use Scite citation context (when available) to see how OTHER papers cite this same source
- If the manuscript cites the paper as "supporting" but most other citing papers treat it as "contrasting" (or vice versa), flag the discrepancy
- Identify citations where the manuscript cherry-picks a minor finding while ignoring the paper's main conclusion

#### 3. Specificity Verification
- For citations that reference specific numbers, statistics, or quotes: verify these against the source
- Flag unverifiable specifics (e.g., "Smith et al. reported a 95% accuracy" when the actual figure cannot be confirmed)
- Check page numbers or section references when provided

#### 4. Context Misrepresentation Detection
- Detect "citation bluffing": citing a paper in a way that implies the author read it, when the citation is likely copied from another paper's reference list
- Indicators: citing a paper for a claim it does not directly make, using the same citation context as a third paper
- Detect scope inflation: citing a narrow study as if it proved a broad claim

### Integrity Report Output

```
Citation Integrity Audit
========================
Total citations analyzed: 34
Verified (high confidence): 28
Uncertain (needs manual check): 4
Flagged (potential misrepresentation): 2

Detailed Findings:

[HIGH CONFIDENCE] \cite{smith2024} in introduction.tex:15
  Claim: "Transformers outperform RNNs on long-range dependencies"
  Source says: Confirmed, paper's main finding
  Confidence: 95%

[FLAGGED] \cite{jones2023} in discussion.tex:42
  Claim: "Previous work confirms our approach is optimal"
  Source says: Paper actually presents a competing approach with better results
  Confidence: 82%
  Action: Review this citation, may be misrepresenting the source

[UNCERTAIN] \cite{chen2022} in methods.tex:28
  Claim: "Standard preprocessing pipeline (Chen et al., 2022)"
  Source says: Could not retrieve full text to verify preprocessing details
  Confidence: 40%
  Action: Manually verify that your pipeline matches what Chen et al. describe
```

### Integration with Scite

When the Scite MCP server is connected, the integrity audit is significantly more powerful:
- Scite smart citations provide actual sentences from the cited paper and from other papers citing it
- Supporting/contrasting/mentioning tallies help identify whether the manuscript's characterization aligns with community consensus
- Without Scite, the audit relies on abstracts and metadata only, which reduces confidence scores

## Read/Write Operations

### Reading entries
- Parse `library.bib` to extract all entries with their keys, types, and fields
- Support querying by key, author, year, journal, or keyword in title

### Updating entries
- Locate entry by key in `library.bib`
- Replace or add specific fields while preserving the rest
- Re-validate after update if DOI changed

### Deleting entries
- Only delete when explicitly requested by user
- Confirm before deletion
- Warn if the key is still referenced in any `.tex` file

### Sorting
On request, sort `library.bib` entries by:
- Citation key (alphabetical): default
- Year (ascending or descending)
- Author last name (alphabetical)

## Integration Points

- **literature-search:** When user selects papers from search results, hand off to citation-management for `.bib` entry creation
- **manuscript-setup:** Initial `library.bib` is created by manuscript-setup; citation-management maintains it thereafter
- **journal-formatting:** Citation style must match target journal; journal-formatting may trigger a format conversion
- **pre-commit-citation-check hook:** Runs the Missing Citations and Unused Entries audits automatically before git commits
- **scripts/bib-validator.py:** Batch validation backend; citation-management invokes it and interprets results

## Connector Usage

Check which connectors are available before attempting imports. If a connector is unavailable, inform the user and suggest manual alternatives (DOI entry, .bib file import).

### CrossRef API
```
Resolve DOI:    GET https://api.crossref.org/works/{doi}
Search by title: GET https://api.crossref.org/works?query.bibliographic={title}&rows=5
```
Include `mailto` parameter for polite pool: `?mailto=user@example.com`

### Zotero MCP
Use Zotero MCP connector tools to list collections and fetch items. Convert Zotero JSON to BibTeX fields.

### Mendeley MCP
Use Mendeley MCP connector tools to authenticate, list folders, and fetch documents. Convert Mendeley JSON to BibTeX fields.

## Integrity constraints

1. Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it: never invent a DOI, author list, venue, or year.
2. Never invent data: only user-provided or actually computed numbers may appear as results; anything illustrative must be labeled "(synthetic, for demonstration)".
3. Refuse to present as valid output any of the following: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).

Canonical copy: `references/integrity-constraints.md`.
