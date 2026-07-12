---
title: "Guide: Planning & Design"
description: The four skills that turn a hunch into a rigorous, reproducible study you can actually write up.
sidebar:
  label: Planning & Design
  order: 2
---

Four skills carry you from a 2 a.m. hunch to a scaffolded manuscript: sharpen the question, design the experiment, pick the right statistics, and build the project folder. Together they make sure that by the time you start writing, the study is defensible rather than merely finished.

The running example throughout is self-supervised learning for ECG arrhythmia classification, evaluated on PTB-XL.

## brainstorming

Socratic refinement, not a brainstorm dump. It takes a vague hunch ("maybe contrastive pretraining helps with ECG") and interrogates it: what population, what comparison, what outcome, what would falsify it? You leave with a precise, answerable research question and a scope you can actually defend, plus a `brainstorm-log.md` that records how you got there.

For the running example, "SSL is good for ECG" becomes something testable: does contrastive pretraining on unlabeled ECG improve macro-AUC for multi-label arrhythmia classification on PTB-XL under a limited-label regime, compared to fully supervised training from scratch?

**Trigger it:** "Help me turn this idea into a research question", "`/brainstorm`".

## experiment-design

Turns the question into a protocol before you burn a week of GPU time. It works through controls, sample sizes, and a power analysis so you know the study can detect the effect you care about, then plans the ablations that isolate which component actually did the work.

For the ECG example, that means fixing the PTB-XL train/test folds, defining the supervised-from-scratch baseline as the control, planning label-fraction sweeps (1 percent, 10 percent, 100 percent), and listing the ablations (augmentation choice, projection-head depth, pretraining corpus) so a reviewer cannot ask "but did you check..." about something you skipped.

**Trigger it:** "`/design-experiment`", "Design the experiment for this study".

## statistical-analysis

Chooses the test that matches your data and your design, rather than defaulting to whatever you ran last time. It checks assumptions (normality, homoscedasticity, independence) before committing, flags when a nonparametric or corrected test is the honest choice, and generates the analysis in Python, R, or MATLAB. Results come back formatted for APA reporting, effect sizes and confidence intervals included.

For comparing macro-AUC across seeds and label fractions, it will steer you toward paired comparisons with multiple-comparison correction rather than a pile of unadjusted t-tests, and it reports on the actual numbers you produce. It will not invent a p-value.

**Trigger it:** "Which statistical test should I use?", "Run the stats and report them APA style".

## manuscript-setup

Scaffolds the whole project so you are not fighting your directory structure at submission time. It builds a `manuscript/` folder with `main.tex` and per-section files for LaTeX, or `sections/*.md` plus a `build-docx.js` for Word, along with `config.yaml` (title, authors, journal, citation style), `terminology.yaml` for consistent naming, and a `references/library.bib`.

Point it at PTB-XL work and you get an IMRaD skeleton with the sections stubbed, the bibliography wired up, and figure and table folders waiting, so drafting starts on prose instead of boilerplate.

**Trigger it:** "`/new-manuscript`", "Set up the manuscript project".

## See it in action

Once the study is designed and scaffolded, the [write-a-paper recipe](/researcher/cookbook/write-a-paper/) takes it through drafting, review, and submission, and the [Research & Discovery guide](/researcher/guides/research-and-discovery/) covers the searching and fact-checking that feed your introduction.
