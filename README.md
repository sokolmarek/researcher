# Researcher

![A lone researcher hunched over a glowing laptop, long past midnight](assets/img/header.png)

**A tireless research assistant for the entire academic pipeline. It does not sleep, so you finally can.**

> Built by a doctoral student, for doctoral students (and anyone else drowning in research and manuscripts at 3 AM).

---

*The academic writing workflow is too long, too fragmented, and too lonely. You have a research question on Monday, a literature review due on Friday, a methods section that won't write itself, reviewer comments that question your existence, and a formatting guide that was clearly written by someone who hates you.*

*Researcher is the assistant that absolutely does not understand what you're going through (it is, after all, just an AI that has never once cried in the library stacks), but it will still help you claw your way out.*

**But let's be real:** this tool is not going to do your research for you. It's not going to write your paper while you sleep (though, and this is rather the entire point, you might finally *get* some sleep). It won't fabricate citations, invent data, or pretend to understand your domain better than you do. What it *will* do is handle the brutal, fragmented, soul-crushing logistics of academic publishing so you can focus on the part that actually matters: **your ideas**.

Think of it as a very capable assistant that never sleeps, never forgets a citation format, never sighs when you restructure your introduction for the ninth time, and, crucially, does not need you to stay awake to keep it company.

---

> **Full documentation and a step-by-step cookbook live at [sokolmarek.github.io/researcher](https://sokolmarek.github.io/researcher).** Prefer to read the source? Worked examples with real, DOI-verified output (and rendered figures) are in [`examples/`](examples/).

## What This Is

A Claude Code / Cowork plugin with **28 specialized skills**, **9 agents**, **11 slash commands**, and integrations with every major academic database. It covers the full research pipeline:

```
Brainstorm -> Literature Search -> Research Gaps -> Experiment Design
    -> Statistical Planning -> Implementation -> Manuscript Drafting
    -> Visualization -> Citation Management -> Peer Review -> Revision
    -> Journal Selection -> Formatting -> Submission
```

LaTeX-first, Word-compatible. Every output works in both worlds.

---

## Features

### Research & Discovery

| Skill | What it does |
|-------|-------------|
| **Literature Search** | Multi-source search across PubMed, Semantic Scholar, arXiv, Scite, Google Scholar, CrossRef. Deduplication, ranking, PRISMA tracking. |
| **Research Convergence** | Not just finding papers -- converging on arguments. Three modes: Socratic (interactive), Full Research (deep multi-round), Flash (quick scan). |
| **Fact-Checking** | Verify claims against literature. Uses Scite smart citations. Classifies evidence as supported, contested, or contradicted. |
| **SOTA Finder** | Track state-of-the-art results for any benchmark. Performance timelines, trend detection, comparison tables. |
| **Research Gaps** | Systematically identify methodological, empirical, and theoretical gaps. Rank by impact potential. |
| **Citation Context** | Classify citations as supporting, contrasting, or mentioning. Audit your manuscript for misrepresented sources. |

### Planning & Design

| Skill | What it does |
|-------|-------------|
| **Brainstorming** | Socratic refinement of research ideas. From vague hunch to precise research question through guided questioning. |
| **Experiment Design** | Design studies with proper controls, sample sizes, power analysis. Computational and empirical. Ablation study planning. |
| **Statistical Analysis** | Method selection wizard, assumption checking, implementation in Python/R/MATLAB, APA-formatted results reporting. |
| **Manuscript Setup** | Scaffold a complete project: per-section .tex files, bibliography, figures folder, config. LaTeX, Word, or both. |

### Writing & Revision

| Skill | What it does |
|-------|-------------|
| **Paper Drafting** | Outline mode and section-by-section drafting. Funnel introductions, reproducible methods, data-driven results. Terminology tracking. |
| **Writing Style Analysis** | Calibrate to your voice from past papers. Sentence patterns, hedging, citation density, vocabulary -- all captured in a style profile. |
| **Peer Review** | Simulated multi-reviewer system: Editor-in-Chief, R1 (Methodology), R2 (Domain Expert), R3 (Cross-disciplinary), Devil's Advocate, Writing Reviewer. Optional external model reviewers. |
| **Revision Management** | Parse reviewer comments, create revision roadmap, generate tracked changes in LaTeX and Word. |
| **Response to Reviewers** | Point-by-point response documents. Color-coded changes. Diplomatic disagreements with evidence. |
| **Cover Letter** | Journal-appropriate cover letters. Adapts tone to journal tier. |

### Visualization & Figures

| Skill | What it does |
|-------|-------------|
| **Visualization** | Publication-quality plots in matplotlib, seaborn, ggplot2, ggpubr, plotly, pgfplots. Smart chart type selection. Statistical annotations. |
| **TikZ Diagrams** | System architectures, flowcharts, state machines, timelines, data flow, pgfplots -- all in TikZ. |
| **PlotNeuralNet** | Neural network architecture diagrams with 3D layered boxes. Self-contained single-file .tex. Presets for VGG, ResNet, U-Net, Transformer. |
| **Figure Suggestions** | Analyzes your manuscript and recommends what figures you need, what type, and where to place them. |
| **LaTeX Tables** | Booktabs-style tables. Significance markers, bold best results, multi-column, landscape, longtable. CSV/JSON ingestion. |

### Publishing & Formatting

| Skill | What it does |
|-------|-------------|
| **Journal Finder** | Recommend best-fit journals. Filter by impact factor, quartile, indexing, open access, APC. Detailed reasoning for each. |
| **Conference Finder** | Find relevant conferences with deadlines, rankings, acceptance rates, locations. |
| **Journal Formatting** | Auto-apply requirements for Elsevier, Springer, IEEE, ACM, Nature, Science, PLOS, MDPI, and 50+ more. Compliance validation. |
| **Word Output** | Full DOCX support. Tracked changes, comments, journal templates. Not just pandoc -- proper formatting via docx-js. |
| **Citation Management** | Maintain .bib files, validate DOIs, detect retractions, flag predatory journals, convert formats. Zotero/Mendeley sync. Citation integrity audit. |

### Code & Implementation

| Skill | What it does |
|-------|-------------|
| **Implementation** | Experiment scripts, data pipelines, evaluation code. Reproducibility enforced. Routes to Sonnet to save your Opus budget. |
| **Code Analysis** | Analyze your codebase and generate methods section with pseudocode, complexity analysis, and algorithm environments. |

---

## Slash Commands

| Command | What it does |
|---------|-------------|
| `/new-manuscript` | Create a new manuscript project with full folder structure |
| `/draft-section <section>` | Draft a specific section (abstract, introduction, methods, results, discussion, conclusion) |
| `/review-paper` | Run simulated multi-perspective peer review |
| `/submit-ready` | Pre-submission checklist: citations, formatting, word count, required sections |
| `/revise <round>` | Handle revision round (R1, R2, R3) with reviewer comment parsing |
| `/brainstorm` | Socratic research design refinement |
| `/find-journal` | Find best-fit journals for your paper |
| `/find-conference` | Find relevant conferences with deadlines |
| `/fact-check` | Verify claims against scientific literature |
| `/sota` | Find state-of-the-art results for a benchmark |
| `/design-experiment` | Design an experiment for your research question |

---

## Agents

Nine specialized agents orchestrate skills for complex workflows:

| Agent | Role | Key Skills |
|-------|------|-----------|
| **Research Agent** | Literature search & synthesis | literature-search, citation-management |
| **Writing Agent** | Section drafting & coherence | paper-drafting, writing-style-analysis, figure-suggestions |
| **Review Agent** | Multi-perspective peer review | peer-review (+ optional ChatGPT/Gemini/Ollama) |
| **Formatting Agent** | LaTeX/Word formatting & compliance | journal-formatting, latex-tables, tikz-diagrams, word-output |
| **Code Agent** | Code analysis & implementation (Sonnet) | implementation, code-analysis |
| **Style Agent** | Writing voice calibration | writing-style-analysis |
| **Visualization Agent** | Plots, diagrams, NN architectures (Sonnet) | visualization, tikz-diagrams, plotneuralnet, figure-suggestions |
| **Statistics Agent** | Method selection & experiment design | statistical-analysis, experiment-design, visualization |
| **Discovery Agent** | Journal/conference finding, gaps, SOTA | journal-finder, conference-finder, research-gaps, sota-finder |

---

## Installation

### Claude Code (plugin)

```bash
/plugin marketplace add sokolmarek/researcher
/plugin install researcher@researcher-marketplace
```

### Claude Cowork (Desktop)

1. Clone this repo: `git clone https://github.com/sokolmarek/researcher.git`
2. Open Claude Desktop -> Cowork tab
3. Customize -> Browse plugins -> Upload plugin folder

### Local development (against a clone)

```bash
git clone https://github.com/sokolmarek/researcher.git
claude --plugin-dir researcher
```

---

## Quick Start

### Start a new paper
```
You: "I want to write a paper on federated learning for medical imaging privacy"
```
The plugin scaffolds your manuscript folder, asks for details, and you're ready to go.

### Research your topic
```
You: "Search for recent papers on differential privacy in healthcare AI"
You: "/fact-check Federated learning always preserves patient privacy"
You: "/sota Federated learning medical image segmentation"
```

### Design your experiment
```
You: "/design-experiment Does our federated approach maintain model accuracy within 2% of centralized training?"
You: "What statistical test should I use to compare accuracy across 5 hospital sites?"
```

### Draft and refine
```
You: "/draft-section introduction"
You: "Analyze my writing style from the papers in author-papers/"
You: "Create a system architecture diagram"
You: "Generate a results comparison table from this CSV data"
```

### Review before submission
```
You: "/review-paper"
You: "/find-journal --filters Q1, open access, indexed in Scopus"
You: "/submit-ready"
```

### Handle revisions
```
You: "/revise R1"
You: "Here are the reviewer comments: [paste]"
You: "Generate the response to reviewers document"
```

---

## Connectors

The plugin integrates with external academic services via MCP connectors:

| Service | Protocol | What it provides |
|---------|----------|-----------------|
| **Scite** | MCP | Smart citation context, supporting/contrasting classification |
| **PubMed** | NCBI API | Biomedical literature (20M+ articles) |
| **Semantic Scholar** | S2 API | CS/science papers, citation graphs, author data |
| **arXiv** | API | Preprints in CS, physics, math, biology |
| **CrossRef** | REST API | DOI resolution, metadata validation |
| **Google Scholar** | Web search | Broadest coverage |
| **Zotero** | API/MCP | Reference library sync |
| **Mendeley** | REST API | Reference library sync |

### Optional External Reviewers

For multi-model peer review, configure:

| Service | Environment Variable |
|---------|---------------------|
| OpenAI (ChatGPT) | `OPENAI_API_KEY` |
| Google (Gemini) | `GOOGLE_AI_API_KEY` |
| Local (Ollama) | `OLLAMA_ENDPOINT` |

---

## Requirements

- **Claude Code** or **Claude Cowork** (paid plan)
- **Recommended model:** Claude Opus 4.6 (the plugin routes code tasks to Sonnet automatically)
- **LaTeX compilation:** `tectonic` (auto-installs packages, single binary)
- **Word output:** `node` + `npm` (for docx-js)

---

## Project Structure

```
researcher/
├── .claude-plugin/               # Plugin manifest + marketplace catalog
├── skills/                       # 28 specialized skills
├── agents/                       # 9 orchestration agents
├── commands/                     # 11 slash commands
├── connectors/                   # 8 MCP connector docs
├── hooks/                        # Pre-commit & post-draft checks
├── references/                   # Citation guides, journal DB, TikZ patterns
├── templates/                    # LaTeX & Word templates
├── scripts/                      # Python/bash utilities
├── examples/                     # Worked examples with real, verified output
├── docs/                         # Astro (Starlight) documentation site
├── assets/                       # Header image and rendered figures
└── CLAUDE.md                     # Build instructions
```

---

## Philosophy

1. **Assistant, not author.** This tool guides, assists, and handles logistics. It does not replace your expertise, your thinking, or your judgment (it has none of its own). Every claim needs your verification. Every citation must be real.

2. **Integrity first.** The plugin will never fabricate citations, invent data, or make unsupported claims. It has integrity gates at every step: citation validation, fact-checking, reference verification.

3. **Your voice, amplified.** Style Calibration learns how *you* write. The goal is to sound like a better version of you, not like a robot.

4. **LaTeX-first, Word-compatible.** Because some of us chose suffering and some of us had suffering chosen for us by our collaborators.

5. **Token-smart.** Code and formatting tasks route to Sonnet. Research thinking, writing, and review use Opus. Your budget goes further.

---

## Writing Style Rule

This plugin does not use em dashes in generated academic text. Sentences are restructured to avoid them. Use commas, parentheses, colons, or separate sentences instead.

---

## Contributing

Issues and PRs welcome. If you're a PhD student and this saved you even one hour of formatting hell, that's a win.

---

## Credits & Acknowledgments

Researcher stands on the shoulders of the open academic-tooling community. It was inspired by, and re-implements ideas from, several excellent projects. No code was copied; ideas are credited here and in [`CREDITS.md`](CREDITS.md).

- [academic-research-skills](https://github.com/Imbad0202/academic-research-skills), the prompt-driven skill suite that showed the shape of an integrity-first research assistant.
- [PaperQA2](https://github.com/Future-House/paper-qa), verified retrieval-augmented answering over scientific PDFs.
- [STORM / Co-STORM](https://github.com/stanford-oval/storm), multi-perspective grounded long-form synthesis.
- [Elicit](https://elicit.com), [Consensus](https://consensus.app), and [Scite](https://scite.ai), for structured extraction, evidence synthesis, and Smart Citations.
- [FutureHouse](https://www.futurehouse.org), multi-agent research over real scientific databases.

Documentation is built with [Astro](https://astro.build) and [Starlight](https://starlight.astro.build). See [`CREDITS.md`](CREDITS.md) for the full list.

---

## License

MIT

---

*"The best time to start writing was yesterday. The second best time is right now, ideally after a full night of sleep that your tireless assistant quietly made possible."*
