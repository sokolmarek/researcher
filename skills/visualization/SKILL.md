---
name: visualization
description: "Generate publication-quality data visualizations with matplotlib, seaborn, ggplot2, pgfplots. Triggers: plot data, create chart, visualize results, make figure, bar chart, scatter plot, heatmap, line plot, plot the accuracy curve, plot the loss curve over training epochs, publication plot, statistical plot, data visualization. It writes the plotting code and renders the figure from data you already have; choosing which figure a section needs is figure-suggestions."
---

# Visualization

Publication-quality data visualization with multiple plotting libraries. Generates actual runnable code that produces journal-ready figures.

## Model Routing

This skill runs in the main session: it needs the conversation's data context. For heavy plotting code, you may launch the `visualization-agent` subagent (pinned to Sonnet in its frontmatter) via the Task/Agent tool; the skill itself does not switch models.

## Supported Libraries

### matplotlib (Python)
General-purpose plotting. Use for maximum control over every visual element.
- Line plots, bar charts, scatter plots, histograms
- Heatmaps, contour plots, 3D surface plots
- Error bars, annotations, inset axes
- Multi-panel figures with `plt.subplots()`

### seaborn (Python)
Statistical visualization built on matplotlib. Use for statistical plots with minimal code.
- Distribution plots: KDE, violin, box, swarm, strip
- Relationship plots: pair plots, joint plots, regression plots
- Categorical plots: bar with CI, count, point
- Heatmaps with clustering (clustermap)

### ggplot2 (R)
Grammar of graphics. Use when the user works in R or wants faceted figures.
- All standard geoms: `geom_point`, `geom_line`, `geom_bar`, `geom_boxplot`
- Faceting: `facet_wrap`, `facet_grid`
- Themes: `theme_minimal`, `theme_classic`, `theme_bw`
- Scale customization: colors, axes, legends

### ggpubr (R)
Publication-ready statistical plots with annotations. Use for figures requiring significance brackets.
- `ggboxplot`, `ggbarplot`, `ggscatter`, `ggviolin` with stat comparisons
- Automatic p-value brackets (`stat_compare_means`)
- `ggarrange` for multi-panel layouts
- Ready-made publication themes

### plotly (Python / R)
Interactive HTML plots. Use for supplementary materials or web-based presentations.
- Interactive hover, zoom, pan
- 3D scatter and surface plots
- Animated transitions
- Export as self-contained HTML

### pgfplots (LaTeX)
Native LaTeX plotting. Use when figures must compile within the manuscript `.tex` file.
- Integrates directly with LaTeX math notation
- Consistent fonts with document body
- `addplot` from data files or inline tables
- Grouped bar charts, error bars, fill between

## Smart Chart Selection

When the user provides data without specifying chart type, select based on data characteristics:

| Data Type | Recommended Chart |
|-----------|-------------------|
| One numeric variable | Histogram, KDE, box plot |
| Two numeric variables | Scatter plot, line plot (if ordered) |
| One categorical + one numeric | Bar chart, box plot, violin plot |
| Two categorical | Heatmap, grouped bar chart |
| Time series | Line plot with date axis |
| Correlation matrix | Heatmap with annotations |
| Distribution comparison | Violin plot, ridge plot, overlaid KDE |
| Part-of-whole | Stacked bar chart (avoid pie charts in academic work) |
| Spatial data | Contour plot, 2D density, map |
| Model performance across conditions | Grouped bar chart with error bars |

## Publication Styling

### Journal Requirements
Apply journal-specific figure standards:
- **DPI:** 300 minimum for raster (PNG), vector preferred (PDF/SVG/EPS)
- **Width:** Single column (3.3 in / 84 mm) or double column (6.7 in / 170 mm)
- **Fonts:** Match manuscript font, minimum 6pt for labels
- **Color:** Use colorblind-safe palettes by default

### Colorblind-Safe Palettes
Default to these palettes unless the user specifies otherwise:
- **Categorical:** Wong palette (`#E69F00`, `#56B4E9`, `#009E73`, `#F0E442`, `#0072B2`, `#D55E00`, `#CC79A7`)
- **Sequential:** Viridis, Inferno, Plasma
- **Diverging:** Coolwarm, RdBu (reversed if needed)
- Always verify grayscale legibility for print journals

### Standard Style Template (matplotlib)
```python
import matplotlib.pyplot as plt
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
})
```

## Style Presets

Named figure style presets: `default`, `nature`, `ieee`. Each preset's rcParams and sizing rules are defined once in `references/figure-styles.md`; load that file rather than duplicating values here.

Presets resolve in one precedence order, highest first: **explicit `Style:` line > trigger phrase > journal inference from `manuscript/config.yaml` > `default`**.

### `Style:` line (accepted input)
The invocation may carry an explicit `Style:` line, which outranks every other selector:

```
Plot macro-AUROC against labeled fraction, one line per method.
Style: nature
```

- `Style: nature`, `Style: ieee`: apply that preset.
- `Style: default`, or no `Style:` line at all: the no-op path, exactly the output this skill produces today. An omitted `Style:` line is never an error.
- Any other value: do not guess and do not improvise a preset. Say it is not defined, list the presets that are (`default`, `nature`, `ieee`), and ask which to use.

### Trigger phrases
With no `Style:` line, apply a preset when the user asks for it in prose, for example:
- "nature style", "in Nature format", "for submission to Nature" -> `nature`
- "IEEE two-column figure" -> `ieee`

### Journal inference
If the user gives neither a `Style:` line nor a trigger phrase, but `manuscript/config.yaml` specifies a target journal, map that journal to its preset (Nature-family journals -> `nature`, IEEE venues -> `ieee`).

### Default rule
If nothing above resolves, use the `default` preset. This is the current behavior, unchanged. Always state which preset was applied and why.

### Integrity
Presets restyle only: fonts, sizes, colors, dimensions, DPI. They never change data values or synthetic-data labels.

## Statistical Annotations

- **Significance brackets:** p-value brackets between groups (*, **, ***, ns)
- **Correlation coefficients:** Pearson r or Spearman rho on scatter plots
- **Regression lines:** With confidence bands (95% CI shading)
- **Error bars:** Standard error (SE), standard deviation (SD), or confidence interval (CI): always label which
- **Effect sizes:** Cohen's d or eta-squared annotations where appropriate

## Data Input

### From CSV
```python
import pandas as pd
df = pd.read_csv('data/results.csv')
```

### From JSON
```python
df = pd.read_json('data/results.json')
```

### Inline Specification
User provides data directly in the prompt. Parse into a DataFrame or table structure.

### From manuscript tables
Extract data from existing LaTeX tables in `manuscript/tables/` and visualize.

## Multi-Panel Figures

### matplotlib/seaborn
```python
fig, axes = plt.subplots(2, 2, figsize=(6.7, 5))
# Label panels: (a), (b), (c), (d)
for ax, label in zip(axes.flat, 'abcd'):
    ax.set_title(f'({label})', loc='left', fontweight='bold')
```

### ggplot2/ggpubr
```r
library(ggpubr)
ggarrange(p1, p2, p3, p4, labels = c("a", "b", "c", "d"), ncol = 2, nrow = 2)
```

Panel labels follow journal convention: lowercase letters in parentheses, bold, top-left.

## Export Formats

| Format | Use Case | Command (matplotlib) |
|--------|----------|---------------------|
| PDF | Vector, LaTeX inclusion | `plt.savefig('fig.pdf')` |
| PNG | Raster, Word inclusion | `plt.savefig('fig.png', dpi=300)` |
| SVG | Web, scalable | `plt.savefig('fig.svg')` |
| EPS | Legacy journal requirement | `plt.savefig('fig.eps')` |

## Workflow

1. **Determine data source:** CSV, JSON, inline, or existing manuscript table
2. **Select chart type:** Based on data characteristics or user request
3. **Choose library:** Based on user preference, language, or best fit
4. **Generate code:** Write the plotting code in-session; for heavy plotting code, optionally launch the `visualization-agent` subagent (Sonnet) via the Task/Agent tool
5. **Apply style preset:** Load `references/figure-styles.md`, resolve the preset by precedence (explicit `Style:` line, then trigger phrase, then journal inference from `manuscript/config.yaml`, then `default`), apply its rcParams and sizing, and tell the user which preset was applied
6. **Apply publication styling:** DPI, fonts, colors, dimensions per journal requirements
7. **Add statistical annotations** if applicable
8. **Generate caption** following journal conventions
9. **Save to `figures/`** in appropriate format
10. **Generate manuscript inclusion snippet** (`\includegraphics{}` or Word embedding)

## Caption Generation

Generate figure captions following academic conventions:
- First sentence: what the figure shows (descriptive)
- Subsequent sentences: key observations, statistical details, panel descriptions
- Example: "Figure 3. Comparison of model accuracy across datasets. (a) Performance on CIFAR-10. (b) Performance on ImageNet. Error bars indicate 95% confidence intervals. The proposed method (blue) significantly outperforms the baseline (orange) on both datasets (p < 0.01)."

## Integration Points

- **figure-suggestions:** Suggests what to plot; visualization generates the actual code
- **latex-tables:** Data from tables can be visualized; visualizations can be tabulated
- **journal-formatting:** Provides figure dimension and style requirements
- **tikz-diagrams:** For schematic/conceptual figures use tikz-diagrams; for data-driven plots use visualization
- **word-output:** PDF exports for LaTeX; PNG exports for Word, which the user places in the document by hand (automated image embedding is planned, not implemented: `templates/word/build-docx.js` generates headings, paragraphs, and lists only)
- **implementation:** Visualization code may be part of experiment pipeline

## Alt Text

Alt text is a REQUIRED output of this skill, delivered with every plot (and every preset variant).
Write one or two sentences describing the DATA content: name the axes, the series compared, and the
direction and size of the trend. Never describe styling (colors, fonts, palette); presets restyle
only, so all variants of one plot share ONE data description plus at most a one-clause style note
(for example "(Nature preset: 89 mm single column)"). Do not begin with "Image of" or restate the
caption verbatim. See the Alt Text section of `references/figure-styles.md`. When the plot is embedded
in Word, `templates/word/build-docx.js` carries this text into the DOCX image accessibility
properties; for LaTeX inclusion, offer `\pdftooltip` (pdfcomment package) without claiming PDF/UA.
