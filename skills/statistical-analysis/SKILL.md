---
name: statistical-analysis
description: "Statistical method selection, guidance, and results reporting. Triggers when user says: 'which statistical test', 'analyze data', 'statistical analysis', 'p-value', 'significance test', 'power analysis', 'sample size calculation', 'effect size', 'regression', 'ANOVA', 'compare groups', 'correlation analysis', 'assumption check', 'meta-analysis', 'pool effect sizes', 'pooled effect', 'forest plot', 'funnel plot', 'heterogeneity', 'random-effects model', 'I-squared'. Guides users through choosing the right statistical test, checking assumptions, generating implementation code, reporting results in APA format, and running the meta-analysis synthesis step of a systematic review. Use this skill whenever the user needs help with quantitative data analysis or pooling effect sizes across studies."
---

# Statistical Analysis

Statistical method selection, assumption verification, implementation, and results reporting.

## Method Selection Wizard

Guide the user through a decision tree to select the appropriate test.

### Step 1: Research Question Type

| Question | Direction |
|----------|-----------|
| Is there a difference between groups? | → Comparison tests |
| Is there a relationship between variables? | → Correlation / regression |
| Can we predict an outcome? | → Regression / classification |
| Does this sample differ from a known value? | → One-sample tests |
| Is there an association between categories? | → Chi-square / Fisher's exact |

### Step 2: Data Characteristics

Determine based on the data:
- **Scale of measurement:** nominal, ordinal, interval, ratio
- **Number of groups:** 1, 2, or 3+
- **Paired or independent:** same subjects measured twice vs different subjects
- **Sample size:** small (< 30) vs large
- **Distribution:** normal vs non-normal (determines parametric vs non-parametric)

### Step 3: Test Selection Matrix

| Scenario | Parametric | Non-parametric |
|----------|-----------|----------------|
| 2 independent groups | Independent t-test | Mann-Whitney U |
| 2 paired groups | Paired t-test | Wilcoxon signed-rank |
| 3+ independent groups | One-way ANOVA | Kruskal-Wallis |
| 3+ paired groups | Repeated measures ANOVA | Friedman test |
| 2 continuous variables | Pearson correlation | Spearman correlation |
| Predict continuous outcome | Linear regression | N/A |
| Predict binary outcome | Logistic regression | N/A |
| 2 categorical variables | N/A | Chi-square / Fisher's exact |
| Time-to-event | Cox proportional hazards | Log-rank test |

### Effect Size for Each Test

| Test | Effect Size | Small | Medium | Large |
|------|------------|-------|--------|-------|
| t-test | Cohen's d | 0.2 | 0.5 | 0.8 |
| ANOVA | Eta-squared (η²) | 0.01 | 0.06 | 0.14 |
| Correlation | r | 0.1 | 0.3 | 0.5 |
| Chi-square | Cramer's V | 0.1 | 0.3 | 0.5 |

### Multiple Comparison Corrections

When running multiple tests, recommend the appropriate correction:
- **Bonferroni:** conservative, controls family-wise error rate
- **Holm-Bonferroni:** step-down, less conservative than Bonferroni
- **Benjamini-Hochberg (FDR):** controls false discovery rate, preferred for exploratory
- **Tukey HSD:** post-hoc for ANOVA pairwise comparisons
- **Dunnett:** compare multiple treatments to a single control

## Assumption Checking

Guide the user through verifying each assumption for the selected test.

### Normality
- Visual: Q-Q plot, histogram
- Formal: Shapiro-Wilk (n < 50), Kolmogorov-Smirnov (n ≥ 50)
- Rule of thumb: with n > 30, parametric tests are robust to mild non-normality

### Homogeneity of Variance
- Levene's test (robust to non-normality)
- If violated: use Welch's t-test or Welch's ANOVA

### Independence
- Study design question, not a statistical test
- Flag if repeated measures, clustered data, or time-series

### Linearity (for regression)
- Residual plots (residuals vs fitted values)
- Component-plus-residual plots for each predictor

## Implementation Code

Generate ready-to-run code in the user's preferred language.

### Python (default)
```python
# Libraries: scipy.stats, statsmodels, pingouin, scikit-posthocs
# Generate complete analysis script with:
# - Data loading
# - Assumption checks (with plots)
# - Test execution
# - Effect size calculation
# - Results summary
```

### R
```r
# Libraries: base R, tidyverse, ggpubr, rstatix, effectsize
# Same structure as Python output
```

### MATLAB and Julia
Provide equivalent implementations on request.

Always include:
- Comments explaining each step
- Assumption check code before the main test
- Effect size computation alongside p-values
- Visualization of results

## Results Reporting (APA Format)

Generate publication-ready results text from statistical output.

### Templates

**t-test:**
> An independent-samples t-test revealed a [significant/non-significant] difference in [DV] between [group 1] (M = X.XX, SD = X.XX) and [group 2] (M = X.XX, SD = X.XX), t(df) = X.XX, p = .XXX, d = X.XX [95% CI: X.XX, X.XX].

**ANOVA:**
> A one-way ANOVA showed a [significant/non-significant] effect of [IV] on [DV], F(df1, df2) = X.XX, p = .XXX, η² = .XX. Post-hoc comparisons using Tukey's HSD indicated...

**Correlation:**
> There was a [strong/moderate/weak] [positive/negative] correlation between [var1] and [var2], r(df) = .XX, p = .XXX [95% CI: .XX, .XX].

**Chi-square:**
> A chi-square test of independence showed a [significant/non-significant] association between [var1] and [var2], χ²(df) = X.XX, p = .XXX, V = .XX.

## Power Analysis

Calculate required sample size or achieved power:
- Inputs: effect size, alpha, power (or sample size), number of groups
- Tools: G*Power formulas, or generate code using `statsmodels.stats.power` (Python) / `pwr` package (R)
- Always report the assumptions behind the calculation

## Meta-analysis

The synthesis step of a systematic review (see the systematic-review skill for the surrounding
workflow). Meta-analysis pools effect sizes across the included studies; run it only when clinical
and methodological homogeneity support pooling, otherwise synthesize narratively and say why.

### Inputs: the typed effect-size columns

Effect sizes arrive from the extraction-tables skill as typed columns, one row per study or per
contrast: point estimate, its variance or standard error (or the confidence interval bounds), the
n per arm, and the metric definition (RR, OR, Hedges g / SMD, mean difference, hazard ratio). Only
these typed, extracted values are pooled. A cell the extraction step marked "not reported" or
`insufficient-passage` is EXCLUDED from the pool, never imputed silently; if imputation is used
(for example computing SE from a CI, or a correlation for a change score), state the method
explicitly in the manuscript.

### The model split (who does what)

- Claude, on the session model, makes the judgments: pick the effect measure, choose fixed versus
  random effects, choose the heterogeneity estimator (DerSimonian-Laird, or REML for random
  effects), decide the small-study-effects assessment, and explain each choice. Reasoning stays in
  the session.
- The analysis CODE is not written here in prose. Generate it by invoking the implementation skill,
  which carries `context: fork` + `agent: code-agent` frontmatter and forks into the Sonnet-pinned
  code-agent (D1 model split). Prose cannot switch models; that frontmatter does.

### The generated script

The code-agent produces a Python script (for example `scripts/meta_analysis.py`) with pinned
dependencies in a per-review environment (a committed `requirements.txt` or lockfile). The script:

- reads the committed extraction table (the typed columns above), never re-typed numbers;
- computes the pooled effect and its confidence interval, the heterogeneity statistics
  (Cochran's Q, I-squared with its CI, tau-squared), and the prediction interval;
- renders the forest plot and the funnel plot to files, and runs a small-study-effects test
  (for example Egger's) when at least 10 studies are pooled;
- writes every pooled number to a machine-readable artifact (for example
  `figures/pooled-estimates.json`) that the manuscript and plots read from;
- is deterministic: pin any RNG seed and pin the dependency versions, so a rerun reproduces the
  estimates byte-for-byte.

### No pooled number is hand-typed (compile binding, D18)

Commit the script alongside its inputs and outputs, then bind every pooled number to it so the M3
compile gate can verify it was not altered by hand:

- Record an experiment-run manifest (validated against `core/schemas/experiment-manifest.schema.json`)
  carrying `code_commit`, `dirty_worktree`, `data_hashes` (the input extraction-table hash),
  `environment_lockfile_hash`, `metric_definitions`, and `artifact_hashes` (the generated
  `pooled-estimates.json` and plot files), with a caller-supplied `ts` per D19.
- Add one INTERNAL evidence edge per pooled-number claim
  (`{claim_id, target_kind: "internal", manifest_hash}`, per `evidence-edge.schema.json`) into the
  manuscript lineage graph (`manuscript/lineage/graph.jsonl`), pointing at that manifest hash.
- A hand edit to a pooled estimate, CI, I-squared, or tau-squared changes the artifact content
  without updating the manifest, so `researcher compile` reports **C002** (altered number) and the
  gate fails. **C006** (artifact-code drift) fires if the run's commit is not an ancestor of HEAD or
  the worktree was dirty at run time. This is what makes "no pooled number is hand-typed" enforceable
  rather than a promise.

### Reporting

Report, in APA / PRISMA 2020 wording: the pooled estimate with its 95% CI, the number of studies
and participants, the model and estimator named, I-squared with its CI, tau-squared, and the
prediction interval. Interpret I-squared with caveats (roughly 25 / 50 / 75 percent as low /
moderate / high, but read alongside the CI and the number of studies, never mechanically). Feed
funnel-plot asymmetry into the GRADE publication-bias domain (see the RoB 2 / GRADE worksheets).
The forest plot is a generated figure; the visualization skill may restyle it via presets, which
change only colors, fonts, and line widths, never the values.

### Deterministic backend

Compile-time verification of the pooled numbers (D3: this needs `uv` and `core/`):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core \
    compile --manuscript manuscript/ --lineage manuscript/lineage/graph.jsonl --json
```

Read the `--json` report's diagnostics list, not the exit code alone: a `C002` on the meta-analysis
artifact means a pooled number was altered after generation; a `C006` means the run drifted from
HEAD. Exit 1 is a failing gate (refusal-grade only on C001 through C006 on clean evidence); an
`inconclusive` or `insufficient-passage` line item is an open item and NEVER fails the gate (D9,
D11). Fallbacks: `pip install -e core/` then `researcher-core compile ...`, or
`python -m researcher_core compile ...` from a checkout.

Degradation path when `uv` and `core/` are absent: still generate the pinned-dependency script,
still commit the script with its inputs and outputs, but state plainly in the manuscript that the
pooled numbers are NOT compile-verified in this environment. Do not claim the D18 binding you cannot
produce, and never hand-type a pooled number to fill the gap.

### Integrity (meta-analysis)

- Never hand-type or "adjust" a pooled estimate, CI, I-squared, or tau-squared: every synthesis
  number is script-generated and, where the kernel is present, compile-bound.
- Pool only real, extracted effect sizes; excluded or absent cells are stated, never imputed
  silently.
- The four axes still bind the included studies: surface any `retracted` (axis b) or `contradicted`
  (axis c) source; `inconclusive` and `insufficient-passage` are open items for human review, never
  treated as fabrication and never refusal-grade.

## Common Pitfalls: Actively Warn

- **p-hacking:** running many tests and reporting only significant ones
- **HARKing:** hypothesizing after results are known
- **Multiple testing without correction:** inflated Type I error
- **Confusing significance with importance:** report effect sizes, not just p-values
- **Small sample overinterpretation:** wide confidence intervals mean low precision
- **Misusing parametric tests on ordinal/non-normal data**
- **Correlation ≠ causation** (always flag in observational studies)

## Integration

- Receives study design from **experiment-design** skill
- Feeds APA-formatted results into **paper-drafting** skill (results section)
- Implementation code integrates with **implementation** skill
- Power analysis feeds back into **experiment-design** for sample sizing

## Integrity constraints

- Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it; never invent a DOI, author list, venue, or year.
- Never invent data: only user-provided or actually computed numbers may appear as results. Anything illustrative must be labeled "(synthetic, for demonstration)".
- Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).

Canonical copy: `references/integrity-constraints.md`.
