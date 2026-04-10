---
name: citation-context
description: "Analyze how citations are used — supportive, contrastive, or mentioning. Triggers: citation context, how is this cited, citation framing, analyze citations, citation roles, supporting vs contrasting, citation audit, check citation framing."
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

## Operations

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
  introduction.tex:14 — \cite{smith2023} — Supporting
    Context: "As shown by Smith et al. (2023), transformers outperform..."
    
  methods.tex:31 — \cite{jones2022benchmark} — Methodological
    Context: "We evaluate on the benchmark introduced by Jones (2022)..."
```

### Audit Citation Framing
Triggered by: "audit citations", "check citation framing", "are my citations accurate"

**Workflow:**
1. For each citation in the manuscript, identify the role (as above)
2. If Scite MCP connector is available, retrieve smart citation data for the cited DOI
3. Compare the user's framing against the actual relationship:
   - Does the cited paper actually support the claim being made?
   - Is a "supporting" citation actually a contrasting result?
   - Is the cited paper's finding accurately represented?
4. Flag mismatches and potentially misleading framings

**Output:**
```
Citation Framing Audit
======================
Potential issues found: 3

WARNING: introduction.tex:22 — \cite{smith2023} framed as Supporting
  Your text: "Smith et al. (2023) confirmed that X improves Y"
  Actual finding: Smith et al. found X improves Y only under condition Z
  Suggestion: Add qualifier — "under condition Z"

WARNING: discussion.tex:45 — \cite{jones2022} framed as Contrasting
  Your text: "Unlike Jones (2022), we found..."
  Actual finding: Jones reported mixed results, not a clear contradiction
  Suggestion: Reframe as "Extending the mixed findings of Jones (2022)..."
```

### Suggest Citation Framing
Triggered by: "how should I cite this", "frame this citation", "cite this as"

**Workflow:**
1. User provides a citation key and the claim they want to support
2. Retrieve the cited paper's abstract and key findings (via Scite MCP or literature-search)
3. Determine the actual relationship between the paper and the user's claim
4. Suggest appropriate framing with example sentences
5. Warn if the paper does not actually support the intended use

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
  Contrasting: wang2022  (1 citation — addressed in discussion)
  Status: Well-supported

Claim: "Training is more efficient than prior approaches"
  Supporting: smith2023  (1 citation)
  Contrasting: none found
  Status: Under-supported — consider additional evidence
```

## Scite MCP Integration

When the Scite MCP connector is available, use it for enhanced citation context analysis:
- Retrieve "smart citations" — actual excerpts showing how papers cite each other
- Access citation statement classifications (supporting, contrasting, mentioning)
- Cross-reference citation contexts across the literature, not just the user's manuscript
- Check editorial notices for retractions or corrections

When Scite is unavailable, fall back to:
- Local text analysis of the user's manuscript only
- Signal phrase detection for role classification
- Abstract-level comparison via literature-search results

## Integration Points

- **literature-search:** Retrieves paper metadata and abstracts for framing analysis
- **citation-management:** Shares `library.bib` entries; may flag entries needing framing review
- **research-convergence:** Argument maps inform which citations should be supporting vs contrasting
- **paper-drafting:** Citation context analysis guides how to frame references during drafting
- **peer-review:** Reviewers check whether citation framing is accurate and fair
- **post-draft-integrity hook:** Can trigger citation framing audit after drafting completes
