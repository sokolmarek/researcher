---
name: research-gaps
description: "Systematically identify research gaps from an analysis of the literature that exists. Triggers: find research gaps, identify gaps, what is missing in the literature, unexplored areas, find an underexplored angle, open problems in this field, gap analysis over these papers, where is the gap, research opportunities, what hasn't been studied yet. It derives gaps from papers already collected; inventing candidate ideas without a corpus is brainstorming."
---

# Research Gaps

Systematically analyze a body of literature to identify research gaps, contradictions, and opportunities for novel contributions.

## CRITICAL INTEGRITY RULE
**NEVER fabricate gaps or misrepresent the literature.** Every identified gap must be supported by evidence from actual papers in the analyzed corpus. Cite specific papers when claiming something has or has not been studied. If the corpus is too small to draw reliable conclusions, state the limitation explicitly.

## Deterministic backend

A gap is a claim that *nothing* addresses a question, and that claim is fabricated the moment a paper you never checked already fills it. Route the retrieval and verification work through the `core/` evidence kernel so the "we searched, we traversed, we found nothing" trail is reproducible rather than asserted from memory. Heavy API detail lives in `references/core-cli.md`.

### Commands this skill uses

Standard invocation (no install step; `uv` provisions from `core/pyproject.toml` on first run):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core <cmd> ... --json
```

| Purpose | Command | JSON fields consumed |
|---|---|---|
| Verify the seed set, axis (a) | `verify-ref "<doi-or-title>"` or `verify-bib manuscript/references/library.bib` | `entries[].verdict`, `entries[].refusal_grade`, `entries[].reason`, `entries[].status`, `entries[].best_match` |
| Validation search for prior work | `search "<query>" [--since YEAR] [--limit N]` | `records[]`, `counts{retrieved, deduplicated}`, `warnings[]` |
| Forward traversal (who cites the seed) | `citations <id> [--depth 1] [--limit N]` | `nodes[]`, `edges[]`, `counts{}`, `warnings[]` |
| Backward traversal (what the seed cites) | `references <id> [--depth 1] [--limit N]` | `nodes[]`, `edges[]`, `counts{}`, `warnings[]` |
| Anchor a quoted limitation, axis (c) | `faithfulness "<claim>" --doc <id>` | `claims[].verdict`, `claims[].layer`, `summary{}` |

### Degradation path (never hard-fail, D3)

If `uv` or `core/` is unavailable, state that in the output and fall back in order:
1. **MCP servers** where relevant: Scite for citation context around a seed paper, Zotero for the user's own library as the corpus.
2. **Web search** for the validation searches, clearly labeled as non-reproducible.

The kernel is optional. The skill still runs without it, only with a weaker, unsnapshotted evidence trail; it never hard-fails for want of core.

### Identity verdicts: four states, never a boolean (D9)

Read the four-state axis (a) verdict from `verify-ref`, never a pass/fail boolean:

- **`unresolvable`** and **`mismatch`** are the only refusal-grade identity verdicts. A gap whose supporting reference (the paper cited for "X has not been studied") is refusal-grade, or whose seed paper is **`retracted`** on axis (b), is **downgraded** and held out of the ranked list until the reference resolves: that evidence cannot carry a gap claim.
- **`inconclusive`** is NEVER refusal-grade. A source errored, or only one index holds the paper. It does NOT downgrade the gap; surface it as an open item ("seed identity inconclusive, re-check"). Acting on it would accuse an honest author of citing a paper that is in fact real, the worst failure this system can make.

The kernel emits `refusal_grade` per entry, so never re-derive this rule by hand.

### The verified layer

When a gap rests on a specific claim quoted from a paper (for example "the authors name privacy as a limitation and do not address it"), anchor that quote with `faithfulness` and name the layer in the report: abstract or full-text. When full text is unavailable the verdict is `insufficient-passage`, never clean or faithful; it is an open item, not a pass, and must be surfaced. Axis (c) is a LEXICAL baseline (token overlap, BM25, polarity heuristics), so it can miss an overstatement: read a `supported` verdict as consistent-with-the-passage, not proof the paper says exactly this.

## Workflow

1. **Gather and verify the seed set**: collect papers from one or more sources:
   - `manuscript/references/library.bib` (papers already in the bibliography)
   - Recent literature-search results (from prior search sessions)
   - User-provided papers (PDFs or citations the user shares directly)

   Run `verify-ref` / `verify-bib` over the seed set first (axis (a) identity). A gap must never rest on a paper you have not confirmed exists; downgrade any gap whose supporting reference is refusal-grade (`unresolvable` / `mismatch`) or retracted, per the identity rule above. An `inconclusive` seed is an open item, not a downgrade.
2. **Extract claims and methods**: for each paper, identify:
   - Research questions addressed
   - Methodology and techniques used
   - Datasets and populations studied
   - Key findings and conclusions
   - Stated limitations and future work suggestions
3. **Cross-reference and map**: build a coverage matrix across the corpus
4. **Identify gaps**: systematically check each gap category
5. **Validate gaps through core**: confirm each candidate gap is genuinely unaddressed (not just missing from the current corpus), and record the negative-evidence trail:
   - Run targeted `search` queries for the candidate gap.
   - Traverse the citation graph around the seed set with `citations` (who cites the seed) and `references` (what the seed cites): a candidate gap is not a gap if a citing or cited paper already addresses it.
   - List, on every reported gap, the exact searches and traversals that failed to find prior work. A gap with no recorded negative evidence is unsubstantiated and must not be presented as a gap.
6. **Rank and present**: prioritize gaps by significance and feasibility

## Gap Categories

### Methodological Gaps
Techniques or approaches not yet applied to this problem domain.
- Methods proven effective in adjacent fields but absent in target domain
- Recent algorithmic advances not yet tested on established benchmarks
- Missing ablation studies or component analyses
- Lack of formal theoretical analysis for empirically successful methods

### Empirical Gaps
Missing experimental evidence or data coverage.
- Benchmarks or datasets not yet evaluated
- Scale gaps (only small-scale studies exist, no large-scale validation)
- Missing real-world deployment studies (only synthetic data or lab settings)
- Incomplete evaluation metrics (accuracy reported but not fairness, efficiency, or robustness)

### Theoretical Gaps
Unexplained phenomena or incomplete frameworks.
- Empirical results without theoretical justification
- Conflicting findings across studies without reconciliation
- Missing convergence proofs, complexity analyses, or formal guarantees
- Incomplete taxonomy or categorization of the problem space

### Temporal Gaps
Studies that need updating or replication with modern methods.
- Foundational results from pre-deep-learning era not re-evaluated
- Benchmarks that have become saturated (need harder variants)
- Claims based on outdated baselines or hardware constraints
- Surveys that are more than 3-5 years old on a fast-moving topic

### Geographic and Demographic Gaps
Missing representation in studied populations and contexts.
- Studies limited to specific languages, regions, or populations
- Lack of cross-cultural validation
- Missing low-resource or underrepresented settings
- Biased training data without mitigation studies

## Output Format

Present gaps in structured format, grouped by category:

```
## Gap Analysis Report

Corpus: 35 papers (2019-2026) on [topic]
Analysis date: 2026-04-09

### Methodological Gaps

[M1] Transformer architectures not applied to time-series anomaly detection
     in industrial IoT contexts
     Evidence: 12/35 papers use LSTM or CNN variants; 0/35 apply transformers
               despite their success in NLP anomaly tasks (Chen et al., 2024).
     Searched: search "transformer time-series anomaly detection industrial IoT"
               (0 relevant of 41 retrieved); citations of Chen et al. 2024
               (depth 1, 63 nodes, none on industrial IoT); references of the
               3 seed surveys (0 transformer + IoT hits). All negative.
     Seed identity: Chen et al. 2024 verified; all 3 surveys verified (axis a).
     Suggested RQ: "Can vision-transformer-inspired architectures improve
                    anomaly detection in multivariate sensor streams?"
     Impact: HIGH (transformers show 15-20% gains in adjacent domains).
     Feasibility: MEDIUM (requires adaptation for streaming data).

[M2] No federated learning approaches despite privacy-sensitive data
     Evidence: All 8 empirical papers use centralized datasets. Li et al.
               (2023) note privacy as a limitation but do not address it
               (faithfulness: supported, layer = full-text).
     Searched: search "federated anomaly detection IoT" (0 relevant of 27);
               citations of Li et al. 2023 (depth 1, 0 federated hits). Negative.
     Suggested RQ: "How does federated anomaly detection perform compared
                    to centralized approaches on distributed IoT networks?"
     Impact: MEDIUM (addresses a real deployment constraint).
     Feasibility: HIGH (federated frameworks are mature).

[M3] (DOWNGRADED) No causal-inference treatment of sensor drift
     Evidence rests on Kumar et al. (2025), which verify-ref returns as
     `unresolvable` (all queried sources clean-negative): the paper cited for
     "no prior causal work" could not be confirmed to exist.
     Action: held out of the ranked list until the reference resolves; do NOT
             present as a gap on this evidence.
```

## Coverage Matrix

Generate a visual summary mapping papers against dimensions:

```
                    | Method A | Method B | Method C | Method D |
Dataset Alpha       |  [3]     |  [1]     |  [0]     |  [2]     |
Dataset Beta        |  [2]     |  [0]     |  [0]     |  [1]     |
Dataset Gamma       |  [5]     |  [3]     |  [1]     |  [0]     |
Real-world deploy   |  [1]     |  [0]     |  [0]     |  [0]     |

[N] = number of papers covering this combination
[0] = GAP: no papers cover this combination
```

## Contradiction Detection

Flag conflicting findings across papers:

```
CONTRADICTION: Effect of data augmentation on model robustness
  - Park et al. (2024): "augmentation improves robustness by 12%"
  - Zhang et al. (2025): "augmentation has no significant effect (p=0.34)"
  Possible explanations: different datasets, different augmentation types,
                         different robustness metrics used.
  Opportunity: controlled study isolating the confounding variables.
```

## Significance Rating

Rate each gap on two dimensions (HIGH / MEDIUM / LOW):
- **Impact:** how much filling this gap would advance the field
- **Feasibility:** whether it can be addressed with existing tools, data, and methods

Prioritize gaps that are HIGH impact + HIGH feasibility. Every ranked gap must carry its negative-evidence trail (step 5); a downgraded gap (its supporting reference refusal-grade or retracted) is held out of the ranked list until the reference resolves. For each gap, the targeted `search` also catches a gap that was recently filled by a preprint.

## Integration with Other Skills

- **literature-search**: provides the corpus and runs the core-backed validation searches
- **paper-drafting**: gaps inform the Introduction (gap statement) and Discussion (future work)
- **citation-management**: `verify-bib` the seed set and ensure all evidence citations are tracked in `library.bib`
- **sota-finder**: complements gap analysis with current performance benchmarks

## References

Load papers from `manuscript/references/library.bib` or from recent literature-search sessions. Use Scite (if available) for smart citation context to understand how papers relate to each other.
