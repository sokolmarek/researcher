---
name: tikz-diagrams
description: "Generate TikZ/PGF diagrams for academic papers. Triggers: create diagram, draw architecture, tikz figure, system diagram, flowchart, pipeline diagram, neural network diagram."
---

# TikZ Diagrams

Generate publication-ready TikZ/PGF diagrams for academic papers.

## Diagram Types

### System Architecture
- Layered block diagrams with labeled components
- Arrows showing data/control flow between modules
- Color-coded subsystems with legend
- Typical use: software systems, ML pipelines, hardware architectures

### Neural Network Diagrams
- Layer-by-layer visualization (input, hidden, output)
- Convolutional filter stacks, attention blocks, skip connections
- Annotated dimensions (e.g., 128x128x64)
- Uses custom node styles for different layer types

> **Note on PlotNeuralNet-style diagrams:** For simple neural network diagrams (basic layer stacks, small architectures), this skill handles them well. However, for publication-quality 3D layered architecture diagrams (the style popularized by PlotNeuralNet with isometric 3D blocks, color-coded layer types, and detailed dimension annotations), defer to the dedicated **plotneuralnet** skill instead. That skill specializes in generating PlotNeuralNet-compatible Python/LaTeX code that produces the distinctive 3D CNN/transformer visualizations commonly seen in top-tier ML publications. Use this skill for flowchart-style NN diagrams; use plotneuralnet for 3D architectural visualizations.

### Flowcharts and Pipelines
- Decision diamonds, process rectangles, start/end ovals
- Conditional branching with labeled yes/no paths
- Linear pipelines with sequential processing steps
- Data transformation chains with intermediate representations

### Experimental Setup
- Equipment arrangement diagrams
- Participant flow (CONSORT-style)
- Measurement configurations
- Stimulus presentation timelines

### State Machines
- States as rounded rectangles or circles
- Transitions as labeled arrows with conditions
- Initial/final state markers
- Guard conditions and actions on transitions

### Data Flow Diagrams
- Sources, sinks, processes, and data stores
- Directional arrows with data labels
- Hierarchical decomposition levels

### Comparison Frameworks
- Side-by-side or matrix layouts
- Feature grids with visual indicators
- Venn diagrams for overlap visualization

### Timeline and Gantt Charts
- Horizontal timeline with milestones
- Gantt bars for parallel tasks and dependencies
- Phase markers with date labels

### Tree Structures
- Uses `forest` package for linguistic/parse trees
- Hierarchical classification trees
- Decision trees with split conditions
- Taxonomy diagrams

### Mathematical Plots (pgfplots)
- Line plots, bar charts, scatter plots
- Error bars and confidence bands
- Multiple axes and grouped plots
- Axis labels with LaTeX math notation

## Required Packages

| Package | Purpose |
|---------|---------|
| `tikz` | Core drawing engine |
| `pgfplots` | Data-driven plots and charts |
| `forest` | Tree and hierarchy diagrams |
| `tikz-cd` | Commutative diagrams (category theory) |
| `circuitikz` | Circuit diagrams |
| `tikz-timing` | Timing diagrams |

### Common TikZ Libraries
- `arrows.meta`: modern arrow tips
- `positioning`: relative node placement
- `shapes.geometric`: diamonds, ellipses, trapezoids
- `calc`: coordinate arithmetic
- `fit`: bounding boxes around node groups
- `backgrounds`: shaded regions behind nodes
- `decorations.pathreplacing`: braces and brackets

## Style Conventions

Reference `references/tikz-patterns.md` for reusable patterns. Follow these defaults:

- **Colors:** Use a consistent palette (e.g., `blue!60`, `red!60`, `green!60`). Define named colors at the top of the file for easy theming.
- **Fonts:** Use `\sffamily\small` for node labels. Match the document font family.
- **Line widths:** `thick` for primary flow, `thin` for secondary. Avoid `ultra thick`.
- **Arrow tips:** Use `arrows.meta` style: `-{Stealth[length=3mm]}` or `-{Latex[length=2.5mm]}`.
- **Node spacing:** Minimum 1.5cm between nodes for readability.
- **Grayscale fallback:** Every diagram must remain legible in grayscale (use patterns or dashes alongside color).

## Style presets

This skill consumes TikZ style macros (colors, fonts, line widths, arrowheads) that replace the defaults in `references/tikz-patterns.md`. Named presets are defined once in `references/figure-styles.md`: do not duplicate those definitions here, load that file when a preset is needed.

- **default**: the current behavior described above (Style Conventions). Used when no style is mentioned; zero change from prior output.
- **nature**: preset for Nature-portfolio submissions.
- **ieee**: preset for IEEE submissions.

**Trigger phrases:** "nature style", "in Nature format", "for submission to <journal>", "IEEE format".

**Journal inference:** if a target journal is set in `manuscript/config.yaml`, map it to a preset family: Nature portfolio titles map to `nature`, IEEE titles map to `ieee`, anything else (or no target journal) maps to `default`.

**Scope of presets:** presets restyle only, they change colors, fonts, line widths, and arrowheads. They never alter data, values, or the "(synthetic, for demonstration)" labeling used elsewhere in generated figures.

## Output Format

### Standalone .tex File
Every diagram is saved as a standalone file in `figures/`:

```latex
\documentclass[tikz,border=5pt]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
% ... additional packages as needed

\begin{document}
\begin{tikzpicture}
  % diagram code
\end{tikzpicture}
\end{document}
```

### Integration with Manuscript
Generate an `\input{}` or `\includegraphics{}` reference for `main.tex`:

```latex
\begin{figure}[htbp]
  \centering
  \input{figures/architecture-diagram.tex}
  \caption{Overview of the proposed system architecture.}
  \label{fig:architecture}
\end{figure}
```

### PDF Compilation
- Compile standalone `.tex` to PDF via tectonic
- Verify the output renders correctly before delivering
- Report any compilation errors with suggested fixes

## Workflow

1. Identify diagram type from user description
2. Determine required packages and TikZ libraries
3. Consult `references/tikz-patterns.md` for matching patterns
4. Load `references/figure-styles.md` and apply the matching preset (default, nature, or ieee), determined from trigger phrases or from the target journal in `manuscript/config.yaml`; state which preset was applied and why
5. Generate TikZ code with named styles and coordinates
6. Save standalone `.tex` to `figures/<diagram-name>.tex`
7. Compile to PDF via tectonic and verify output
8. Generate `\input{}` snippet for manuscript integration
9. If Word output is needed, export PDF and embed as image in DOCX
