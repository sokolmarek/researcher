# PlotNeuralNet-Style Layer Definitions

Self-contained TikZ definitions for neural network architecture diagrams.
Loaded by the plotneuralnet skill. All definitions are embedded directly in each generated .tex file
so no external dependencies are needed beyond standard TikZ.

Based on the PlotNeuralNet project (github.com/HarisIqbal88/PlotNeuralNet), adapted for
single-file standalone compilation.

Named style-preset variants (default, nature, ieee) live in `references/figure-styles.md`;
this file documents the default preset's color definitions.

## Preamble (include in every generated file)

```latex
\documentclass[border=15pt, multi, tikz]{standalone}
\usepackage{import}
\usepackage{tikz}
\usetikzlibrary{positioning, 3d, arrows.meta, calc, fit, backgrounds}

% ============================================================
% COLOR DEFINITIONS
% ============================================================
\definecolor{ConvColor}{HTML}{3498DB}       % Blue - convolutional layers
\definecolor{ConvReluColor}{HTML}{E67E22}   % Orange - conv+relu band
\definecolor{PoolColor}{HTML}{E74C3C}       % Red - pooling layers
\definecolor{UnpoolColor}{HTML}{2ECC71}     % Green - unpooling/upsample
\definecolor{FcColor}{HTML}{9B59B6}         % Purple - fully connected
\definecolor{SoftmaxColor}{HTML}{1ABC9C}    % Teal - softmax/output
\definecolor{BnColor}{HTML}{F39C12}         % Gold - batch norm
\definecolor{InputColor}{HTML}{95A5A6}      % Gray - input
\definecolor{SkipColor}{HTML}{2C3E50}       % Dark - skip connections
\definecolor{AttentionColor}{HTML}{E91E63}  % Pink - attention layers
\definecolor{NormColor}{HTML}{FF9800}       % Amber - normalization
\definecolor{EmbedColor}{HTML}{00BCD4}      % Cyan - embedding layers
```

## 3D Box Layer Macro

The core macro draws a 3D rectangular box representing a neural network layer.
Parameters: name, fill color, opacity, caption, width, height, depth, x/y/z offset.

```latex
% ============================================================
% CORE 3D BOX MACRO
% ============================================================
% #1=name, #2=fill color, #3=opacity, #4=caption,
% #5=width(x), #6=height(y), #7=depth(z),
% #8=x-offset, #9=y-offset from previous
\newcommand{\nnlayer}[9]{
    \coordinate (#1-anchor) at (#8, #9, 0);
    % Back face
    \fill[#2, opacity=#3]
        (#1-anchor) ++(-#5/2, -#6/2, -#7/2) --
        ++(#5, 0, 0) -- ++(0, #6, 0) -- ++(-#5, 0, 0) -- cycle;
    % Right face
    \fill[#2!70!black, opacity=#3]
        (#1-anchor) ++(#5/2, -#6/2, -#7/2) --
        ++(0, 0, #7) -- ++(0, #6, 0) -- ++(0, 0, -#7) -- cycle;
    % Top face
    \fill[#2!40!white, opacity=#3]
        (#1-anchor) ++(-#5/2, #6/2, -#7/2) --
        ++(#5, 0, 0) -- ++(0, 0, #7) -- ++(-#5, 0, 0) -- cycle;
    % Front face
    \fill[#2!85, opacity=#3]
        (#1-anchor) ++(-#5/2, -#6/2, #7/2) --
        ++(#5, 0, 0) -- ++(0, #6, 0) -- ++(-#5, 0, 0) -- cycle;
    % Edges
    \draw[black!50, thin]
        (#1-anchor) ++(-#5/2, -#6/2, -#7/2) -- ++(#5,0,0) -- ++(0,#6,0) -- ++(-#5,0,0) -- cycle
        (#1-anchor) ++(-#5/2, -#6/2, #7/2) -- ++(#5,0,0) -- ++(0,#6,0) -- ++(-#5,0,0) -- cycle
        (#1-anchor) ++(-#5/2, -#6/2, -#7/2) -- ++(0,0,#7)
        (#1-anchor) ++(#5/2, -#6/2, -#7/2) -- ++(0,0,#7)
        (#1-anchor) ++(#5/2, #6/2, -#7/2) -- ++(0,0,#7)
        (#1-anchor) ++(-#5/2, #6/2, -#7/2) -- ++(0,0,#7);
    % Caption
    \node[below, font=\scriptsize] at (#1-anchor |- 0,-#6/2-0.3) {#4};
}
```

## Simplified Layer Commands

```latex
% ============================================================
% LAYER SHORTHAND COMMANDS
% ============================================================

% Conv2D layer
% \convlayer{name}{caption}{width}{height}{depth}{x-pos}{y-pos}
\newcommand{\convlayer}[7]{%
    \nnlayer{#1}{ConvColor}{0.8}{#2}{#3}{#4}{#5}{#6}{#7}%
}

% Conv + ReLU layer (with orange band)
\newcommand{\convrelulayer}[7]{%
    \nnlayer{#1}{ConvColor}{0.8}{#2}{#3}{#4}{#5}{#6}{#7}%
    % ReLU band on right face
    \fill[ConvReluColor, opacity=0.9]
        (#1-anchor) ++(#3/2-0.05, -#4/2, -#5/2) --
        ++(0.1, 0, 0) -- ++(0, #4, 0) -- ++(-0.1, 0, 0) -- cycle;
}

% Pooling layer
\newcommand{\poollayer}[7]{%
    \nnlayer{#1}{PoolColor}{0.5}{#2}{#3}{#4}{#5}{#6}{#7}%
}

% Unpooling / Upsample layer
\newcommand{\unpoollayer}[7]{%
    \nnlayer{#1}{UnpoolColor}{0.5}{#2}{#3}{#4}{#5}{#6}{#7}%
}

% Fully Connected layer
\newcommand{\fclayer}[7]{%
    \nnlayer{#1}{FcColor}{0.8}{#2}{#3}{#4}{#5}{#6}{#7}%
}

% Softmax / Output layer
\newcommand{\softmaxlayer}[7]{%
    \nnlayer{#1}{SoftmaxColor}{0.8}{#2}{#3}{#4}{#5}{#6}{#7}%
}

% Batch Normalization layer
\newcommand{\bnlayer}[7]{%
    \nnlayer{#1}{BnColor}{0.6}{#2}{#3}{#4}{#5}{#6}{#7}%
}

% Attention layer
\newcommand{\attentionlayer}[7]{%
    \nnlayer{#1}{AttentionColor}{0.7}{#2}{#3}{#4}{#5}{#6}{#7}%
}

% Embedding layer
\newcommand{\embedlayer}[7]{%
    \nnlayer{#1}{EmbedColor}{0.7}{#2}{#3}{#4}{#5}{#6}{#7}%
}
```

## Connection Macros

```latex
% ============================================================
% CONNECTIONS
% ============================================================

% Arrow between layers
% \connection{from-name}{to-name}
\newcommand{\connection}[2]{%
    \draw[-{Stealth[length=3mm]}, thick, black!70]
        (#1-anchor) -- (#2-anchor);
}

% Skip / Residual connection (curved arrow)
% \skipconnection{from-name}{to-name}{bend-height}
\newcommand{\skipconnection}[3]{%
    \draw[-{Stealth[length=3mm]}, thick, SkipColor, dashed]
        (#1-anchor) to[out=90, in=90, looseness=#3] (#2-anchor);
}

% Sum node (for residual additions)
% \sumnode{name}{x-pos}{y-pos}
\newcommand{\sumnode}[3]{%
    \node[circle, draw, thick, fill=white, inner sep=2pt,
          minimum size=0.6cm, font=\large] (#1) at (#2, #3, 0) {$+$};
}

% Concatenation node
% \concatnode{name}{x-pos}{y-pos}
\newcommand{\concatnode}[3]{%
    \node[circle, draw, thick, fill=white, inner sep=2pt,
          minimum size=0.6cm, font=\small] (#1) at (#2, #3, 0) {cat};
}
```

## Dimension Annotation

```latex
% ============================================================
% ANNOTATIONS
% ============================================================

% Annotate tensor dimensions above a layer
% \dimannotation{layer-name}{text}  e.g. \dimannotation{conv1}{64@32x32}
\newcommand{\dimannotation}[2]{%
    \node[above, font=\tiny\ttfamily, text=black!60] at (#1-anchor |- 0,1.5) {#2};
}
```

## Example: Simple CNN

```latex
\begin{document}
\begin{tikzpicture}[x=1cm, y=1cm, z=0.4cm]
    \convrelulayer{conv1}{Conv+ReLU\\3x3, 64}{0.4}{3}{3}{0}{0}
    \convrelulayer{conv2}{Conv+ReLU\\3x3, 64}{0.4}{3}{3}{2.5}{0}
    \poollayer{pool1}{MaxPool\\2x2}{0.3}{2}{2}{4.5}{0}
    \convrelulayer{conv3}{Conv+ReLU\\3x3, 128}{0.6}{2}{2}{6.5}{0}
    \poollayer{pool2}{MaxPool\\2x2}{0.3}{1.5}{1.5}{8.5}{0}
    \fclayer{fc1}{FC 512}{0.8}{1.5}{0.3}{10.5}{0}
    \fclayer{fc2}{FC 256}{0.6}{1.2}{0.3}{12}{0}
    \softmaxlayer{out}{Softmax\\10}{0.3}{1}{0.3}{13.5}{0}

    \connection{conv1}{conv2}
    \connection{conv2}{pool1}
    \connection{pool1}{conv3}
    \connection{conv3}{pool2}
    \connection{pool2}{fc1}
    \connection{fc1}{fc2}
    \connection{fc2}{out}
\end{tikzpicture}
\end{document}
```

## Example: U-Net (encoder-decoder with skip connections)

```latex
\begin{tikzpicture}[x=1cm, y=1cm, z=0.4cm]
    % Encoder
    \convrelulayer{enc1}{Enc1\\64}{0.5}{3}{3}{0}{0}
    \poollayer{pool1}{}{0.3}{2.5}{2.5}{2}{0}
    \convrelulayer{enc2}{Enc2\\128}{0.6}{2.5}{2.5}{4}{0}
    \poollayer{pool2}{}{0.3}{2}{2}{6}{0}
    % Bottleneck
    \convrelulayer{bottleneck}{Bottleneck\\256}{0.8}{2}{2}{8}{0}
    % Decoder
    \unpoollayer{up1}{}{0.3}{2.5}{2.5}{10}{0}
    \convrelulayer{dec2}{Dec2\\128}{0.6}{2.5}{2.5}{12}{0}
    \unpoollayer{up2}{}{0.3}{3}{3}{14}{0}
    \convrelulayer{dec1}{Dec1\\64}{0.5}{3}{3}{16}{0}
    % Output
    \softmaxlayer{output}{Output}{0.3}{3}{3}{18}{0}

    % Forward connections
    \connection{enc1}{pool1} \connection{pool1}{enc2}
    \connection{enc2}{pool2} \connection{pool2}{bottleneck}
    \connection{bottleneck}{up1} \connection{up1}{dec2}
    \connection{dec2}{up2} \connection{up2}{dec1}
    \connection{dec1}{output}

    % Skip connections
    \skipconnection{enc2}{dec2}{1.2}
    \skipconnection{enc1}{dec1}{1.5}
\end{tikzpicture}
```

## Architecture Presets

When the user requests a common architecture, use these as starting points:

| Architecture | Key layers | Notes |
|-------------|-----------|-------|
| VGG | Conv+ReLU blocks → Pool → FC → Softmax | Progressively smaller spatial, deeper channels |
| ResNet | Conv blocks with skip connections + Sum nodes | Identity shortcuts every 2-3 layers |
| U-Net | Encoder → Bottleneck → Decoder with skip connections | Symmetric structure |
| Transformer | Embed → Attention → Norm → FC → Norm (repeated) | Use attention layers |
| GAN | Generator (deconv chain) + Discriminator (conv chain) | Two parallel networks |
| Autoencoder | Encoder → Bottleneck → Decoder | Symmetric, no skip connections |
| LSTM/GRU | Embed → Recurrent blocks → FC → Output | Use custom color for recurrent |

## Sizing Guidelines

- Scale layer height/depth proportional to spatial dimensions (e.g., 224x224 → height=4, 112x112 → height=3)
- Scale layer width proportional to number of channels/filters (64 → 0.4, 512 → 1.0)
- Keep x-spacing consistent (2-3 cm between layers)
- Use at most 12-15 layers for readability; group repeated blocks
