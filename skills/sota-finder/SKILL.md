---
name: sota-finder
description: "Find and track state-of-the-art results for research tasks and benchmarks, and assemble the SOTA comparison table from what has actually been reported. Triggers: state of the art, SOTA, best results, current best, benchmark results, leaderboard, top performing, leading methods, what beats, performance comparison, build a SOTA comparison table, best reported results on this benchmark. It sources the numbers from papers and leaderboards; typesetting numbers you already have is latex-tables."
---

# SOTA Finder

Discover, compare, and track state-of-the-art results across benchmarks and research tasks, with trend analysis and competitiveness assessment.

## CRITICAL INTEGRITY RULE
**NEVER fabricate benchmark results or performance numbers.** Every metric must come from an actual paper retrieved THIS session and verified through core (see Deterministic backend). Distinguish peer-reviewed results from preprint claims on every row. A source that resolves `inconclusive` is included with that flag, never dropped as fabricated; only `unresolvable`, `mismatch`, and `retracted` rows are withheld. See Row verdicts and withholding.

## Workflow

1. **Parse task definition**: identify the benchmark, dataset, task, and metrics from user input or manuscript context
2. **Retrieve candidate papers this session** through the deterministic backend (see below): core `search` for the task and benchmark, core `get` to normalize a specific paper or leaderboard entry. Every number in the final table must trace to a paper retrieved in THIS session, never to model recall. When core is unavailable the sources degrade to Papers with Code leaderboards, Semantic Scholar, arXiv, and conference proceedings (NeurIPS, ICML, ACL, CVPR) via web search, with Scite/Zotero MCP enrichment where connected.
3. **Verify each source** with core `verify-ref`: read the four-state identity verdict (axis a), the publication status (axis b), and accessibility (axis d) for every candidate row.
4. **Extract results**: for each method, pull metric scores, datasets, and paper details from the retrieved record
5. **Build comparison table**: structured ranking across methods and metrics, each row carrying its identity verdict and a peer-reviewed/preprint flag (see Row verdicts and withholding)
6. **Analyze trends**: how has performance evolved over time
7. **Assess competitiveness**: if user provides their own results, compare against the field

## Deterministic backend

Retrieval and verification route through the `core/` evidence kernel, so every number in a SOTA
table traces to a paper pulled this session and carries a reproducible verdict rather than model
recall. Full command and JSON reference: `references/core-cli.md`.

Invocations this skill uses (each is one line; the base runtime needs no install step):

- Retrieve candidates for a task or benchmark:
  `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<benchmark> <task> state of the art" --json`
  Consume `records[]` (CSL-JSON). Each record's `custom` block carries the source list, citation
  count, OA URL, and venue metadata that set the peer-reviewed/preprint flag.

- Normalize one paper or leaderboard entry (DOI, arXiv ID, or OpenAlex ID):
  `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core get <id> --json`
  Consume `found` and `record`.

- Verify every candidate before it enters the table:
  `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-ref "<doi-or-title>" --json`
  Per entry, consume `verdict` (axis a), `refusal_grade`, `reason`, the `status` block (axis b), the
  `accessibility` block (axis d), and `best_match`. Read `refusal_grade` directly; never re-derive it.

Fallbacks when `uv` or `CLAUDE_PLUGIN_ROOT` is missing: `pip install -e core/` then
`researcher-core ... --json`, or `python -m researcher_core ... --json` from a checkout.

**Degradation path (state it in the output when it applies).** No `uv` or `core/` ->
Scite/Zotero MCP servers where connected -> web search (Papers with Code, Semantic Scholar, arXiv,
conference proceedings). The plugin never hard-fails for want of core (D3). When core is absent no
row can be `verified`: label every verdict `inconclusive` (unverified) and say the table was built
without the kernel.

## Row verdicts and withholding

Every row carries the four-state identity verdict from `verify-ref`, never a boolean:

- **`verified`**: two or more sources confirmed the paper. Included, no identity flag.
- **`inconclusive`**: a source errored, or only one index holds the paper. INCLUDED with an
  `inconclusive` flag, NEVER dropped as fabricated. inconclusive is NOT refusal-grade; withholding a
  real result because one index was slow would accuse an honest author of inventing a number.
- **`unresolvable`** or **`mismatch`**: refusal-grade. Withhold the row from the ranked table and
  list it separately as "could not resolve", so a fabricated or wrong citation contributes no number.

Two more flags ride beside the identity verdict:

- **Publication status (axis b)**: `retracted` or `expression-of-concern` is refusal-grade for the
  number; surface the paper as a flagged, unranked row and never present it as current SOTA.
  `corrected` is noted, not withheld.
- **Peer-reviewed vs preprint**: derived from the record venue and type (an arXiv or preprint source
  flags `preprint`; a journal or proceedings record flags `peer-reviewed`). This flag qualifies a
  row, it never withholds one.

Only `unresolvable`, `mismatch`, and `retracted` withhold a row. `inconclusive` and
`insufficient-passage` (next) never do.

## Verifying the number against the paper

The identity verdict confirms the paper exists; it does not confirm the paper reports the number in
the row. To check the number itself, anchor it on the paper's text with the M2 passage layer:

- `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages index <id> --json` (once per paper)
- `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core faithfulness "<method> reaches <metric> <value> on <benchmark>" --doc <doc-id> --json`

Read the axis (c) verdict: `supported`, `partial`, `contradicted`, or `insufficient-passage`.

- Every verdict NAMES the layer it checked (abstract vs full-text). When OA full text is
  unavailable the verdict is `insufficient-passage`, never `supported` and never "faithful": the
  number is reported-only and stays flagged, not clean.
- `contradicted` is refusal-grade for that number: do not enter it as the paper's result.
- `insufficient-passage` is NEVER refusal-grade. It is an open item ("could not confirm in text"),
  surfaced beside the row, not a reason to drop it.
- Axis (c) is a LEXICAL baseline (BM25 plus token-overlap and polarity heuristics). It can mark an
  overstated number `supported`, so a `supported` verdict on a benchmark claim is a floor, not a
  guarantee. Note that limit when a number is load-bearing.

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

| Rank | Method              | Top-1 Acc | Top-5 Acc | Year | Venue    | Identity     | Type          |
|------|---------------------|-----------|-----------|------|----------|--------------|---------------|
| 1    | Model-X (Zhu et al.)| 92.3%     | 99.1%     | 2026 | CVPR     | verified     | peer-reviewed |
| 2    | Model-Y (Lee et al.)| 91.8%     | 98.9%     | 2025 | NeurIPS  | verified     | peer-reviewed |
| 3    | Model-W (Ito et al.)| 91.6%     | 98.8%     | 2026 | arXiv    | inconclusive | preprint      |
| ...  | ...                 | ...       | ...       | ...  | ...      | ...          | ...           |
| ---  | Your method         | 90.2%     | 98.1%     | 2026 | -        | -            | -             |

Withheld (refusal-grade, not ranked): Model-Q (Sun et al.), verify-ref returned unresolvable.
Sources: core search + verify-ref, replay snapshot <hash>, retrieved 2026-04-09.
Note 1: your method would rank approximately #8 on this benchmark.
Note 2: row 3 is a preprint whose number is insufficient-passage (abstract-only) on axis (c),
reported but not text-confirmed; it is included with a flag, not dropped.
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

Emit `\cite` keys only for rows that passed verification (`verified` or `inconclusive`); withheld
refusal-grade rows contribute no `\cite` and no number. A dangling `\cite` key is exactly what the
commit citation guard blocks.

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

Deterministic retrieval and verification: `core/` via `references/core-cli.md`. Fallback sources:
Papers with Code leaderboards, Semantic Scholar search results, arXiv preprints. Always note the
access date (or the replay snapshot hash) for leaderboard data, as rankings change frequently.
