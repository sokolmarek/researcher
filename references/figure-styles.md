# Figure Style Presets

Loaded on demand by the visualization, tikz-diagrams, plotneuralnet, latex-tables, and
figure-suggestions skills. This file defines named style presets (default, nature, ieee) so
that every figure, diagram, and table produced for one manuscript looks like it came from one
hand. Presets restyle only: they change fonts, colors, line weights, sizes, and label
placement. They NEVER change data, values, statistical annotations, or the "(synthetic, for
demonstration)" labeling of example data. See the integrity note at the end of this file.

## Choosing a Preset

Presets resolve in one fixed precedence order, highest first:

**explicit `Style:` line > trigger phrase > journal inference from `manuscript/config.yaml` > `default`**

| Precedence | Selector | Preset |
|---|---|---|
| 1 (highest) | `Style: nature` in the invocation | `nature` |
| 1 | `Style: ieee` in the invocation | `ieee` |
| 1 | `Style: default` in the invocation | `default` (explicit no-op) |
| 2 | "nature style", "in Nature format", "for submission to Nature", "Nature Communications", "npj ..." | `nature` |
| 2 | "IEEE format", "two-column IEEE figure", "for IEEE Transactions", "for an IEEE conference" | `ieee` |
| 3 | Target journal in `manuscript/config.yaml` (see Journal inference below) | `nature` or `ieee` |
| 4 (lowest) | Nothing above matched: no `Style:` line, no trigger phrase, no mapped target journal | `default` (zero behavior change from current skill output) |

A higher-precedence selector wins outright. `Style: ieee` on a manuscript whose `config.yaml` targets
Nature Communications produces the `ieee` preset; the journal is not consulted at all.

### The `Style:` invocation line

The visualization, tikz-diagrams, plotneuralnet, latex-tables, and figure-suggestions skills accept an
optional `Style:` line in the invocation. It is the only way to pin a preset unambiguously:

```
Plot macro-AUROC against labeled fraction, one line per method.
Style: nature
```

- `Style: nature` or `Style: ieee`: apply that preset.
- `Style: default`, or no `Style:` line at all: the no-op path, exactly the output the skills produce
  today. An omitted `Style:` line is never an error.
- Any other value (for example `Style: science`): do not guess and do not improvise a preset. Say the
  requested preset is not defined here, list the ones that are (`default`, `nature`, `ieee`), and ask
  which to use.

In figure-suggestions the same `Style:` token appears in two roles: as this accepted input line, and as
the `Style:` field of each figure recommendation the skill emits. When the input line is present, it is
also the value that skill recommends onward.

### Journal inference

If `manuscript/config.yaml` names a target journal, map its family before falling back to
`default`:

- Nature portfolio (Nature, Nature Communications, Nature Methods, any `npj` title, Scientific
  Reports): apply `nature`.
- IEEE (any IEEE Transactions, IEEE Access, IEEE conference): apply `ieee`.
- Anything else: apply `default`.

Whenever a preset is chosen by inference rather than by an explicit user request, say which
preset you applied and why ("Applied the nature preset because manuscript/config.yaml targets
Nature Communications"). Never switch presets silently.

## Preset: default

This is exactly what the skills produce today. It is codified here so the other presets have a
baseline to diverge from. Choosing `default` changes nothing.

### Sizing

- Single column: 3.3 in (84 mm); double column: 6.7 in (170 mm)
- DPI: 300 minimum for raster output, vector (PDF/SVG/EPS) preferred
- These match the current values in `skills/visualization/SKILL.md`.

### matplotlib rcParams

The current standard style template, unchanged:

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

# Categorical colors: Wong colorblind-safe palette (current default)
WONG = ['#E69F00', '#56B4E9', '#009E73', '#F0E442',
        '#0072B2', '#D55E00', '#CC79A7']
```

Single-column figures use `figsize=(3.3, 2.5)`; multi-panel figures use the 6.7 in width as in
the existing `plt.subplots(2, 2, figsize=(6.7, 5))` pattern.

### TikZ style macros

The current conventions from `references/tikz-patterns.md`: `thick` lines, Stealth arrows at
3 mm, pastel `!10`/`!15` fills, and the `cb-*` palette for data-bearing elements.

```latex
% Colorblind-safe palette (current cb-* definitions)
\definecolor{cb-blue}{HTML}{0072B2}
\definecolor{cb-orange}{HTML}{E69F00}
\definecolor{cb-green}{HTML}{009E73}
\definecolor{cb-red}{HTML}{D55E00}
\definecolor{cb-purple}{HTML}{CC79A7}
\definecolor{cb-cyan}{HTML}{56B4E9}
\definecolor{cb-yellow}{HTML}{F0E442}

\tikzset{
    block/.style={rectangle, draw, fill=blue!10, minimum height=2em,
                  minimum width=4em, align=center, rounded corners=2pt},
    arrow/.style={-{Stealth[length=3mm]}, thick},
    label/.style={font=\small\itshape}
}
```

All other pattern styles (`process`, `decision`, `io`, `startstop`, `neuron`, `datastore`,
`external`, `flow`, `component`, `data`, `state`, `trans`) keep their definitions from
`references/tikz-patterns.md` verbatim.

### PlotNeuralNet conventions

The current color block from `references/plotneuralnet-layers.md`, unchanged:

```latex
\definecolor{ConvColor}{HTML}{3498DB}       % Blue - convolutional layers
\definecolor{ConvReluColor}{HTML}{E67E22}   % Orange - conv+relu band
\definecolor{PoolColor}{HTML}{E74C3C}       % Red - pooling layers
\definecolor{UnpoolColor}{HTML}{2ECC71}     % Green - unpooling/upsample
\definecolor{FcColor}{HTML}{9B59B6}         % Purple - fully connected
\definecolor{SoftmaxColor}{HTML}{1ABC9C}    % Teal - softmax/output
```

Outlines: `black!50, thin` box edges, `line width=0.3pt` layer style. Labels: `\scriptsize`
captions below boxes, `\tiny\ttfamily` dimension annotations.

Geometry macros (`\nnlayer`, `\convlayer`, `\connection`, and the rest) are
preset-independent: presets change only colors, fonts, and line weights, never box geometry
or auto-sizing.

### Table conventions

Exactly the rules in `references/table-patterns.md`: booktabs (`\toprule`, `\midrule`,
`\bottomrule`), never `\hline`; no vertical rules; `@{}` outer padding removal;
numbers right-aligned; caption above the table; best result bolded.

### Panel labels

Lowercase letters in parentheses, bold, top-left, as in the current multi-panel pattern:

```python
for ax, label in zip(axes.flat, 'abcd'):
    ax.set_title(f'({label})', loc='left', fontweight='bold')
```

## Preset: nature

For Nature portfolio submissions. Nature figures are small, dense, and sans-serif; every point
of font size matters at 89 mm width. The journal-database entry for the Nature family caps
figures at 8 (including tables) at 300 DPI minimum; this preset targets well above that floor.

### Sizing

- Single column: 89 mm (3.50 in); double column: 183 mm (7.20 in); maximum height: 247 mm
- Design at final size. Do not design large and shrink, or fonts land below the readable
  minimum.

### matplotlib rcParams

```python
import matplotlib.pyplot as plt

NATURE_RC = {
    # Sans-serif stack. The DejaVu Sans fallback is REQUIRED so rendering
    # never fails on machines without Helvetica or Arial installed.
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'font.size': 7,
    'axes.labelsize': 7,
    'axes.titlesize': 7,
    'xtick.labelsize': 6,
    'ytick.labelsize': 6,
    'legend.fontsize': 6,
    'axes.linewidth': 0.5,
    'lines.linewidth': 1.0,
    'xtick.major.width': 0.5,
    'ytick.major.width': 0.5,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': False,          # if a grid is essential, use alpha <= 0.15
    'grid.alpha': 0.15,
    'figure.figsize': (3.50, 2.60),   # single column; (7.20, h) for double
    'figure.dpi': 300,
    'savefig.dpi': 450,
    'savefig.bbox': 'tight',
    'legend.frameon': False,
}
plt.rcParams.update(NATURE_RC)

# Muted categorical palette: desaturated variants of the Wong
# colorblind-safe hues. Lightness is deliberately staggered so the
# series stay distinguishable when printed in grayscale.
NATURE_COLORS = [
    '#2E6E8E',  # muted blue      (from #0072B2, darkest)
    '#C08A28',  # muted orange    (from #E69F00)
    '#3B8C6E',  # muted green     (from #009E73)
    '#A65D33',  # muted vermilion (from #D55E00)
    '#A87C9F',  # muted purple    (from #CC79A7)
    '#7FAECC',  # muted sky blue  (from #56B4E9)
    '#CFC964',  # muted yellow    (from #F0E442, lightest)
]
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=NATURE_COLORS)
```

If more than seven series are needed, add markers or line styles rather than extending the
palette. Verify grayscale legibility before delivery (convert the exported figure to
grayscale and confirm every series is still identifiable).

### TikZ style macros

Sans-serif throughout, hairline weights, smaller arrowheads. Style names mirror
`references/tikz-patterns.md` so existing patterns re-skin by swapping this block in; no
node placement changes.

```latex
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}

% Muted palette (same hexes as the matplotlib preset)
\definecolor{cb-blue}{HTML}{2E6E8E}
\definecolor{cb-orange}{HTML}{C08A28}
\definecolor{cb-green}{HTML}{3B8C6E}
\definecolor{cb-red}{HTML}{A65D33}
\definecolor{cb-purple}{HTML}{A87C9F}
\definecolor{cb-cyan}{HTML}{7FAECC}
\definecolor{cb-yellow}{HTML}{CFC964}

\tikzset{
    % Line weights: 0.5pt primary, 0.3pt secondary. Never use "thick".
    every node/.style={font=\footnotesize},
    block/.style={rectangle, draw, line width=0.5pt, fill=cb-blue!15,
                  minimum height=2em, minimum width=4em, align=center,
                  rounded corners=2pt},
    arrow/.style={-{Stealth[length=2mm]}, line width=0.5pt},
    label/.style={font=\footnotesize\itshape},
    process/.style={rectangle, draw, line width=0.5pt, fill=cb-blue!15,
                    minimum height=2em, minimum width=5em, align=center},
    decision/.style={diamond, draw, line width=0.5pt, fill=cb-yellow!25,
                     minimum height=2em, minimum width=4em, align=center, aspect=2},
    io/.style={trapezium, draw, line width=0.5pt, fill=cb-green!15,
               trapezium left angle=70, trapezium right angle=110,
               minimum height=2em, align=center},
    startstop/.style={rectangle, rounded corners=1em, draw, line width=0.5pt,
                      fill=cb-red!15, minimum height=2em, minimum width=4em,
                      align=center},
    flow/.style={-{Stealth[length=2mm]}, line width=0.5pt},
    dashedarrow/.style={-{Stealth[length=2mm]}, line width=0.5pt, dashed},
    trans/.style={-{Stealth[length=2mm]}, line width=0.5pt, bend left=20},
    secondary/.style={line width=0.3pt}   % gridlines, guides, brackets
}
```

### PlotNeuralNet conventions

Replacement color block only; all geometry macros stay as defined in
`references/plotneuralnet-layers.md`.

```latex
\definecolor{ConvColor}{HTML}{2E6E8E}       % muted blue
\definecolor{ConvReluColor}{HTML}{C08A28}   % muted orange
\definecolor{PoolColor}{HTML}{A65D33}       % muted vermilion
\definecolor{UnpoolColor}{HTML}{3B8C6E}     % muted green
\definecolor{FcColor}{HTML}{A87C9F}         % muted purple
\definecolor{SoftmaxColor}{HTML}{4E9C8E}    % muted teal
```

Outline weight: `line width=0.3pt` with `black!40` edges (lighter than default's
`black!50`). Label font: `\sffamily\scriptsize` captions, `\sffamily\tiny` dimension
annotations. Geometry macros are preset-independent: only colors, fonts, and line weights
change.

### Table conventions

- Body font: `\footnotesize`
- Lighter booktabs rules:

```latex
\setlength{\heavyrulewidth}{0.06em}
\setlength{\lightrulewidth}{0.04em}
```

- Caption above the table (same as default)
- All other rules from `references/table-patterns.md` (booktabs only, no vertical rules,
  right-aligned numbers) still apply.

### Panel labels

Bold lowercase letters with no parentheses: **a**, **b**, **c**. 8pt, placed at the top-left
outside the axes area:

```python
fig.text(x0, y0, 'a', fontsize=8, fontweight='bold', va='top', ha='left')
```

Compute `x0, y0` from each panel's axes bounding box so the label sits outside the axes, not
in the plot area.

## Preset: ieee

For IEEE Transactions and IEEE conference papers. The journal-database entry specifies
single column 3.5 in, double column 7 in, formats EPS/PDF/PNG; IEEEtran is two-column at
10pt body text, so figure text is serif and slightly larger than Nature's.

### Sizing

- Single column: 3.5 in (88.9 mm); double column: 7.16 in (181.8 mm) for `figure*` floats
- Prefer single-column figures; double-column floats migrate to page tops and can drift far
  from their reference.

### matplotlib rcParams

```python
import matplotlib.pyplot as plt

IEEE_RC = {
    # Serif stack to match IEEEtran's Times body text.
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Times', 'Nimbus Roman', 'DejaVu Serif'],
    'font.size': 8,
    'axes.labelsize': 8,
    'axes.titlesize': 8,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'axes.linewidth': 0.5,
    'lines.linewidth': 1.0,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.figsize': (3.5, 2.6),     # single column; (7.16, h) for figure*
    'figure.dpi': 300,
    'savefig.dpi': 600,               # 600 DPI for line art
    'savefig.bbox': 'tight',
}
plt.rcParams.update(IEEE_RC)

# Keep the standard Wong palette; IEEE has no house palette requirement,
# and Wong is colorblind-safe and grayscale-checkable.
WONG = ['#E69F00', '#56B4E9', '#009E73', '#F0E442',
        '#0072B2', '#D55E00', '#CC79A7']
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=WONG)
```

Export vector PDF when possible; use 600 DPI only when a raster format is unavoidable for
line art (photographic content may use 300 DPI).

### TikZ style macros

Times to match the IEEEtran body font. Line weights stay close to default but drop `thick`
in favor of an explicit 0.6pt so diagrams do not look heavier than the 10pt body text.

```latex
\usepackage{newtxtext}   % Times text font, matches IEEEtran
\usepackage{newtxmath}   % matching math, if the diagram contains math

% Standard cb-* palette (unchanged from default)
\definecolor{cb-blue}{HTML}{0072B2}
\definecolor{cb-orange}{HTML}{E69F00}
\definecolor{cb-green}{HTML}{009E73}
\definecolor{cb-red}{HTML}{D55E00}
\definecolor{cb-purple}{HTML}{CC79A7}
\definecolor{cb-cyan}{HTML}{56B4E9}
\definecolor{cb-yellow}{HTML}{F0E442}

\tikzset{
    every node/.style={font=\small},
    block/.style={rectangle, draw, line width=0.6pt, fill=cb-blue!10,
                  minimum height=2em, minimum width=4em, align=center,
                  rounded corners=2pt},
    arrow/.style={-{Stealth[length=2.5mm]}, line width=0.6pt},
    label/.style={font=\small\itshape},
    process/.style={rectangle, draw, line width=0.6pt, fill=cb-blue!10,
                    minimum height=2em, minimum width=5em, align=center},
    decision/.style={diamond, draw, line width=0.6pt, fill=cb-yellow!15,
                     minimum height=2em, minimum width=4em, align=center, aspect=2},
    io/.style={trapezium, draw, line width=0.6pt, fill=cb-green!10,
               trapezium left angle=70, trapezium right angle=110,
               minimum height=2em, align=center},
    startstop/.style={rectangle, rounded corners=1em, draw, line width=0.6pt,
                      fill=cb-red!10, minimum height=2em, minimum width=4em,
                      align=center},
    flow/.style={-{Stealth[length=2.5mm]}, line width=0.6pt},
    dashedarrow/.style={-{Stealth[length=2.5mm]}, line width=0.6pt, dashed},
    trans/.style={-{Stealth[length=2.5mm]}, line width=0.6pt, bend left=20}
}
```

### PlotNeuralNet conventions

Keep the default color block (the standard palette prints fine in IEEE's format); switch the
label font to Times via `newtxtext` in the standalone preamble.

```latex
\usepackage{newtxtext}
% Colors identical to references/plotneuralnet-layers.md (default preset)
```

Outline weight: default (`black!50, thin` edges, `line width=0.3pt` layer style). Label
font: `\scriptsize` captions, `\tiny\ttfamily` dimensions, now rendered in Times. Geometry
macros are preset-independent: only colors, fonts, and line weights change.

### Table conventions

- Body font: `\small`
- IEEEtran caption conventions: table captions render as "TABLE I" in small caps with a
  Roman numeral, placed above the table. Do not fight the class; use plain `\caption{}` and
  let IEEEtran style it.
- Booktabs rules at their default widths, and all rules from
  `references/table-patterns.md` still apply (no `\hline`, no vertical rules).

### Panel labels

`(a)`, `(b)`, `(c)` centered below each panel, matching the IEEE subfigure convention (the
`subfig` or `subcaption` packages under IEEEtran). Prefer assembling panels as separate PDFs
combined with `\subfloat[]{}` in LaTeX so IEEEtran places the (a)/(b) labels natively; if
labeling in matplotlib, put the label in a `fig.text` below the axes, not as a top-left
title.

## Alt Text

Alt text is a required output of every visualization-family skill (visualization, tikz-diagrams,
plotneuralnet, latex-tables, figure-suggestions), alongside the figure or table itself. It is the
short description a screen reader announces and a sighted reader falls back to when the image fails
to load, so it must convey what the figure would tell someone who cannot see it.

Alt text describes the DATA content, never the styling. Write what the figure shows (the variables,
the comparison, the direction and size of the effect, the panels), not how it looks (fonts, colors,
line weights, palette). "Colorblind-safe muted palette" is a styling fact and belongs in the caption
or nowhere, not in alt text.

Because presets restyle only and never change data (see the Integrity Note below), every preset
variant of one figure shares ONE data description. Emit that single data sentence, then append at
most one short style clause naming the preset. The data sentence is identical across variants; only
the trailing clause changes:

- default: `Label-efficiency line plot: self-supervised curves sit above the supervised baselines,
  with the gap largest at the 1% labeled fraction.`
- nature: the same sentence, plus `(Nature preset: 89 mm single column, sans-serif, muted palette).`
- ieee: the same sentence, plus `(IEEE preset: single-column, serif, Wong palette).`

Keep it to one or two sentences. Do not restate the caption verbatim, do not begin with "Image of"
or "Figure showing", and do not put data values in alt text that are absent from the figure. For a
data plot, name the axes and the trend; for a schematic or architecture diagram, name the stages and
their order; for a table rendered as a figure, name the rows/columns compared and the headline result.

Where the alt text travels: markdown examples carry it in the `![alt](path)` text (its presence is
checked mechanically by `evals/example-freshness.py`); `templates/word/build-docx.js` writes it into
the DOCX image accessibility properties; for LaTeX, document `\pdftooltip` (from the `pdfcomment`
package) or a tagged-PDF workflow, without claiming full PDF/UA compliance. Quality stays a human
checkpoint: the presence check cannot judge whether the description is faithful.

## Integrity Note

Presets change appearance only. Restyling never alters:

- a data value, error bar, or statistical annotation,
- a caption's data statement (what was measured, n, CI level, p-values),
- the "(synthetic, for demonstration)" label on example data. If the input figure carries
  that label, the restyled figure carries it too, verbatim.

If a preset's size constraint would require dropping data to fit (for example, a
double-column panel that no longer fits in an 89 mm single column, or a legend that cannot
be placed without covering points), say so and ask the user how to proceed. Never silently
trim series, panels, ticks that carry values, or caption content to satisfy a size limit.

## Adding a Preset

The six subsections above are the contract. A new preset is complete only when it defines
all of them:

1. **Sizing:** single column, double column, and max height, in both mm and inches.
2. **matplotlib rcParams:** a complete, copy-pasteable `rcParams.update` block with an
   explicit font stack (always end the stack with a DejaVu fallback so rendering never
   fails), an explicit `figsize`, and an explicit color cycle with hex values.
3. **TikZ style macros:** a `\definecolor` block plus `\tikzset` overrides that reuse the
   exact style names from `references/tikz-patterns.md` (`block`, `arrow`, `process`,
   `decision`, `io`, `startstop`, `flow`, `trans`, and friends) so existing patterns
   re-skin without edits.
4. **PlotNeuralNet conventions:** a replacement `\definecolor` block, outline weight, and
   label font. Geometry macros stay untouched.
5. **Table conventions:** body font size, booktabs rule widths, caption position.
6. **Panel labels:** letter case, parentheses or not, size, and position.

Then add rows to the "Choosing a Preset" table for its `Style:` value (precedence 1) and its trigger
phrases (precedence 2), and extend the journal inference mapping if the preset corresponds to a journal
family. A preset with no `Style:` value is not selectable explicitly, so it is not finished.

Requirements for any new palette: colorblind-safe (start from Wong or a desaturation of it)
and grayscale-legible (stagger lightness, then check a grayscale export). Keep this file's
structure parallel across presets so skills can locate any subsection by heading.

Obvious future candidates: `science` (Science/AAAS) and `cell` (Cell Press). Both are
structurally close to `nature` (small sans-serif figures, strict figure counts, muted
palettes), so start from the nature preset and adjust sizing and panel-label conventions.
