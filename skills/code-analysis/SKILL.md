---
name: code-analysis
description: "Analyze a source-code repository that already exists and turn it into publication text. Triggers: analyze codebase, describe implementation, methods from code, write the methods section from my source code, document algorithm as pseudocode, review this codebase for reproducibility, check whether the code is reproducible, check the code matches the described method. It reads existing code and writes about it; writing new code is implementation, and judging a manuscript is peer-review. Runs in the code-agent subagent (Sonnet)."
context: fork
agent: code-agent
---

# Code Analysis

Analyze a project's source code to produce a publication-ready methods section, algorithm pseudocode, and reproducibility documentation.

## Model Routing

This skill executes inside the **code-agent** subagent via its frontmatter (`context: fork`, `agent: code-agent`), which is pinned to Sonnet. The fork receives only the task description and the repository, not the whole conversation, so name the codebase paths to analyze and the target manuscript section explicitly in the task.

## Workflow

1. **Identify scope**: ask user which directories/files to analyze, or default to the project root (excluding `manuscript/`, `node_modules/`, `.git/`, `venv/`)
2. **Run codebase analyzer**: execute `scripts/codebase-analyzer.py` on the target directory to extract structure metadata
3. **Map code to paper sections**: identify which code components correspond to which manuscript sections
4. **Generate outputs**: methods text, pseudocode blocks, complexity analysis, dependency documentation

## Code-to-Paper Mapping

| Code Artifact | Paper Section | Output |
|---------------|---------------|--------|
| Data loading / preprocessing | Methods: Data | Description of pipeline, transformations |
| Model / algorithm definition | Methods: Approach | Pseudocode + prose description |
| Training / optimization loop | Methods: Training | Hyperparameters, optimization details |
| Evaluation scripts | Methods: Evaluation | Metrics, test protocols |
| Config files / CLI args | Methods: Experimental Setup | Hyperparameter tables |
| Test suites / benchmarks | Results | Evaluation metrics, baseline comparisons |

## Analysis Dimensions

### Algorithms and Data Structures
- Identify core algorithms (sorting, graph traversal, optimization, neural architectures)
- Document data structures and their roles
- Extract computational complexity (time and space) for key operations
- Note any approximations or heuristics

### Dependencies and Frameworks
- Parse `requirements.txt`, `pyproject.toml`, `package.json`, `Cargo.toml`, `environment.yml`
- List frameworks with versions (e.g., PyTorch 2.1, scikit-learn 1.4)
- Identify hardware requirements (GPU, memory) from code hints

### Hyperparameters and Configuration
- Extract all configurable parameters from config files, argparse definitions, or constants
- Organize into a LaTeX table with: parameter name, value, description
- Flag hardcoded values that should be documented

### Data Preprocessing
- Trace the data pipeline from raw input to model-ready format
- Document transformations: normalization, augmentation, tokenization, feature engineering
- Note dataset splits and sampling strategies

### Evaluation Metrics
- Identify all metrics computed in evaluation code (accuracy, F1, BLEU, RMSE, etc.)
- Document how each metric is calculated
- Extract baseline comparison logic for results section

## Output: Methods Section

Generate LaTeX for `manuscript/methods.tex` with appropriate subsections:

```latex
\section{Methods}

\subsection{Data}
% Data collection, preprocessing, splits

\subsection{Proposed Approach}
% Core algorithm/model description with pseudocode

\subsection{Experimental Setup}
% Hardware, software, hyperparameters

\subsection{Evaluation}
% Metrics and evaluation protocol
```

## Pseudocode Generation

Generate algorithm blocks using `algorithm2e` (default) or `algorithmicx` (on request):

```latex
\begin{algorithm}[H]
\SetAlgoLined
\KwIn{Input description}
\KwOut{Output description}
Initialization\;
\While{convergence criterion not met}{
  Step 1\;
  Step 2\;
  \eIf{condition}{
    Action A\;
  }{
    Action B\;
  }
}
\caption{Algorithm Name}
\label{alg:name}
\end{algorithm}
```

Write pseudocode at the **appropriate abstraction level** for a methods section: high enough to convey the approach without language-specific syntax, detailed enough to reproduce the work.

## Hyperparameter Table

Generate a `booktabs`-style table in `manuscript/tables/hyperparameters.tex`:

```latex
\begin{table}[h]
\centering
\caption{Hyperparameters used in experiments.}
\label{tab:hyperparams}
\begin{tabular}{@{}llr@{}}
\toprule
Parameter & Description & Value \\
\midrule
Learning rate & Adam optimizer & 3e-4 \\
Batch size & Training & 64 \\
...
\bottomrule
\end{tabular}
\end{table}
```

## Reproducibility Checklist

After analysis, verify and report:
- [ ] All hyperparameters documented
- [ ] Random seeds identified and recorded
- [ ] Software versions captured
- [ ] Hardware requirements noted
- [ ] Data preprocessing steps fully described
- [ ] Evaluation protocol specified
- [ ] Code availability statement drafted

## Related Skills

- **implementation**: generates code from research specifications (inverse of this skill)
- **paper-drafting**: consumes the methods section output
- **latex-tables**: formats hyperparameter and results tables
- **figure-suggestions**: suggests architecture diagrams based on code structure
