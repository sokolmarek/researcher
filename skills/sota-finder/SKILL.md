---
name: sota-finder
description: "Find and track state-of-the-art results for research tasks and benchmarks. Triggers: state of the art, SOTA, best results, current best, benchmark results, leaderboard, top performing, leading methods, what beats, performance comparison."
---

# SOTA Finder

Discover, compare, and track state-of-the-art results across benchmarks and research tasks, with trend analysis and competitiveness assessment.

## CRITICAL INTEGRITY RULE
**NEVER fabricate benchmark results or performance numbers.** Every metric must come from an actual paper, leaderboard, or reproducible source. If results cannot be verified, mark them as "unverified" and cite the source. Clearly distinguish between peer-reviewed results and preprint claims.

## Workflow

1. **Parse task definition**: identify the benchmark, dataset, task, and metrics from user input or manuscript context
2. **Search SOTA sources** via web search and available connectors:
   - Papers with Code (paperswithcode.com), for benchmark leaderboards
   - Semantic Scholar (via API), for recent papers with results on the task
   - arXiv (via API), for latest preprints claiming new SOTA
   - Conference proceedings (NeurIPS, ICML, ACL, CVPR, etc.), for peer-reviewed results
   - Scite (if MCP connector available), for citation context around benchmark papers
3. **Extract results**: for each method, pull metric scores, datasets, and paper details
4. **Build comparison table**: structured ranking across methods and metrics
5. **Analyze trends**: how has performance evolved over time
6. **Assess competitiveness**: if user provides their own results, compare against the field

## Input Modes

### By Task/Benchmark
User specifies a known task or benchmark:
- "SOTA on ImageNet classification"
- "Best results on SQuAD 2.0"
- "State of the art for machine translation EN-DE"

### By Dataset
User specifies a dataset name and the skill identifies all tasks evaluated on it.

### From Manuscript
Read the evaluation section of the current manuscript to identify which benchmarks and metrics are being reported, then search for SOTA on each.

## Result Format

### Leaderboard Table

```
## SOTA: ImageNet Top-1 Classification Accuracy

| Rank | Method              | Top-1 Acc | Top-5 Acc | Year | Venue    | Code |
|------|---------------------|-----------|-----------|------|----------|------|
| 1    | Model-X (Zhu et al.)| 92.3%     | 99.1%     | 2026 | CVPR     | Yes  |
| 2    | Model-Y (Lee et al.)| 91.8%     | 98.9%     | 2025 | NeurIPS  | Yes  |
| 3    | Model-Z (Kim et al.)| 91.5%     | 98.7%     | 2025 | ICLR     | No   |
| ...  | ...                 | ...       | ...       | ...  | ...      | ...  |
| ---  | Your method         | 90.2%     | 98.1%     | 2026 | -        | -    |

Sources: Papers with Code leaderboard, accessed 2026-04-09.
Note: Your method would rank approximately #8 on this benchmark.
```

### Method Detail Card

For any method the user wants to examine more closely:

```
Method:      Model-X
Paper:       "Scaling Vision Transformers Beyond 10B" (Zhu et al., 2026)
Venue:       CVPR 2026 (Oral)
DOI:         10.1109/CVPR.2026.12345
Results:     ImageNet Top-1: 92.3% | Top-5: 99.1%
             ImageNet-V2: 84.1% | ImageNet-R: 78.5%
Parameters:  10.2B
FLOPs:       1.8T per inference
Code:        https://github.com/example/model-x (PyTorch)
Key Ideas:   Sparse mixture-of-experts in ViT backbone; progressive
             resolution training; synthetic data augmentation.
```

## Trend Analysis

Track how SOTA has progressed over time for a given benchmark:

```
## ImageNet Top-1 Accuracy Timeline

2012: 63.3%  AlexNet           (Krizhevsky et al.)    [CNN era begins]
2014: 74.8%  VGGNet            (Simonyan & Zisserman)
2015: 80.2%  ResNet-152        (He et al.)            [residual connections]
2017: 82.7%  SENet             (Hu et al.)
2019: 84.4%  EfficientNet-B7   (Tan & Le)
2020: 87.1%  ViT-H/14          (Dosovitskiy et al.)   [transformer era]
2023: 90.2%  Model-A           (Author et al.)
2026: 92.3%  Model-X           (Zhu et al.)           [current SOTA]

Trend: +0.7%/year average improvement (2020-2026), slowing from +1.2%/year (2015-2020).
Dominant paradigm shift: CNN -> Transformer (2020), now MoE-Transformer (2024+).
```

Also identify leading research groups driving progress on the task (by number of SOTA entries in recent years).

## Competitiveness Assessment

When the user provides their own results:

1. **Rank placement**: where their results would fall on the leaderboard
2. **Gap analysis**: how far from current SOTA (absolute and relative)
3. **Competitive window**: which methods they outperform
4. **Novelty angle**: if not SOTA, suggest positioning strategies: efficiency advantage, simplicity, domain-specific strengths, or theoretical contribution

## LaTeX Output

Generate publication-ready comparison tables:

```latex
\begin{table}[t]
\centering
\caption{Comparison with state-of-the-art methods on ImageNet.
         Best results in \textbf{bold}, second best \underline{underlined}.}
\label{tab:sota-comparison}
\begin{tabular}{lccc}
\toprule
Method & Top-1 (\%) & Params (M) & FLOPs (G) \\
\midrule
Model-X \cite{zhu2026}    & \textbf{92.3} & 10,200 & 1,800 \\
Model-Y \cite{lee2025}    & \underline{91.8} & 5,400 & 980 \\
Ours                       & 90.2 & \textbf{200} & \textbf{45} \\
\bottomrule
\end{tabular}
\end{table}
```

## Multi-Benchmark Comparison

When the user evaluates on multiple benchmarks, generate a unified view:

```
| Method | Dataset A | Dataset B | Dataset C | Avg Rank |
|--------|-----------|-----------|-----------|----------|
| SOTA-1 | **95.2**  | 88.1      | **91.3**  | 1.3      |
| SOTA-2 | 94.8      | **89.0**  | 90.7      | 1.7      |
| Ours   | 93.1      | 87.5      | 90.1      | 3.0      |
```

## Integration with Other Skills

- **literature-search**: retrieves papers reporting benchmark results
- **latex-tables**: generates formatted comparison tables for the manuscript
- **research-gaps**: SOTA analysis reveals which approaches are unexplored
- **paper-drafting**: SOTA tables integrate directly into Related Work and Results sections
- **citation-management**: auto-adds cited SOTA papers to `library.bib`

## References

Primary sources: Papers with Code leaderboards, Semantic Scholar search results, arXiv preprints. Always note the access date for leaderboard data, as rankings change frequently.
