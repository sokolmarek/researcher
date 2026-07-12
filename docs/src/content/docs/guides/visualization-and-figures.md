---
title: "Guide: Visualization & Figures"
description: The five skills that turn results into diagrams, architectures, tables, and charts that compile.
sidebar:
  label: Visualization & Figures
  order: 4
---

Five skills cover the visual half of a paper, from "which figures do I even need" to "compile this table without crying". Every diagram and table is checked with `tectonic` before you see it, and every chart is rendered from the exact code shown. The running scenario throughout is self-supervised pretraining for ECG arrhythmia classification, evaluated on PTB-XL.

Want to see all four figure types rendered rather than described? Jump straight to the [Make figures cookbook](/researcher/cookbook/make-figures/), then come back here for the how and the why.

## visualization

Publication-quality charts, as actual runnable code. Backends cover matplotlib and seaborn (Python), ggplot2 and ggpubr (R, with automatic significance brackets), and pgfplots (native LaTeX). The skill does not just draw what you name: it picks the chart type from the shape of the data, so a trend over a continuous axis becomes a line plot and a comparison of categories becomes a bar chart. In the worked example it plots macro-AUROC against labeled fraction on a log x-axis, keeps a colorblind-safe palette, and draws the self-supervised curves as solid lines above the dashed supervised baselines. Code generation routes to a Sonnet subagent to spare your Opus budget.

**Trigger it:** "Plot X vs Y", "Make a bar chart of these results", "Visualize the results, colorblind-safe".

## tikz-diagrams

Standalone TikZ figures for the things that are not charts: system architectures, flowcharts, pipelines, and timelines. It draws from a library of layout patterns (system architecture, experimental setup, and more) and emits a `.tex` file that compiles on its own to a cropped PDF. The example builds the two-stage pipeline (contrastive pretraining on unlabeled 12-lead ECG, then fine-tuning on PTB-XL) with a dashed arrow carrying the pretrained weights from one stage into the next.

**Trigger it:** "Draw a TikZ diagram of my pipeline", "Make a flowchart of the protocol", "Diagram this architecture, standalone".

## plotneuralnet

The 3D block diagrams that make neural-network architectures look like architectures. This is the PlotNeuralNet aesthetic (github.com/HarisIqbal88/PlotNeuralNet) with one crucial difference: every layer macro, color, and style command is inlined into the file preamble, so it compiles with `tectonic` and no cloned repo. The example renders a 1D-CNN ECG encoder where box height shrinks as the signal is pooled and box width grows with channel count, which is exactly the intuition a reader wants from the picture.

**Trigger it:** "Draw a PlotNeuralNet-style diagram of my CNN", "3D architecture diagram of this network".

## figure-suggestions

Before you draw anything, this skill reads the current `manuscript/` sections and tells you which figures the paper is missing. It reasons per section: a conceptual overview or a research-gap comparison for the introduction, a system architecture or data-pipeline diagram for the methods, and for the results it matches each data scenario to a chart type (categories to a bar chart, a trend to a line plot, a relationship to a scatter plot). Each recommendation comes with a suggested caption, placement, and panel layout, then hands off to the skill that will build it. Think of it as the reviewer who asks "where is the figure showing that?" before the reviewer does.

**Trigger it:** "What figures should this paper have?", "Suggest figures for my results section".

## latex-tables

Booktabs tables that follow the rules editors actually enforce: no vertical rules, only `\toprule`, `\midrule`, and `\bottomrule`. It ingests a CSV, groups rows (supervised versus self-supervised in the example), bolds the best result in each column, and attaches significance markers with a `threeparttable` note explaining the paired t-test behind the asterisks. Give it numbers and it hands back a table that drops into the manuscript and compiles.

**Trigger it:** "Turn this CSV into a booktabs table", "Format a results table, bold the best per column, add significance markers".

## See it in action

The [Make figures cookbook](/researcher/cookbook/make-figures/) shows a TikZ architecture, a PlotNeuralNet encoder, a booktabs table, and a matplotlib chart all rendered from one running scenario. The full source for each, including the compile notes, lives in [`examples/visualization-latex/`](https://github.com/sokolmarek/researcher/tree/main/examples/visualization-latex).
