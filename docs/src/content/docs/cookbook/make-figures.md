---
title: "Cookbook: Make the figures"
description: Diagrams, neural-network architectures, tables, and charts, with rendered previews.
sidebar:
  label: Make figures
  order: 4
---

Figures are where a paper is won or lost, and also where LaTeX chooses violence. Researcher generates four kinds of publication-ready visual, each as source you own plus a rendered preview. Everything below is from the worked examples in the repository, on one running scenario: self-supervised pretraining for ECG arrhythmia classification.

## Architecture diagram (TikZ)

> Make a TikZ diagram of my two-stage pipeline: contrastive pretraining on unlabeled 12-lead ECG, then fine-tuning on PTB-XL. Standalone, colorblind-safe.

The `tikz-diagrams` skill picks a system-architecture layout, groups the two stages, and emits a standalone `.tex` that compiles on its own.

![Two-stage pipeline: self-supervised contrastive pretraining, then fine-tuning on PTB-XL](../../../assets/examples/tikz-architecture.png)

## Neural-network architecture (PlotNeuralNet style)

> Draw a PlotNeuralNet-style 3D diagram of my 1D-CNN ECG encoder. It must compile without the PlotNeuralNet repo.

The `plotneuralnet` skill inlines every layer macro, so the file is self-contained. Box height shrinks as the signal is pooled; width grows with channel count.

![1D-CNN ECG encoder: input, three conv blocks with pooling, global average pooling, dense layer, softmax](../../../assets/examples/plotneuralnet-cnn.png)

## Results table (booktabs)

> Turn this results CSV into a publication-quality table: group by supervised vs self-supervised, bold the best in each column, add significance markers.

The `latex-tables` skill follows booktabs rules (no vertical lines, `\toprule`/`\midrule`/`\bottomrule`), bolds the best per column, and puts significance markers in a table note. Synthetic demonstration data is labeled as such.

![Label-efficiency comparison table across 1%, 10%, and 100% labeled fractions](../../../assets/examples/latex-results-table.png)

## Chart (matplotlib)

> Plot macro-AUROC vs labeled fraction, one line per method, log x-axis, colorblind-safe.

The `visualization` skill chooses a line plot on a log axis (a trend, not a comparison of categories), keeps the same palette as the diagram, and draws the self-supervised methods as solid lines against dashed supervised baselines.

![Label-efficiency line plot: self-supervised curves above supervised, gap largest at 1% labels](../../../assets/examples/label-efficiency-plot.png)

:::tip[Every figure is compile-checked]
Diagrams and tables are compiled with `tectonic` before you ever see them, and charts are rendered from the code shown. If it appears in your docs, it built.
:::

The full source for each of these lives in [`examples/visualization-latex/`](https://github.com/sokolmarek/researcher/tree/main/examples/visualization-latex).
