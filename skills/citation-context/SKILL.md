---
name: citation-context
description: "Analyze how citations are used: supportive, contrastive, or mentioning. Triggers: citation context, how is this cited, citation framing, analyze citations, citation roles, supporting vs contrasting, citation audit, check citation framing."
---

# Citation Context

Analyze whether citations are supportive, contrastive, or merely mentioning. Helps build stronger arguments by ensuring citation framing matches the actual relationship between papers.

## Citation Role Taxonomy

### Supporting
The cited work provides evidence for or agrees with the current claim.
- Signal phrases: "As shown by", "Consistent with", "In line with", "Confirmed by", "Supporting this", "corroborates"
- Example: "As demonstrated by Smith et al. (2023), attention mechanisms improve performance on long-range dependencies."

### Contrasting
The cited work disagrees with, contradicts, or presents an alternative to the current claim.
- Signal phrases: "Unlike", "However", "In contrast to", "Contradicting", "While X found", "disputes"
- Example: "Unlike Jones (2022), who reported no significant effect, our results show a clear improvement."

### Mentioning
Neutral reference without evaluative framing. Acknowledges existence or provides background.
- Signal phrases: "X studied", "X proposed", "X introduced", "X reported", "According to"
- Example: "Smith (2023) proposed a transformer-based approach for protein folding."

### Extending
The current work builds directly on the cited work, adding to it or adapting it.
- Signal phrases: "Building on", "Extending the work of", "Adapting the approach of", "Inspired by"
- Example: "Building on the framework of Smith (2023), we introduce a multi-scale attention mechanism."

### Methodological
The cited work provides a method, tool, dataset, or metric used in the current study.
- Signal phrases: "Following the approach of", "Using the method described in", "Evaluated on the benchmark of", "Implemented using"
- Example: "We evaluate our model on the benchmark introduced by Smith et al. (2023)."

## Deterministic backend

Citation enumeration and every existence claim about a citing or cited paper route through the
`researcher-core` evidence kernel. Claude keeps the interpretive work (deciding whether a
citation is supporting, contrasting, mentioning, extending, or methodological); core does the
reproducible work (enumerating who cites a paper, resolving four-state identity, and checking
retraction status). Full command reference: `references/core-cli.md`.

### Enumerate who cites a paper (citation graph)

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core citations <doi-or-id> --limit 50 --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core references <doi-or-id> --limit 50 --json
```

- `citations <id>` returns forward citations (works that cite this one); `references <id>`
  returns backward references (works this one cites). Both return
  `{seeds[], direction, depth, nodes[], edges[], warnings[], sources[], counts{}}`, and each
  `nodes[]` element is a CSL-JSON record. Read `nodes[]` for the enumerated works and
  `warnings[]` for any source that failed.
- Default sources are `openalex,semantic_scholar,opencitations`. A source in `warnings[]` is a
  coverage gap, not evidence a paper is uncited.

### Verify any citing entry asserted as existing (axis a, four-state)

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-ref "<doi-or-title>" --json
```

Read, per entry: `verdict` (`verified` / `mismatch` / `unresolvable` / `inconclusive`),
`refusal_grade` (already computed, never re-derive it), `reason`, `source_outcomes[]`,
`best_match`, and the `status` and `accessibility` blocks. Consume the four-state verdict,
NEVER a boolean.

- **Refusal-grade fires ONLY on `unresolvable` or `mismatch`** (plus `retracted` from axis b,
  `contradicted` from axis c). A citing entry that is `unresolvable` or `mismatch` is FLAGGED as
  unresolved, never listed as an established citing work.
- **`inconclusive` is NEVER refusal-grade.** It means a source errored or only one index holds
  the paper. Surface it as an open item ("could not confirm, one index only"), never as
  fabrication. Accusing an honest author of inventing a real citation is the worst failure here.

### Retraction annotations on citing papers (axis b)

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core status <doi-or-id> --json
```

Read `entries[].status` for `current` / `corrected` / `retracted` / `expression-of-concern`.
Annotate any citing paper that is `retracted` or `expression-of-concern` inline: a retracted
work still counts in the tally but must carry the notice. `status.checked: false` means axis (b)
was never answered, which is absence of evidence, not a clean bill of health.

### Framing faithfulness (axis c), and the layer it names

When auditing whether the user's framing matches the cited paper's actual finding, anchor on M2
passages:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages index <doi-or-url> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core faithfulness "<the user's claim>" --doc <doc-id> --json
```

- Every faithfulness verdict NAMES its layer: full-text when an OA copy was indexed,
  abstract-only otherwise. When full text is unavailable the verdict is `insufficient-passage`,
  never "clean" or "faithful"; surface it as an open item, never refusal-grade.
- Axis (c) is a LEXICAL baseline (BM25 plus token-overlap and polarity heuristics). It can miss
  overstatements: a framing it calls `supported` may still overreach. Treat `supported` as "no
  lexical contradiction found at this layer", not proof the framing is accurate. Only
  `contradicted` is refusal-grade on this axis.

### Scite and Claude, side by side

When the Scite MCP connector is connected, its tallies add quantitative supporting / contrasting
/ mentioning counts across the whole literature. These COMPLEMENT, never replace, Claude's
interpretive classification of the specific sentence in front of you. Report both: the Scite
tally (where present) and Claude's role judgment for this manuscript's usage.

### Degradation path (state it in the output when a fallback is used)

1. **Core present** (`uv` + `core/`, or `pip install -e core/`): citation graph, four-state
   identity, status, and faithfulness as above.
2. **No `uv` / no core**: fall back to the **Scite MCP** (smart citations, tallies, editorial
   notices) and **Zotero MCP** (library metadata) where connected.
3. **No MCP either**: web search plus local `\cite` text analysis only. Say so, and never assert
   a citing work exists or a paper is retracted without a retrieval behind it.

## Operations

### Enumerate Citing Works
Triggered by: "who cites this paper", "analyze citations of this paper", "citation audit" for a specific paper

**Workflow:**
1. Resolve the target paper (DOI, arXiv ID, or OpenAlex ID).
2. Run core `citations <id> --json` to enumerate the works that cite it (and `references <id>`
   for what it cites). Read `nodes[]`; note any source in `warnings[]` as a coverage gap.
3. For each citing work you assert as existing, run `verify-ref` and consume the four-state
   verdict. List `verified` and `inconclusive` works (the latter flagged "one index only"); FLAG
   `unresolvable` / `mismatch` works as unresolved, never as established citations.
4. Run `status` over the citing set; annotate any `retracted` or `expression-of-concern` paper.
5. If Scite is connected, attach its supporting / contrasting / mentioning tallies. Claude
   classifies the interpretive role of each citation's framing.

**Output:**
```
Citing Works for Smith et al. (2023)  [DOI 10.xxxx/yyyy]
========================================================
Enumerated: 42 citing works (openalex 42, semantic_scholar 38, opencitations 40)
Coverage note: none (all sources returned)

Verified citing works:            39
Inconclusive (one index, open):    2
Unresolvable (flagged, NOT fact):  1

Retraction notices:
  jones2021: RETRACTED (axis b), still tallied, notice attached

Scite tally (where available): supporting 12, contrasting 5, mentioning 25
Claude role read (this manuscript's usage): 3 supporting, 1 contrasting
```

### Analyze Citation Roles in Manuscript
Triggered by: "analyze my citations", "citation roles", "how am I using my citations"

**Workflow:**
1. Parse all `.tex` files in `manuscript/` for citation commands (`\cite`, `\citep`, `\citet`, `\parencite`, `\textcite`)
2. For each citation, extract the surrounding sentence and paragraph context
3. Classify the citation role based on signal phrases and semantic context
4. Generate a citation context report

**Output:**
```
Citation Context Report
=======================
Total citations analyzed: 47

Role Distribution:
  Supporting:     18 (38%)
  Contrasting:     7 (15%)
  Mentioning:     12 (26%)
  Extending:       4  (9%)
  Methodological:  6 (13%)

Detailed Analysis:
  introduction.tex:14, \cite{smith2023}: Supporting
    Context: "As shown by Smith et al. (2023), transformers outperform..."
    
  methods.tex:31, \cite{jones2022benchmark}: Methodological
    Context: "We evaluate on the benchmark introduced by Jones (2022)..."
```

### Audit Citation Framing
Triggered by: "audit citations", "check citation framing", "are my citations accurate"

**Workflow:**
1. For each citation in the manuscript, identify the role (as above).
2. Confirm the cited paper exists with core `verify-ref`; consume the four-state verdict and
   attach any `status` retraction notice. Flag `unresolvable` / `mismatch` entries rather than
   auditing framing against a paper that may not exist.
3. Anchor the user's framing against the source with core `faithfulness` (see Deterministic
   backend). Every verdict names its layer (abstract vs full-text); an `insufficient-passage`
   verdict is an open item, not a mismatch. Axis (c) is a lexical baseline that can miss
   overstatements, so a `supported` verdict is not proof the framing is accurate.
4. If Scite MCP is connected, add its smart-citation tallies as corroboration.
5. Flag genuine framing mismatches (a `contradicted` faithfulness verdict, or a Scite tally that
   inverts the user's stated role); the interpretive call stays with Claude.

**Output:**
```
Citation Framing Audit
======================
Potential issues found: 3

WARNING: introduction.tex:22, \cite{smith2023} framed as Supporting
  Your text: "Smith et al. (2023) confirmed that X improves Y"
  Actual finding: Smith et al. found X improves Y only under condition Z
  Suggestion: Add qualifier: "under condition Z"

WARNING: discussion.tex:45, \cite{jones2022} framed as Contrasting
  Your text: "Unlike Jones (2022), we found..."
  Actual finding: Jones reported mixed results, not a clear contradiction
  Suggestion: Reframe as "Extending the mixed findings of Jones (2022)..."
```

### Suggest Citation Framing
Triggered by: "how should I cite this", "frame this citation", "cite this as"

**Workflow:**
1. User provides a citation key and the claim they want to support.
2. Retrieve the cited paper via core `get` (abstract and metadata) or `fulltext` (OA full text
   where available); fall back to Scite MCP or literature-search if core is absent.
3. Determine the actual relationship with core `faithfulness`, naming the layer verified (abstract
   vs full-text). Remember axis (c) is a lexical baseline and can miss overstatements.
4. Suggest appropriate framing with example sentences.
5. Warn if the paper does not actually support the intended use. When the verdict is
   `insufficient-passage` (no OA full text), say the framing could not be checked at full-text
   level, and surface it as an open item rather than endorsing the framing.

**Output:**
```
Citation Framing Suggestion for \cite{smith2023}
================================================
Your claim: "Attention mechanisms are essential for long-range dependencies"
Paper finding: Smith et al. showed attention helps but is not strictly necessary

Recommended role: Supporting (with qualification)
Suggested framing:
  "Smith et al. (2023) demonstrated that attention mechanisms significantly
   improve performance on long-range dependency tasks, though alternative
   approaches such as state-space models show competitive results."

NOT recommended:
  "Smith et al. (2023) proved that attention is essential..." (overstates finding)
```

### Build Argument Support Map
Triggered by: "map citations to arguments", "citation support map", "which citations support which claims"

**Workflow:**
1. Extract the argument structure from the manuscript (or from an argument-map.md if available)
2. Map each citation to the claim(s) it supports or challenges
3. Identify claims with insufficient citation support
4. Identify citations that are not clearly linked to any claim
5. Suggest additional citations needed for under-supported claims

**Output:**
```
Argument Support Map
====================

Claim: "Method X outperforms baselines"
  Supporting: smith2023, jones2024, chen2023  (3 citations)
  Contrasting: wang2022  (1 citation, addressed in discussion)
  Status: Well-supported

Claim: "Training is more efficient than prior approaches"
  Supporting: smith2023  (1 citation)
  Contrasting: none found
  Status: Under-supported: consider additional evidence
```

## Scite MCP Integration

Scite complements the deterministic backend; it does not replace it. Core enumerates citing
works and resolves identity and status deterministically (see Deterministic backend); Scite adds
literature-wide quantitative tallies when connected:
- "Smart citations": actual excerpts showing how papers cite each other
- Citation statement classifications (supporting, contrasting, mentioning) as counts
- Cross-references across the literature, not just the user's manuscript
- Editorial notices for retractions or corrections (corroborating core's axis-b `status`)

The interpretive role classification for a specific sentence always stays with Claude. When
neither core nor Scite is available, fall back to local text analysis of the user's manuscript
(signal-phrase role detection, abstract-level comparison via literature-search) and say so.

## Integration Points

- **literature-search:** Retrieves paper metadata and abstracts for framing analysis
- **citation-management:** Shares `library.bib` entries; may flag entries needing framing review
- **research-convergence:** Argument maps inform which citations should be supporting vs contrasting
- **paper-drafting:** Citation context analysis guides how to frame references during drafting
- **peer-review:** Reviewers check whether citation framing is accurate and fair
- **post-draft-integrity hook:** Can trigger citation framing audit after drafting completes

## Integrity constraints

- Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it; never invent a DOI, author list, venue, or year.
- Never invent data: only user-provided or actually computed numbers may appear as results. Anything illustrative must be labeled "(synthetic, for demonstration)".
- Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).
- Consume the four-state identity verdict, never a boolean. Refusal-grade behavior (flag as unresolved, withhold from the citing list) fires ONLY on `unresolvable` or `mismatch` on axis (a), `retracted` on axis (b), or `contradicted` on axis (c). `inconclusive` and `insufficient-passage` are NEVER refusal-grade: surface them as open items. Treating `inconclusive` as fabrication accuses an honest author of inventing a real citation.

Canonical copy: `references/integrity-constraints.md`.
