---
name: research-gaps
description: "Systematically identify research gaps from an analysis of the literature that exists. Triggers: find research gaps, identify gaps, what is missing in the literature, unexplored areas, find an underexplored angle, open problems in this field, gap analysis over these papers, where is the gap, research opportunities, what hasn't been studied yet. It derives gaps from papers already collected; inventing candidate ideas without a corpus is brainstorming."
---

# Research Gaps

Systematically analyze a body of literature to identify research gaps, contradictions, and opportunities for novel contributions.

## CRITICAL INTEGRITY RULE
**NEVER fabricate gaps or misrepresent the literature.** Every identified gap must be supported by evidence from actual papers in the analyzed corpus. Cite specific papers when claiming something has or has not been studied. If the corpus is too small to draw reliable conclusions, state the limitation explicitly.

## Workflow

1. **Gather corpus**: collect papers from one or more sources:
   - `manuscript/references/library.bib` (papers already in the bibliography)
   - Recent literature-search results (from prior search sessions)
   - User-provided papers (PDFs or citations the user shares directly)
2. **Extract claims and methods**: for each paper, identify:
   - Research questions addressed
   - Methodology and techniques used
   - Datasets and populations studied
   - Key findings and conclusions
   - Stated limitations and future work suggestions
3. **Cross-reference and map**: build a coverage matrix across the corpus
4. **Identify gaps**: systematically check each gap category
5. **Validate gaps**: run targeted follow-up searches via literature-search to confirm the gap is real (not just missing from the current corpus)
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
     Suggested RQ: "Can vision-transformer-inspired architectures improve
                    anomaly detection in multivariate sensor streams?"
     Impact: HIGH (transformers show 15-20% gains in adjacent domains).
     Feasibility: MEDIUM (requires adaptation for streaming data).

[M2] No federated learning approaches despite privacy-sensitive data
     Evidence: All 8 empirical papers use centralized datasets. Li et al.
               (2023) note privacy as a limitation but do not address it.
     Suggested RQ: "How does federated anomaly detection perform compared
                    to centralized approaches on distributed IoT networks?"
     Impact: MEDIUM (addresses a real deployment constraint).
     Feasibility: HIGH (federated frameworks are mature).
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

Prioritize gaps that are HIGH impact + HIGH feasibility. For each identified gap, optionally trigger a targeted literature-search to verify the gap is genuine and has not been recently filled by a preprint.

## Integration with Other Skills

- **literature-search**: provides the corpus and runs validation searches
- **paper-drafting**: gaps inform the Introduction (gap statement) and Discussion (future work)
- **citation-management**: ensures all evidence citations are tracked in `library.bib`
- **sota-finder**: complements gap analysis with current performance benchmarks

## References

Load papers from `manuscript/references/library.bib` or from recent literature-search sessions. Use Scite (if available) for smart citation context to understand how papers relate to each other.
