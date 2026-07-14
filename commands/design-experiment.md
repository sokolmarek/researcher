---
description: Design a comprehensive experiment or study plan for a given research question
argument-hint: "<research question>"
---

# /researcher:design-experiment

Design an experiment or study for your research question.

## Inputs (gathered conversationally)
- Question: the research question or hypothesis to test. Required; state it in your message.
- Type: computational, empirical, or mixed (default: computational). State it in your message or Claude asks.
- Resources: available resources (GPUs, participants, datasets, budget), optional. State it in your message or Claude asks.

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
