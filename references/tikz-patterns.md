# TikZ Diagram Patterns Library

Loaded by tikz-diagrams skill. Reusable patterns for common academic diagrams.

## Preamble (all diagrams)

```latex
\usepackage{tikz}
\usetikzlibrary{
    arrows.meta,
    positioning,
    shapes.geometric,
    shapes.misc,
    calc,
    fit,
    backgrounds,
    decorations.pathreplacing
}
```

## Pattern 1: System Architecture (boxes + arrows)

```latex
\tikzset{
    block/.style={rectangle, draw, fill=blue!10, minimum height=2em, minimum width=4em, align=center, rounded corners=2pt},
    arrow/.style={-{Stealth[length=3mm]}, thick},
    label/.style={font=\small\itshape}
}

\begin{tikzpicture}[node distance=2cm and 2cm]
    \node[block] (input) {Input};
    \node[block, right=of input] (process) {Process};
    \node[block, right=of process] (output) {Output};
    \draw[arrow] (input) -- (process);
    \draw[arrow] (process) -- (output);
\end{tikzpicture}
```

## Pattern 2: Neural Network Layer Diagram

```latex
\tikzset{
    neuron/.style={circle, draw, fill=orange!20, minimum size=1cm, inner sep=0pt},
    layer label/.style={font=\small\bfseries, above=0.5cm}
}

% Draw a layer of N neurons
\foreach \i in {1,...,4} {
    \node[neuron] (h\i) at (2, -\i*1.2) {};
}
```

## Pattern 3: Flowchart

```latex
\tikzset{
    process/.style={rectangle, draw, fill=blue!10, minimum height=2em, minimum width=5em, align=center},
    decision/.style={diamond, draw, fill=yellow!15, minimum height=2em, minimum width=4em, align=center, aspect=2},
    io/.style={trapezium, draw, fill=green!10, trapezium left angle=70, trapezium right angle=110, minimum height=2em, align=center},
    startstop/.style={rectangle, rounded corners=1em, draw, fill=red!10, minimum height=2em, minimum width=4em, align=center},
    arrow/.style={-{Stealth[length=3mm]}, thick}
}
```

## Pattern 4: Comparison Framework (side-by-side)

```latex
\begin{tikzpicture}
    % Left side
    \node[block, fill=blue!15] (a1) at (0, 0) {Method A};
    % Right side
    \node[block, fill=red!15] (b1) at (6, 0) {Method B};
    % Comparison dimension
    \node[font=\small] at (3, 0) {vs.};
    % Feature rows
    \node[font=\small, anchor=east] at (-0.5, -1) {Speed};
    \draw[fill=blue!40] (0, -1.2) rectangle (2, -0.8);    % A score
    \draw[fill=red!40] (6, -1.2) rectangle (7.5, -0.8);   % B score
\end{tikzpicture}
```

## Pattern 5: Timeline / Gantt

```latex
\begin{tikzpicture}
    % Timeline axis
    \draw[-{Stealth}] (0,0) -- (12,0) node[right] {Time};
    % Ticks
    \foreach \x/\label in {0/2020, 3/2021, 6/2022, 9/2023, 12/2024} {
        \draw (\x, 0.15) -- (\x, -0.15) node[below] {\small\label};
    }
    % Events
    \node[fill=blue!20, rounded corners, inner sep=3pt, above=0.3cm] at (1.5, 0) {\small Phase 1};
    \draw[ultra thick, blue] (0, 0.05) -- (3, 0.05);
\end{tikzpicture}
```

## Pattern 6: Data Flow Diagram

```latex
\tikzset{
    datastore/.style={rectangle split, rectangle split parts=2, draw, fill=gray!10, align=center},
    external/.style={rectangle, draw, fill=green!10, minimum height=2em, align=center},
    process/.style={circle, draw, fill=blue!10, minimum size=2cm, align=center},
    flow/.style={-{Stealth}, thick}
}
```

## Pattern 7: Tree Structure (using forest)

```latex
\usepackage{forest}

\begin{forest}
    for tree={
        draw, rounded corners, fill=blue!10,
        minimum height=2em, minimum width=4em,
        align=center, anchor=north,
        edge={-{Stealth}, thick},
        l sep=1.5cm, s sep=1cm
    }
    [Root
        [Child A
            [Leaf 1]
            [Leaf 2]
        ]
        [Child B
            [Leaf 3]
        ]
    ]
\end{forest}
```

## Pattern 8: Mathematical Plot (pgfplots)

```latex
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}

\begin{tikzpicture}
\begin{axis}[
    xlabel={Epoch},
    ylabel={Loss},
    legend pos=north east,
    grid=major,
    width=0.8\textwidth,
    height=0.5\textwidth
]
\addplot[blue, thick] coordinates {(1,2.5)(2,1.8)(3,1.2)(4,0.8)(5,0.5)};
\addplot[red, thick, dashed] coordinates {(1,2.3)(2,1.9)(3,1.5)(4,1.3)(5,1.2)};
\legend{Training, Validation}
\end{axis}
\end{tikzpicture}
```

## Pattern 9: Experimental Setup

```latex
\tikzset{
    component/.style={rectangle, draw, thick, fill=white, minimum height=2.5em, minimum width=5em, align=center, font=\small},
    data/.style={cylinder, draw, thick, fill=green!10, shape border rotate=90, minimum height=1.5em, minimum width=2.5em, aspect=0.3, align=center, font=\small},
    arrow/.style={-{Stealth[length=3mm]}, thick},
    dashedarrow/.style={-{Stealth[length=3mm]}, thick, dashed}
}
```

## Pattern 10: State Machine / FSM

```latex
\tikzset{
    state/.style={circle, draw, thick, fill=blue!10, minimum size=1.5cm, align=center, font=\small},
    accepting/.style={state, double},
    initial/.style={state, fill=green!15},
    trans/.style={-{Stealth[length=3mm]}, thick, bend left=20}
}
```

## Color Palette (publication-friendly)

Named style-preset variants (default, nature, ieee) live in `references/figure-styles.md`; this file documents the default preset.

```latex
% Colorblind-safe palette
\definecolor{cb-blue}{HTML}{0072B2}
\definecolor{cb-orange}{HTML}{E69F00}
\definecolor{cb-green}{HTML}{009E73}
\definecolor{cb-red}{HTML}{D55E00}
\definecolor{cb-purple}{HTML}{CC79A7}
\definecolor{cb-cyan}{HTML}{56B4E9}
\definecolor{cb-yellow}{HTML}{F0E442}
```

## Tips

- Always use colorblind-safe palettes for publication figures
- Set `\pgfplotsset{compat=1.18}` to avoid warnings
- Use `standalone` document class for individual figure compilation
- Export to PDF for vector quality; use `tectonic` for compilation
- Keep diagrams simple: academic figures prioritize clarity over aesthetics
