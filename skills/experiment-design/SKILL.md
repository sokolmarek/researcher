---
name: experiment-design
description: "Design experiments and studies from research questions. Triggers when user says: 'design experiment', 'study design', 'experimental setup', 'how should I test this', 'plan my study', 'ablation study', 'baseline comparison', 'research protocol', 'pilot study', 'sample size', 'how many participants do I need'. Generates comprehensive experiment designs including variables, sample sizing, protocols, and reproducibility checklists. Use this skill to plan how a hypothesis will be tested before any data is collected; choosing a test for data you have already collected is statistical-analysis."
---

# Experiment Design

Comprehensive experiment and study design from research questions to execution plans.

## Workflow

1. **Gather inputs**: research question, hypotheses, available resources, constraints
2. **Recommend study type**: match question to appropriate research design
3. **Specify variables**: identify all variables and their roles
4. **Plan sampling**: determine sample size, selection, and randomization
5. **Define protocol**: step-by-step data collection and analysis plan
6. **Check feasibility**: resource estimation and timeline
7. **Output design document**: structured experiment plan

## Study Type Selection

Match the research question to the most appropriate design:

| Question Type | Recommended Design |
|--------------|-------------------|
| Causal effect of intervention | Randomized Controlled Trial (RCT) |
| Causal effect, no randomization possible | Quasi-experimental (DiD, regression discontinuity) |
| Relationship between variables | Observational (cross-sectional, longitudinal, cohort) |
| Prevalence or distribution | Survey / descriptive study |
| Algorithm performance | Computational experiment (benchmark evaluation) |
| System behavior under conditions | Simulation study |
| User experience or usability | User study (within/between subjects) |
| Rare phenomena or deep context | Case study / qualitative design |

## Variable Specification

For every experiment, explicitly define:

- **Independent variables (IV):** what is manipulated or compared
- **Dependent variables (DV):** what is measured as outcome
- **Controlled variables:** what is held constant across conditions
- **Confounding variables:** what might produce spurious relationships
- **Mediating/moderating variables:** what might explain or modify the effect

## Sample Size & Power

- Estimate required sample size given:
  - Expected effect size (Cohen's d, odds ratio, eta-squared)
  - Significance level (alpha, default 0.05)
  - Desired power (default 0.80, recommend 0.90 for confirmatory)
  - Number of groups and measurements
- Provide rationale for effect size estimate (prior literature or pilot data)
- Flag when requested sample exceeds available resources
- Cross-reference with **statistical-analysis** skill for test-specific formulas

## Randomization Strategy

Select and document the randomization approach:
- Simple randomization (coin flip)
- Stratified randomization (balance key covariates)
- Block randomization (equal group sizes)
- Cluster randomization (groups of participants)
- For computational: random seeds, cross-validation folds, dataset splits

## Computational Experiment Design

For CS, ML, and computational science experiments:

### Dataset Selection
- Recommend established benchmarks relevant to the task
- Specify train/validation/test splits with rationale
- Address class imbalance, data leakage, distribution shift
- Document preprocessing pipeline completely

### Baselines
- Identify appropriate baseline methods:
  - Naive baselines (random, majority class, mean prediction)
  - Classical methods (established algorithms)
  - State-of-the-art methods (recent top performers)
  - Ablation variants (proposed method minus components)
- Justify each baseline's inclusion

### Evaluation Metrics
- Primary metric (what determines success)
- Secondary metrics (additional perspectives on performance)
- Justify metric choice relative to research question
- Report confidence intervals or standard deviations, not just point estimates

### Ablation Study Design
- Identify components to ablate (one at a time)
- Design factorial experiments for interaction effects if needed
- Specify which ablations are essential vs. supplementary

### Hyperparameter Search
- Search strategy: grid, random, Bayesian optimization
- Search budget and early stopping criteria
- Report all hyperparameters and ranges searched
- Use separate validation set (never tune on test)

### Compute Budget
- Estimate GPU/CPU hours per experiment
- Total budget for all runs (main + ablations + hyperparameter search)
- Recommend compute-efficient alternatives if budget is tight

## Protocol Template

```markdown
## Experiment Protocol

### Objective
[What this experiment tests]

### Hypothesis
[Specific, falsifiable prediction]

### Design
- Type: [study design]
- Groups: [experimental vs control, conditions]
- Duration: [timeline]

### Participants / Data
- Source: [where subjects/data come from]
- Size: N = [sample size] (power analysis: d=[effect], alpha=[α], power=[1-β])
- Inclusion criteria: [who/what qualifies]
- Exclusion criteria: [who/what is excluded]

### Procedure
1. [Step-by-step protocol]
2. ...

### Measurements
| Variable | Instrument | Scale | Timing |
|----------|-----------|-------|--------|
| DV1 | ... | ... | ... |

### Analysis Plan
- Primary analysis: [statistical test]
- Secondary analyses: [exploratory analyses]
- Multiple comparison correction: [method]

### Reproducibility
- [ ] Random seed documented
- [ ] Environment specification (requirements.txt / Dockerfile)
- [ ] Data preprocessing steps scripted
- [ ] Analysis code version-controlled
- [ ] Raw data preserved separately from processed data
```

## Pilot Study Recommendations

Always recommend a pilot study when:
- The measurement instrument is new or adapted
- The effect size is unknown
- The procedure is complex or untested
- Participant burden is uncertain

Pilot study output: revised effect size estimate, protocol refinements, feasibility assessment.

## Output Formats

- **Experiment design document:** `manuscript/experiment-design.md`
- **Methods section skeleton:** LaTeX fragment for `methods.tex` with placeholders
- **Reproducibility checklist:** standalone checklist file

## Integration

- Receives refined questions and hypotheses from **brainstorming** skill
- Cross-references **statistical-analysis** skill for test selection and power analysis
- Feeds into **paper-drafting** skill (methods section content)
- Feeds into **implementation** skill (experiment scripts and configurations)
- Uses **code-analysis** skill to verify implementation matches design
