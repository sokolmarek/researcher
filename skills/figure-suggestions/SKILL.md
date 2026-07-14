---
name: figure-suggestions
description: "Suggest appropriate figures and visualizations for manuscript content. Triggers: suggest figures, what figures should I include, visualize results, what charts, figure ideas."
---

# Figure Suggestions

Analyze manuscript content and recommend appropriate figures, chart types, panel layouts, and captions for each section.

## Workflow

1. **Read manuscript state**: load all current section files from `manuscript/`
2. **Identify visualization opportunities**: scan each section for data, processes, comparisons, and relationships that benefit from visual presentation
3. **Recommend figure type**: match content to the most effective visualization
4. **Specify details**: caption, placement, panel layout, data requirements
5. **Link to generation**: hand off to tikz-diagrams or note external tool requirements

## Section-Specific Recommendations

### Introduction
- **Conceptual overview diagram:** high-level illustration of the research problem or domain
- **Research gap visualization:** Venn diagram or comparison matrix showing what prior work covers and where the gap lies
- **Scope diagram:** visual framing of what the paper addresses vs what it does not

### Methods
- **System architecture:** block diagram of overall approach / pipeline
- **Experimental setup:** physical or logical setup of the experiment
- **Data pipeline:** flow diagram from raw data to processed features
- **Model architecture:** neural network layers, module connections, or algorithmic structure
- **Study design:** participant flow (CONSORT), sampling strategy, or protocol diagram

### Results
Select chart type based on data characteristics:

| Data Scenario | Recommended Chart | When to Use |
|---------------|-------------------|-------------|
| Comparison across categories | Bar chart (grouped or stacked) | Discrete categories, few groups |
| Trend over time or sequence | Line chart | Continuous independent variable |
| Relationship between variables | Scatter plot | Two continuous variables |
| Distribution of values | Histogram, box plot, violin plot | Understanding spread and shape |
| Correlation matrix | Heatmap | Many pairwise relationships |
| Part-of-whole composition | Stacked bar or pie chart | Proportional data |
| Performance across conditions | Grouped bar with error bars | Mean + variance comparisons |
| Multi-metric comparison | Radar / spider chart | Comparing profiles across methods |
| Spatial or grid data | Heatmap or contour plot | 2D structured data |
| Qualitative examples | Sample grid | Model outputs, generated images |

### Discussion
- **Comparison frameworks:** tables or diagrams contrasting the proposed approach with prior work
- **Conceptual models:** theoretical framework or causal diagrams
- **Limitation visualization:** scope boundaries, failure cases, edge conditions
- **Future work roadmap:** timeline or branching diagram of next steps

## Figure Specification Format

Present each suggestion in this structure:

```
Figure N: [Descriptive Title]
  Section:    Methods / Results / Discussion
  Type:       Bar chart / Architecture diagram / Heatmap / ...
  Purpose:    What this figure communicates to the reader
  Data needs: What data or information is required to create it
  Layout:     Single panel / Multi-panel (a-d) / Full width / Half width
  Caption:    "Proposed caption text following target journal style."
  Placement:  After paragraph discussing [topic] in [section]
  Generation: TikZ (hand off to tikz-diagrams) / matplotlib / external tool
  Style:      default / nature / ieee (recommended preset, see references/figure-styles.md)
```

## Panel Layout Recommendations

For multi-panel figures, suggest logical groupings:

- **2 panels (a-b):** comparison between two conditions or before/after
- **3 panels (a-c):** pipeline stages or three experimental conditions
- **4 panels (a-d):** 2x2 grid for two factors with two levels each
- **6 panels (a-f):** comprehensive results across multiple metrics or datasets

Specify panel arrangement (rows x columns) and shared axis conventions (shared x-axis for time comparisons, shared y-axis for metric comparisons).

## Caption Guidelines

Generate captions that follow these academic conventions:
1. **First sentence:** state what the figure shows (e.g., "Comparison of model accuracy across four benchmark datasets.")
2. **Detail sentences:** describe panels, axes, color coding, statistical annotations
3. **Interpretation hint:** brief note on the key takeaway (e.g., "Our method consistently outperforms baselines on datasets with >10k samples.")
4. Adapt caption length and style to target journal requirements when `manuscript/config.yaml` specifies a journal

## Placement Strategy

- Place each figure as close as possible to its first textual reference
- Ensure every figure is referenced in the text with `\ref{fig:label}`
- Balance figures across sections (avoid overloading Results with 10 figures and leaving Methods with none)
- Respect journal figure limits; if the journal allows N figures, prioritize the top N suggestions and recommend the rest as supplementary material

## Priority Ranking

Rank all suggestions by impact:
1. **Essential**: the paper is incomplete without this figure (e.g., architecture diagram, main results)
2. **Recommended**: significantly improves clarity or persuasiveness
3. **Optional**: nice to have, could move to supplementary material

## Related Skills

- **tikz-diagrams**: generates TikZ/PGF code for suggested diagrams and charts
- **latex-tables**: alternative when tabular format is more appropriate than a figure
- **paper-drafting**: consumes figure references and integrates placement into section drafts
- **journal-formatting**: provides figure format requirements (DPI, file type, color mode, size limits)
- **image-prompt-crafting**: hand off conceptual illustrations and graphical abstracts to this skill for prompt crafting. Boundary: it never produces data or results figures; those stay with visualization, tikz-diagrams, plotneuralnet, and latex-tables.
