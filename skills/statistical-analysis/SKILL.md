---
name: statistical-analysis
description: "Statistical method selection, guidance, and results reporting. Triggers when user says: 'which statistical test', 'analyze data', 'statistical analysis', 'p-value', 'significance test', 'power analysis', 'sample size calculation', 'effect size', 'regression', 'ANOVA', 'compare groups', 'correlation analysis', 'assumption check'. Guides users through choosing the right statistical test, checking assumptions, generating implementation code, and reporting results in APA format. Use this skill whenever the user needs help with quantitative data analysis."
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
