---
name: plotneuralnet
description: "Generate publication-quality neural network architecture diagrams using PlotNeuralNet-style TikZ, drawn layer by layer with conv, pooling, and feature-map blocks. Triggers: neural network diagram, plot neural net, architecture diagram, draw the CNN architecture, CNN diagram, U-Net diagram, encoder-decoder diagram, network architecture, layer diagram, deep learning figure. It draws the layer stack of a model; diagrams that are not layer stacks are tikz-diagrams."
---

# PlotNeuralNet

Generate publication-quality neural network architecture diagrams as self-contained TikZ `.tex` files. Based on the PlotNeuralNet approach (github.com/HarisIqbal88/PlotNeuralNet), but fully self-contained: no external dependency files needed.

## Key Principle

Every generated `.tex` file is a single standalone document. All layer macros, color definitions, and style commands are embedded directly in the file preamble. The file compiles with any standard TeX engine (tectonic recommended, or TeX Live, MiKTeX, MacTeX) without additional files.

## Layer Types

Each layer is rendered as a 3D box with configurable width, height, and depth. Colors follow a consistent scheme for visual clarity.

### Convolutional Layers
- **Conv2D / Conv3D:** Blue boxes (`ConvColor = blue!50`)
- **ConvReLU:** Blue box with orange activation band (`ConvReluColor = blue!40, ReluColor = orange!50`)
- **ConvBatchNormReLU:** Blue box with green BN band and orange ReLU band

### Pooling Layers
- **MaxPool / AvgPool:** Orange boxes (`PoolColor = orange!60`)
- **UnPool / Upsample:** Green boxes (`UnpoolColor = green!50`)
- **GlobalAvgPool:** Small orange cube

### Activation and Normalization
- **ReLU:** Orange band (usually part of ConvReLU)
- **Softmax:** Teal box (`SoftmaxColor = teal!50`)
- **BatchNorm:** Green band
- **LayerNorm:** Light green band
- **Dropout:** Dashed outline modifier

### Fully Connected Layers
- **FC / Dense:** Purple boxes (`FcColor = purple!50`)
- **FC + ReLU:** Purple box with orange band
- **Output layer:** Purple box with dimension annotation

### Special Elements
- **Residual / Skip connections:** Curved arrows connecting non-adjacent layers
- **Sum node:** Circle with `+` symbol, for residual addition
- **Concatenation node:** Circle with `||` symbol, for feature map concatenation
- **Input image:** Rendered as a small image placeholder or labeled rectangle
- **Custom layers:** User-defined color and label

## Auto-Sizing

Layer box dimensions are proportional to feature map sizes:
- **Height/Depth:** Proportional to spatial dimensions (H, W), scaled logarithmically for large differences
- **Width:** Proportional to number of channels/filters, with minimum width for visibility
- Scaling factors are configurable at the top of the generated file

## Annotations

Each layer box can display:
- **Layer name:** Above or below the box (e.g., "Conv1", "Pool2")
- **Tensor dimensions:** Formatted as CxHxW or HxWxC on the side of the box
- **Parameter count:** Optional, shown below the layer name
- **Kernel size:** Shown as small text (e.g., "3x3", "1x1")

## Architecture Presets

### VGG
Triggered by: "VGG diagram", "VGG architecture"
- Sequential conv blocks (2-3 conv layers each) with increasing filters
- MaxPool between blocks
- Three FC layers at the end
- Classic architecture: Conv(64) x2 -> Pool -> Conv(128) x2 -> Pool -> ... -> FC(4096) -> FC(4096) -> FC(1000)

### ResNet
Triggered by: "ResNet diagram", "residual network"
- Residual blocks with skip connections (curved arrows)
- Sum nodes for residual addition
- Bottleneck blocks (1x1 -> 3x3 -> 1x1) for deeper variants
- Downsampling via stride-2 convolutions

### U-Net
Triggered by: "U-Net diagram", "encoder-decoder"
- Symmetric encoder-decoder with skip connections
- Encoder: Conv blocks + MaxPool (contracting path)
- Decoder: UpConv + Concatenation + Conv blocks (expanding path)
- Horizontal skip connections between matching encoder/decoder levels

### Transformer Encoder
Triggered by: "transformer diagram", "attention architecture"
- Multi-head self-attention block
- Feed-forward network block
- Layer normalization bands
- Residual connections around each sub-block
- Positional encoding input

### GAN
Triggered by: "GAN diagram", "generator discriminator"
- Generator and Discriminator as separate sub-diagrams
- Generator: FC -> Reshape -> ConvTranspose blocks
- Discriminator: Conv blocks -> FC -> Sigmoid
- Noise vector input (z) and real/fake labels

### Autoencoder
Triggered by: "autoencoder diagram", "VAE diagram"
- Encoder compressing to latent space (bottleneck)
- Decoder expanding back to input dimensions
- Latent space node (for VAE: mu and sigma branches)
- Symmetric or asymmetric structure

## File Structure

### Generated .tex File
```latex
\documentclass[border=15pt]{standalone}
\usepackage{tikz}
\usepackage{tikz-3dplot}

% === Color Definitions ===
\definecolor{ConvColor}{RGB}{100,149,237}
\definecolor{ConvReluColor}{RGB}{100,149,237}
\definecolor{ReluColor}{RGB}{255,165,0}
\definecolor{PoolColor}{RGB}{255,140,0}
\definecolor{UnpoolColor}{RGB}{80,200,120}
\definecolor{FcColor}{RGB}{147,112,219}
\definecolor{SoftmaxColor}{RGB}{0,180,180}

% === Layer Macros ===
% (all macros defined inline, no external files)
\newcommand{\ConvBlock}[5]{...}   % name, width, height, depth, offset
\newcommand{\PoolBlock}[4]{...}   % name, width, height, offset
\newcommand{\FcBlock}[3]{...}     % name, width, offset
\newcommand{\SkipConnection}[2]{...} % from, to
\newcommand{\SumNode}[2]{...}     % name, offset

% === Scaling ===
\def\channelScale{0.04}  % width per channel
\def\spatialScale{0.02}  % height/depth per spatial dim

\begin{document}
\begin{tikzpicture}[
    x=1cm, y=1cm, z=0.5cm,
    >=stealth,
    layer/.style={draw, fill opacity=0.8, line width=0.3pt},
]
  % Architecture definition here
\end{tikzpicture}
\end{document}
```

## Input Specification

### Natural Language
User describes the architecture in plain text:
> "Draw a CNN with 3 conv layers (32, 64, 128 filters), each followed by ReLU and max pooling, then two FC layers (256, 10) with a softmax output."

Parse into a layer list and generate the diagram.

### Layer List
User provides a structured specification:
```
Input: 224x224x3
Conv2D: 64 filters, 3x3, ReLU
Conv2D: 64 filters, 3x3, ReLU
MaxPool: 2x2
Conv2D: 128 filters, 3x3, ReLU
MaxPool: 2x2
FC: 4096, ReLU
FC: 1000
Softmax
```

### Model Code
User provides PyTorch/TensorFlow/Keras model code. Parse layer definitions and generate the corresponding diagram.

## Workflow

1. **Parse architecture** from natural language, layer list, or model code
2. **Select preset** if architecture matches a known type, otherwise build custom
3. **Calculate box dimensions** from feature map sizes using auto-sizing
4. **Load `references/figure-styles.md` and apply the style preset**: resolve the preset by precedence (an explicit `Style:` line in the request, then trigger phrases, then the target journal in `manuscript/config.yaml`, then `default`); state which preset was applied and why (e.g., "applied `nature` preset: target journal in config.yaml is Nature Communications")
5. **Generate TikZ code** with all macros and definitions inline
6. **Save** to `figures/<architecture-name>.tex`
7. **Compile-check** by running `scripts/latex-compile.py` (or `latex-compile.sh` on POSIX), which uses whichever TeX engine is installed (tectonic recommended, or latexmk / pdflatex from TeX Live, MiKTeX, or MacTeX), and verify rendering
8. **Generate manuscript inclusion** snippet:
   ```latex
   \begin{figure}[htbp]
     \centering
     \includegraphics[width=\textwidth]{figures/<architecture-name>.pdf}
     \caption{Architecture of the proposed network.}
     \label{fig:architecture}
   \end{figure}
   ```

## Customization

Users can override defaults:
- **Colors:** Provide custom color definitions for any layer type
- **Orientation:** Left-to-right (default) or top-to-bottom
- **Scale:** Global scaling factor for the entire diagram
- **Labels:** Toggle layer names, dimensions, parameter counts on/off
- **Spacing:** Adjust gap between layers
- **Highlight:** Emphasize specific layers (thicker border, distinct color) to show novel components

## Style presets

Named presets (`default`, `nature`, `ieee`) are defined once in `references/figure-styles.md`. This skill does not duplicate those definitions; it consumes them. Only colors, fonts, and line weights change between presets: the geometry macros (box sizing, spacing, auto-sizing scale factors) are preset-independent and stay identical across all three.

Presets resolve in one precedence order, highest first: **explicit `Style:` line > trigger phrase > journal inference from `manuscript/config.yaml` > `default`**.

`Style:` line (accepted input): the invocation may carry an explicit `Style:` line, which outranks every other selector:

```
Draw my 1D-CNN ECG encoder as a PlotNeuralNet-style diagram.
Style: nature
```

`Style: nature` and `Style: ieee` apply that preset. `Style: default`, or no `Style:` line at all, is the no-op path: exactly the current behavior described above (zero change), and an omitted `Style:` line is never an error. For any other value, do not guess and do not improvise a preset: say it is not defined, list the presets that are (`default`, `nature`, `ieee`), and ask which to use.

Trigger phrases that select a non-default preset when no `Style:` line is given: "nature style", "in Nature format", "for submission to <journal>", "IEEE format".

Journal inference: with neither a `Style:` line nor a trigger phrase, if a target journal is set in `manuscript/config.yaml`, map it to a preset family automatically:
- Nature portfolio journals -> `nature`
- IEEE journals/transactions -> `ieee`
- Anything else, or no target journal set -> `default`

Presets restyle only. They never alter data, values, layer dimensions, or the "(synthetic, for demonstration)" labeling on placeholder figures.

## References

Consult `references/plotneuralnet-layers.md` for the complete TikZ layer macro definitions and additional style patterns. Consult `references/figure-styles.md` for the style preset definitions.

## Integration Points

- **tikz-diagrams:** For non-neural-network diagrams (flowcharts, system diagrams), use tikz-diagrams instead
- **code-analysis:** Can extract model architecture from codebase and generate diagram automatically
- **paper-drafting:** Architecture diagrams are typically placed in the Methods section
- **journal-formatting:** Figure dimensions and DPI requirements applied before export
- **figure-suggestions:** May recommend a neural network diagram for methods section

## Alt Text

Alt text is a REQUIRED output of this skill, delivered with every architecture diagram (and every
preset variant). Write one or two sentences describing the DATA content: the layer sequence, the
tensor shapes at each stage, and the output (for example "1D-CNN encoder: input 12x1000, three conv
blocks with pooling, global average pooling, dense layer, 5-class softmax"). Do not describe styling
(layer colors, fonts); presets restyle only, so all variants share ONE data description plus at most a
one-clause style note. Do not begin with "Image of". See the Alt Text section of
`references/figure-styles.md`. For LaTeX inclusion, offer `\pdftooltip` (pdfcomment package) without
claiming full PDF/UA compliance.
