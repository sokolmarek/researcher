---
name: writing-style-analysis
description: "Analyze and emulate academic writing style. Triggers: analyze my writing style, match my style, emulate writing, learn my voice, writing profile, style analysis. Reads past papers from local folder or Google Scholar profile."
---

# Writing Style Analysis

Analyze an author's academic writing patterns and produce a reusable style profile that the paper-drafting skill loads during all subsequent drafting operations.

## Input Sources

### Local Files (preferred)
Read the author's past papers from the `author-papers/` folder in the project root. Accepted formats: `.tex`, `.pdf`, `.md`, `.txt`, `.docx`. Analyze every file found; warn if the folder is missing or empty.

### Google Scholar Profile
Triggered by: "from Google Scholar", "my scholar profile", or when user provides a URL or author name.
- Accept a Google Scholar profile URL or an author name string
- Run `scripts/scholar-scraper.py` to fetch available paper texts
- Fall back to Semantic Scholar API if scraping fails
- Store fetched papers in `author-papers/` for future reuse

## Analysis Dimensions

Compute the following metrics across all source documents:

### Sentence-Level
- **Sentence length distribution:** mean, median, standard deviation (in words)
- **Active vs passive voice ratio:** percentage of passive constructions
- **Hedging patterns:** frequency of hedging language ("may", "suggests", "potentially", "appears to", "likely")
- **Boosting patterns:** frequency of emphatic language ("clearly", "significantly", "importantly")

### Vocabulary
- **Flesch-Kincaid grade level** and **readability score**
- **Academic Word List (AWL) frequency:** percentage of tokens from the Coxhead AWL
- **Jargon density:** domain-specific term frequency per 1000 words
- **Lexical diversity:** type-token ratio (TTR) over 1000-word windows

### Paragraph and Section Structure
- **Paragraph length:** mean and range (in sentences)
- **Section length ratios:** relative word allocation across IMRaD sections
- **Topic sentence patterns:** how often first sentence states the paragraph's claim
- **Transition word preferences:** ranked list of most-used transition phrases

### Citation Behavior
- **Citation density per section:** average citations per paragraph in Introduction, Methods, Results, Discussion
- **Citation placement:** beginning, middle, or end of sentence
- **Citation clustering:** single vs multiple citations per claim
- **Self-citation rate** (if detectable)

## Output: style-profile.yaml

Write the profile to `manuscript/style-profile.yaml` with this structure:

```yaml
author: "Author Name"
source_files: ["paper1.tex", "paper2.pdf"]
generated: "2026-04-09"

sentence:
  mean_length: 22.4
  median_length: 20
  std_length: 8.1
  passive_voice_pct: 34.2
  hedging_frequency: 12.3   # per 1000 words
  boosting_frequency: 4.1

vocabulary:
  flesch_kincaid_grade: 14.2
  readability_score: 28.5
  awl_frequency_pct: 11.8
  lexical_diversity_ttr: 0.72

structure:
  paragraph_mean_sentences: 4.8
  section_ratios:
    introduction: 0.22
    methods: 0.30
    results: 0.28
    discussion: 0.20
  top_transitions: ["however", "moreover", "in contrast", "furthermore", "notably"]

citations:
  density_intro: 3.2       # per paragraph
  density_methods: 1.1
  density_results: 0.8
  density_discussion: 2.5
  placement: "end"         # dominant placement
```

## Style Calibration Pipeline

Triggered by: "calibrate style", "build style profile", "learn my writing", "style from my papers"

A structured pipeline for building a comprehensive voice profile from the author's past work.

### Input Requirements
The user provides 3-5 past papers (minimum 3 for statistical reliability). These can be:
- Files in `author-papers/` (any supported format)
- DOIs or URLs to published papers (fetched and cached locally)
- Pasted text blocks from past manuscripts

### Fingerprint Patterns
Beyond the standard metrics in Analysis Dimensions, the calibration pipeline captures qualitative "fingerprint" patterns that define the author's unique voice:

#### Characteristic Phrases and Constructions
- Recurring sentence templates (e.g., "It is worth noting that...", "Taken together, these results...")
- Preferred ways to open and close paragraphs
- Signature hedging constructions (e.g., always uses "our findings suggest" vs "the data indicate")
- Habitual intensifiers or qualifiers

#### Argumentation Patterns
- **Deductive vs inductive**: does the author state the claim first then provide evidence, or build evidence toward a conclusion?
- **Concession style**: how the author handles counterarguments ("While X, we argue Y" vs "Despite X, Y")
- **Evidence integration**: does the author present data first then interpret, or weave interpretation with presentation?

#### Limitation Introduction Style
- Where limitations appear: end of Discussion, dedicated subsection, or distributed throughout
- Framing: self-critical ("a limitation of our study is...") vs balanced ("while our approach handles X, future work could address Y")
- Specificity: vague acknowledgments vs detailed discussion of impact on findings

#### Citation Integration Style
- **Parenthetical heavy**: most citations are parenthetical — (Smith et al., 2024)
- **Narrative heavy**: most citations use the author as subject — "Smith et al. (2024) demonstrated..."
- **Mixed pattern**: specific ratio and context rules (e.g., narrative in Introduction, parenthetical in Discussion)
- Citation clustering behavior: single citations per claim vs citation strings

### Calibration Output
Extends `style-profile.yaml` with a `fingerprint` section:

```yaml
fingerprint:
  characteristic_phrases:
    - "It is worth noting that"
    - "Taken together, these results suggest"
    - "In line with previous work"
  argumentation_style: "deductive"   # deductive | inductive | mixed
  concession_pattern: "while-we-argue"  # pattern template
  limitation_style:
    location: "end-of-discussion"
    framing: "balanced"
    specificity: "detailed"
  citation_integration:
    dominant_style: "narrative"    # parenthetical | narrative | mixed
    parenthetical_pct: 35
    narrative_pct: 65
    clustering: "moderate"         # single | moderate | heavy
```

### Style Consistency Score

After calibrating a profile, any drafted section can be scored for style consistency.

Triggered by: "check style consistency", "does this match my style", "style score"

1. Load the calibrated `style-profile.yaml` (including fingerprint section)
2. Analyze the target text against every metric in the profile
3. Produce a **Style Consistency Score** (0-100):
   - **90-100**: Near-perfect match. Reads as if the author wrote it.
   - **70-89**: Good match. Minor deviations in a few dimensions.
   - **50-69**: Moderate match. Noticeable differences in voice or structure.
   - **<50**: Poor match. Significant style drift; revision recommended.
4. Report per-dimension breakdown showing which aspects match and which diverge
5. Provide specific revision suggestions to improve consistency (e.g., "Reduce average sentence length from 28 to 22 words", "Switch 3 parenthetical citations to narrative style")

**Automatic integration**: the paper-drafting skill loads this profile automatically when `manuscript/style-profile.yaml` exists. No manual activation is needed.

## Style Comparison Mode

Triggered by: "compare my style to journal", "style gap analysis"

1. Analyze 3-5 recent papers from the target journal (user provides PDFs or journal name)
2. Build a journal style profile using the same metrics
3. Produce a **gap report** highlighting differences:
   - Metrics where the author diverges significantly (>1 SD) from journal norms
   - Specific, actionable recommendations (e.g., "Shorten average sentence length from 26 to 20 words", "Increase hedging in Discussion")
4. Store journal profile in `manuscript/journal-style-profile.yaml`

## Style Application During Drafting

When `manuscript/style-profile.yaml` exists, the paper-drafting skill must:
1. Load the profile before generating any section text
2. Match sentence length distribution (target mean +/- 2 words)
3. Mirror the author's hedging and boosting frequencies
4. Use the author's preferred transition words
5. Maintain the author's active/passive voice ratio
6. Follow the author's paragraph length patterns
7. Match citation density targets per section

## Updating the Profile

- Re-run analysis at any time to incorporate new source papers
- The profile is additive: new papers are merged, not replaced
- Track profile version in the YAML header for reproducibility

## Related Skills

- **paper-drafting** — consumes the style profile during all drafting operations
- **journal-formatting** — provides target journal context for comparison mode
- **literature-search** — can fetch author papers for analysis via Semantic Scholar author endpoint
