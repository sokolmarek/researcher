---
name: implementation
description: "Code implementation using Sonnet model. Triggers: implement this, write the code, code this algorithm, run experiment. Routes to Sonnet to conserve Opus tokens."
---

# Implementation

Handle code implementation tasks for research projects. **This skill routes work to the Sonnet model** to conserve Opus tokens for research thinking, writing, and review.

## Model Routing

- All code generation, debugging, and refactoring tasks use **Sonnet** as a subagent
- Opus remains available for high-level architectural decisions and research reasoning
- If the user explicitly requests Opus for a code task, honor that request
- The code-agent (defined in `agents/code-agent.md`) manages this routing

## Workflow

1. **Understand the task** — clarify with the user what needs to be implemented:
   - Experiment script (training, evaluation, ablation)
   - Data processing pipeline (cleaning, transformation, feature extraction)
   - Evaluation code (metrics computation, statistical tests)
   - Visualization script (plots, charts, result figures)
   - Utility or helper module
   - Full project scaffold

2. **Check existing codebase** for context:
   - Read project structure to understand conventions (language, framework, style)
   - Identify existing modules to extend rather than duplicate
   - Check for `requirements.txt`, `environment.yml`, or `pyproject.toml`

3. **Implement** following research software engineering best practices (see below)

4. **Validate** the implementation:
   - Run linters and type checkers if configured
   - Execute tests if test framework is present
   - Verify the code runs without import errors

5. **Connect to manuscript** — offer to update the paper:
   - Suggest running code-analysis skill to generate a methods section
   - Note any hyperparameters or configuration that should be documented

## Reproducibility Requirements

Every implementation must enforce reproducibility:

### Random Seeds
- Set seeds for all sources of randomness: `random`, `numpy`, `torch`, `tensorflow`
- Use a single `SEED` constant or config entry propagated to all libraries
- Document any non-deterministic operations (e.g., CUDA atomics)

### Configuration Files
- Externalize all hyperparameters into a config file (`config.yaml`, `config.json`, or argparse defaults)
- Never hardcode hyperparameters in the training loop
- Include default values with comments explaining each parameter

### Environment Specifications
Generate as appropriate for the project:
- `requirements.txt` — pinned versions (`package==X.Y.Z`)
- `environment.yml` — Conda environment with pinned versions
- `Dockerfile` — reproducible container with exact base image tag
- `pyproject.toml` — if the project uses modern Python packaging

### Logging and Experiment Tracking
- Log all hyperparameters at experiment start
- Log metrics at each evaluation step (loss, accuracy, etc.)
- Save model checkpoints with config metadata
- Support integration with tracking tools: Weights & Biases, MLflow, TensorBoard
- Write results to structured output (CSV or JSON) for downstream analysis

## Code Organization

```
project/
├── src/                    # Source code
│   ├── data/               # Data loading and preprocessing
│   ├── models/             # Model definitions
│   ├── training/           # Training loops and optimization
│   ├── evaluation/         # Metrics and evaluation scripts
│   └── utils/              # Shared utilities
├── scripts/                # Entry-point scripts (train.py, evaluate.py)
├── configs/                # Configuration files
├── tests/                  # Unit and integration tests
├── results/                # Output directory (gitignored)
├── requirements.txt
└── README.md               # Setup and usage instructions
```

Adapt this structure to the user's existing project layout rather than imposing it on established codebases.

## Language and Framework Support

- **Python** (primary): PyTorch, TensorFlow, JAX, scikit-learn, pandas, numpy
- **R**: tidyverse, ggplot2, caret, statistical packages
- **Julia**: Flux, DataFrames, Plots
- **MATLAB**: when required by domain conventions
- **Shell scripts**: data download, preprocessing pipelines, batch job submission

Use whatever language and framework the user's project already employs.

## Visualization Scripts

When generating plots for the paper:
- Use `matplotlib` with publication-quality settings (font sizes, DPI, vector output)
- Export as PDF or EPS for LaTeX inclusion, PNG at 300+ DPI for Word
- Apply consistent color schemes (colorblind-friendly palettes)
- Generate figures into `manuscript/figures/` when a manuscript exists
- Include axis labels, legends, and captions as comments

## Integration with code-analysis Skill

After implementation is complete:
- The code-analysis skill can read the implemented code and generate:
  - Methods section text describing algorithms and data processing
  - Algorithm pseudocode blocks (`algorithm2e` or `algorithmicx`)
  - Computational complexity analysis
- Suggest this integration to the user when implementation wraps up

## After Implementation

- Summarize what was created and where files are located
- List any dependencies that need to be installed
- Provide a minimal command to run the code (e.g., `python scripts/train.py --config configs/default.yaml`)
- Flag any TODO items that require user input (API keys, data paths, hardware-specific settings)
- Suggest next steps: run experiments, analyze code for methods section, or visualize results
