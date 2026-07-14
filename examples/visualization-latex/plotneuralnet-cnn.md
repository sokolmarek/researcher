# Example: PlotNeuralNet-Style CNN Architecture

| Field | Value |
|---|---|
| Skill | plotneuralnet |
| Command | n/a |
| Trigger phrase | "Draw a PlotNeuralNet-style diagram of my 1D-CNN ECG encoder" |
| Connectors used | none |
| Generated | 2026-07-12; compiles with any TeX engine (tectonic, TeX Live, MiKTeX, MacTeX), verified with tectonic on this date |

## Invocation

> Draw a PlotNeuralNet-style 3D block diagram of my 1D-CNN ECG encoder: input is 12 leads by 1000 samples, three conv blocks with pooling, global average pooling, a dense layer, and a 5-class softmax. It must compile without the PlotNeuralNet repo.

## Input

Layer specification (above). Macros and colors from `references/plotneuralnet-layers.md`, embedded directly so the file is self-contained.

## Output

Self-contained `.tex` (all layer macros inlined, no `import` of external PlotNeuralNet files). Compiles with any TeX engine (tectonic, TeX Live, MiKTeX, MacTeX); verified with tectonic on 2026-07-12.

```latex
\documentclass[border=15pt, multi, tikz]{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning, 3d, arrows.meta, calc, fit, backgrounds}

\definecolor{ConvColor}{HTML}{3498DB}
\definecolor{ConvReluColor}{HTML}{E67E22}
\definecolor{PoolColor}{HTML}{E74C3C}
\definecolor{FcColor}{HTML}{9B59B6}
\definecolor{SoftmaxColor}{HTML}{1ABC9C}
\definecolor{InputColor}{HTML}{95A5A6}

% #1=name #2=fill #3=opacity #4=caption #5=w(x) #6=h(y) #7=d(z) #8=x #9=y
\newcommand{\nnlayer}[9]{
    \coordinate (#1-anchor) at (#8, #9, 0);
    \fill[#2, opacity=#3] (#1-anchor) ++(-#5/2,-#6/2,-#7/2) -- ++(#5,0,0) -- ++(0,#6,0) -- ++(-#5,0,0) -- cycle;
    \fill[#2!70!black, opacity=#3] (#1-anchor) ++(#5/2,-#6/2,-#7/2) -- ++(0,0,#7) -- ++(0,#6,0) -- ++(0,0,-#7) -- cycle;
    \fill[#2!40!white, opacity=#3] (#1-anchor) ++(-#5/2,#6/2,-#7/2) -- ++(#5,0,0) -- ++(0,0,#7) -- ++(-#5,0,0) -- cycle;
    \fill[#2!85, opacity=#3] (#1-anchor) ++(-#5/2,-#6/2,#7/2) -- ++(#5,0,0) -- ++(0,#6,0) -- ++(-#5,0,0) -- cycle;
    \draw[black!50, thin]
        (#1-anchor) ++(-#5/2,-#6/2,-#7/2) -- ++(#5,0,0) -- ++(0,#6,0) -- ++(-#5,0,0) -- cycle
        (#1-anchor) ++(-#5/2,-#6/2,#7/2) -- ++(#5,0,0) -- ++(0,#6,0) -- ++(-#5,0,0) -- cycle
        (#1-anchor) ++(-#5/2,-#6/2,-#7/2) -- ++(0,0,#7)
        (#1-anchor) ++(#5/2,-#6/2,-#7/2) -- ++(0,0,#7)
        (#1-anchor) ++(#5/2,#6/2,-#7/2) -- ++(0,0,#7)
        (#1-anchor) ++(-#5/2,#6/2,-#7/2) -- ++(0,0,#7);
    \node[below, font=\scriptsize, align=center] at ($(#1-anchor)+(0,-#6/2-0.35)$) {#4};
}
\newcommand{\dimannotation}[3]{%
    \node[above, font=\tiny\ttfamily, text=black!60] at ($(#1-anchor)+(0,#2)$) {#3};
}
\newcommand{\connection}[2]{%
    \draw[-{Stealth[length=3mm]}, thick, black!70] (#1-anchor) -- (#2-anchor);
}

\begin{document}
\begin{tikzpicture}[x=1cm, y=1cm, z=0.35cm]
    % 1D-CNN ECG encoder: 12 leads x 1000 samples -> conv blocks -> GAP -> FC -> softmax
    \nnlayer{input}{InputColor}{0.7}{Input\\12x1000}{0.3}{3.2}{2}{0}{0}
    \dimannotation{input}{2.1}{12@1000}

    \nnlayer{conv1}{ConvColor}{0.8}{Conv1D\\k7,64}{0.4}{2.8}{2}{2}{0}
    \dimannotation{conv1}{2.1}{64@500}
    \nnlayer{pool1}{PoolColor}{0.5}{MaxPool\\/2}{0.3}{2.2}{1.6}{3.6}{0}

    \nnlayer{conv2}{ConvColor}{0.8}{Conv1D\\k5,128}{0.6}{2.0}{1.6}{5.2}{0}
    \dimannotation{conv2}{2.1}{128@250}
    \nnlayer{pool2}{PoolColor}{0.5}{MaxPool\\/2}{0.3}{1.6}{1.3}{6.8}{0}

    \nnlayer{conv3}{ConvColor}{0.8}{Conv1D\\k3,256}{0.8}{1.4}{1.3}{8.4}{0}
    \dimannotation{conv3}{2.1}{256@125}

    \nnlayer{gap}{ConvReluColor}{0.8}{GAP}{0.3}{1.2}{0.8}{10.0}{0}
    \nnlayer{fc1}{FcColor}{0.8}{FC\\128}{0.7}{1.1}{0.3}{11.4}{0}
    \nnlayer{out}{SoftmaxColor}{0.8}{Softmax\\5 classes}{0.3}{1.0}{0.3}{12.9}{0}

    \connection{input}{conv1}
    \connection{conv1}{pool1}
    \connection{pool1}{conv2}
    \connection{conv2}{pool2}
    \connection{pool2}{conv3}
    \connection{conv3}{gap}
    \connection{gap}{fc1}
    \connection{fc1}{out}
\end{tikzpicture}
\end{document}
```

## Rendered output

The self-contained `.tex` compiles to this 3D block diagram (rasterized here for preview):

![1D-CNN ECG encoder: input 12x1000, three conv blocks with pooling, global average pooling, dense layer, 5-class softmax](../../assets/img/examples/plotneuralnet-cnn.png)

## What this demonstrates

- A PlotNeuralNet-style 3D block diagram produced as a single self-contained file: the `\nnlayer` macro and color definitions are inlined, so no clone of the PlotNeuralNet repository is required, matching the self-contained-`.tex` decision in CLAUDE.md.
- Layer box sizes follow the sizing guidance in `references/plotneuralnet-layers.md`: height shrinks as the temporal dimension is pooled (1000 to 125) and width grows with channel count (64 to 256), with dimension annotations above each block.
- The encoder shown is the same `f_theta` that appears in the TikZ pipeline diagram and the manuscript, so the figures tell one consistent story.
- Compiles with any TeX engine (tectonic, TeX Live, MiKTeX, MacTeX); compile-verified with tectonic before inclusion.
