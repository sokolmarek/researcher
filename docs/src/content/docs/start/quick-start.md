---
title: Quick Start
description: From a research idea to a scaffolded manuscript in a few messages.
sidebar:
  order: 3
---

You do not learn Researcher by reading a manual. You learn it by talking to Claude the way you would talk to a very organized, slightly caffeinated collaborator. Here is a first session.

## 1. Start a paper

```
I want to write a paper on self-supervised learning for ECG arrhythmia classification.
```

The plugin scaffolds a `manuscript/` folder (per-section `.tex` files, `config.yaml`, a bibliography, figures and tables folders), asks a couple of clarifying questions, and you are ready.

## 2. Research the topic

```
Do a systematic literature search on self-supervised learning for ECG classification.
/fact-check Self-supervised pretraining can match supervised ECG performance within one percent.
/sota PTB-XL arrhythmia classification
```

Every result carries a real, resolvable citation. The fact-check comes back with a verdict (Supported, Contested, Partially Supported, or Unsupported) and the evidence behind it.

## 3. Design and draft

```
/design-experiment Does contrastive pretraining improve label efficiency on PTB-XL?
/draft-section introduction
Create a diagram of my two-stage pretraining and fine-tuning pipeline.
Turn this results CSV into a booktabs table with the best result in bold.
```

## 4. Review and submit

```
/review-paper
/find-journal --filters Q1, open access
/submit-ready
```

The review runs a five-persona panel with rubric scores. `/submit-ready` refuses to bless a manuscript whose integrity checks have not run.

## 5. Handle revisions

```
/revise R1
Here are the reviewer comments: [paste]
Generate the response to reviewers document.
```

That is the whole loop. For worked, end-to-end recipes with real output, open the [Cookbook](/researcher/cookbook/write-a-paper/).
