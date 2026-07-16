---
name: citation-management
description: "Manage bibliography, sync Zotero/Mendeley, validate DOIs, convert citation formats. Triggers: add citation, manage bibliography, sync zotero, import references, check citations, validate bib, convert citations."
---

# Citation Management

Maintains a validated, consistent bibliography in `library.bib` with full lifecycle management: import, validate, convert, audit.

## CRITICAL INTEGRITY RULE
**NEVER fabricate or hallucinate bibliography entries.** Every BibTeX entry must originate from a real source: a user-provided reference, a DOI lookup, a Zotero/Mendeley import, or a literature-search result. If a DOI cannot be resolved, flag the entry rather than guessing metadata.

## Deterministic backend

Validation and any "clean" declaration route through the `researcher_core` evidence kernel, which resolves and verifies each entry deterministically instead of asking the model to judge whether a citation is real. Full command and JSON reference: `references/core-cli.md`.

### verify-bib (axes a, b, d)

Run before ANY bibliography is declared clean:
```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-bib manuscript/references/library.bib --json
```
Default sources: `openalex,crossref,datacite`. The report is `{schema_version, protocol_version, versions{}, input{}, thresholds{}, sources_queried[], entries[], summary{}}`. Consume, per `entries[]`:
- `verdict` (axis a, identity): `verified` | `mismatch` | `unresolvable` | `inconclusive`
- `refusal_grade` (bool): the kernel's own refusal decision. Trust it; never re-derive it.
- `reason`, `source_outcomes[]` (each `confirmed` | `negative` | `source_error`), `tally`, `best_match`
- `status{}` (axis b): `current` | `corrected` | `retracted` | `expression-of-concern`, or `checked: false`
- `accessibility{}` (axis d): `full-text` | `abstract-only` | `unavailable`

### status (axis b sweep)

A focused publication-status sweep over the same library. verify-bib already carries a per-entry `status` block; run `status` when you want a standalone re-check (e.g. months after the last verify):
```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core status manuscript/references/library.bib --json
```
Default sources: `crossref,openalex`. Report shape `{... entries[], summary{}}`, each entry carrying the axis (b) verdict above. `status.checked: false` is an absence of evidence, NOT a clean bill of health: do not read it as `current`.

### Four-state verdict and the refusal-grade rule

Consume the FOUR-STATE identity verdict, never a boolean. Refusal-grade behavior (withholding an entry, telling the user a citation looks fabricated or wrong) fires ONLY on:
- axis (a) `unresolvable` or `mismatch`
- axis (b) `retracted`
- (in the integrity audit) axis (c) `contradicted`

`inconclusive` is NEVER refusal-grade: it means a source errored or only one index holds the paper, so a clean negative could not be asserted. Acting on it would accuse an honest author of fabricating a real citation, the worst failure this skill can make. Surface it as an open item and move on. `insufficient-passage` (axis c) and `corrected` / `expression-of-concern` (axis b) are likewise surfaced for human review, never refusal-grade on their own.

### Clean-declaration gate

A bibliography is declared CLEAN only when `verify-bib` reports ZERO refusal-grade entries:
- Zero `unresolvable`, zero `mismatch` (axis a), zero `retracted` (axis b).
- `inconclusive` entries are LISTED for human review and do NOT block the clean declaration.
- `corrected` and `expression-of-concern` are surfaced as mandatory checkpoints (a retraction or concern is a disclosure decision, never a silent drop) but do not, by themselves, block clean.

State the count of each surfaced-but-non-blocking class in the report so nothing is hidden.

### Degradation path (D3)

Core is optional; the plugin never hard-fails without it. Prefer core, then degrade, and STATE in the output which backend produced the report:
1. **core `verify-bib` / `status`** (above) when `uv` and `core/` are present, or via the `pip install -e core/` fallback (`researcher-core verify-bib ... --json`).
2. **`scripts/bib-validator.py`** (the M1 stdlib validator) when core is absent: `python scripts/bib-validator.py manuscript/references/library.bib --check-doi --check-retracted --check-fields`. It resolves DOIs and checks retraction/fields without core, but returns coarser signals (no four-state axis verdicts); map its failures conservatively and never manufacture a refusal-grade verdict from a network error.
3. **MCP servers** where relevant: Zotero for library import/sync, Scite for retraction and status context on flagged entries.
4. **Web search / CrossRef title lookups** as the last resort (see Connector Usage).

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

### Retraction Check (axis b status)
Publication status is axis (b) of the Deterministic backend: core `verify-bib` carries a per-entry `status` block and `status` runs a focused sweep. Verdicts: `current`, `corrected`, `retracted`, `expression-of-concern`.
- A `retracted` verdict is refusal-grade and blocks a clean declaration. Flag it prominently: `% RETRACTED: do not cite without disclosure`, and report the retraction reason when available.
- `corrected` and `expression-of-concern` are surfaced as checkpoints (a disclosure decision), never silent drops, and do not block clean on their own.
- Without core, fall back to CrossRef metadata `update-to` via `python scripts/bib-validator.py manuscript/references/library.bib --check-retracted`.

### Batch Validation and Clean Declaration
Route full-library validation through the **Deterministic backend**: run core `verify-bib` (and, for a standalone status re-check, `status`) and read the per-entry `verdict`, `refusal_grade`, `status`, and `accessibility` fields. Apply the Clean-declaration gate: the library is clean only with ZERO refusal-grade entries (`unresolvable`, `mismatch`, `retracted`); `inconclusive`, `corrected`, and `expression-of-concern` entries are surfaced for human review and do NOT block a clean declaration.

When core is unavailable, fall back to the M1 stdlib validator (same D3 degradation path) and say so in the output:
```
python scripts/bib-validator.py manuscript/references/library.bib --check-doi --check-retracted --check-fields
```
Present a summary table of issues, keeping refusal-grade blockers separate from surfaced-for-review items and stating the count of each class.

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

### Verified layer and faithfulness (axis c)

Claim-source alignment anchors on the Deterministic backend's M2 passages, not on the model's memory. Index the cited paper, then score the claim with core:
```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages index <doi> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core faithfulness "<claim>" --doc <doc-id> --json
```
Axis (c) verdicts are `supported`, `partial`, `contradicted`, `insufficient-passage`. Rules:
- Every verdict NAMES THE LAYER it was checked against: `full-text` or `abstract-only`. When OA full text is unavailable, the verdict is `insufficient-passage` (never "clean" or "faithful"): it is an abstention with `clean: false` and no passage anchors, surfaced as an open item, never refusal-grade.
- `contradicted` is refusal-grade: flag the citation as a likely misrepresentation.
- Axis (c) is a LEXICAL baseline (BM25 plus token-overlap and polarity heuristics). It is honest but weak: it can call an overstatement `supported` and miss subtle scope inflation. Present its verdicts as evidence for human review, not as proof, and defer to Scite context when connected.

Degradation (D3): without core, use Scite MCP smart citations for claim context; without Scite, fall back to abstracts and metadata, and lower confidence accordingly.

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
- **researcher-core `verify-bib` / `status`:** the deterministic validation backend; citation-management routes clean declarations through it and reads the four-state verdicts (see Deterministic backend)
- **scripts/bib-validator.py:** the M1 stdlib fallback when core is absent (D3); invoked and interpreted the same way

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
