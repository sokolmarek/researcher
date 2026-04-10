# /design-experiment

Design an experiment or study for your research question.

## Form Fields
- **question** (text, required): Research question or hypothesis to test
- **type** (select: computational/empirical/mixed, default: computational): Experiment type
- **resources** (text, optional): Available resources (GPUs, participants, datasets, budget)

## Behavior
1. Routes to experiment-design skill
2. Asks clarifying questions about variables, constraints, and expected outputs
3. Generates comprehensive experiment design document:
   - Study type, variables, controls
   - Sample size / dataset selection
   - Baseline methods and evaluation metrics
   - Ablation study plan (if computational)
   - Timeline and phases
4. Cross-references with statistical-analysis skill for method recommendations
5. Saves to manuscript/experiment-design.md
