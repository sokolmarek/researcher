# Researcher

![A lone researcher hunched over a glowing laptop, long past midnight](assets/img/header.png)

**A tireless research assistant for the entire academic pipeline, for Claude Code, Cowork, and OpenAI Codex. It does not sleep, so you finally can.**

[![Listed on ClaudePluginHub](https://www.claudepluginhub.com/badge/sokolmarek-researcher)](https://www.claudepluginhub.com/plugins/sokolmarek-researcher?ref=badge)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/sokolmarek/researcher)](https://github.com/sokolmarek/researcher/releases)

> Built by a doctoral student, for doctoral students (and anyone else drowning in research and manuscripts at 3 AM).

---

*The academic writing workflow is too long, too fragmented, and too lonely. You have a research question on Monday, a literature review due on Friday, a methods section that won't write itself, reviewer comments that question your existence, and a formatting guide that was clearly written by someone who hates you.*

*Researcher is the assistant that absolutely does not understand what you're going through (it is, after all, just an AI that has never once cried in the library stacks), but it will still help you claw your way out.*

**But let's be real:** this tool is not going to do your research for you. It's not going to write your paper while you sleep (though, and this is rather the entire point, you might finally *get* some sleep). It won't fabricate citations, invent data, or pretend to understand your domain better than you do. What it *will* do is handle the brutal, fragmented, soul-crushing logistics of academic publishing so you can focus on the part that actually matters: **your ideas**.

Think of it as a very capable assistant that never sleeps, never forgets a citation format, never sighs when you restructure your introduction for the ninth time, and, crucially, does not need you to stay awake to keep it company.

---

> **Full documentation and a step-by-step cookbook live at [sokolmarek.github.io/researcher](https://sokolmarek.github.io/researcher).** Prefer to read the source? Worked examples with real, DOI-verified output (and rendered figures) are in [`examples/`](examples/).

## What This Is

A Claude Code / Cowork plugin with **29 specialized skills**, **9 agents**, and **11 slash commands** covering the full research pipeline:

```
Brainstorm -> Literature Search -> Research Gaps -> Experiment Design
    -> Statistical Planning -> Implementation -> Manuscript Drafting
    -> Visualization -> Citation Management -> Peer Review -> Revision
    -> Journal Selection -> Formatting -> Submission
```

It also runs on **OpenAI Codex**: all 29 skills install with one script (`python scripts/install-codex-skills.py`), because Codex reads the same open agent-skills format. See [OpenAI Codex](#openai-codex) under Installation for what carries over.

LaTeX-first, Word-compatible. Every output works in both worlds.

## What works today, what is planned

| Capability | Status |
|---|---|
| 29 skills, 9 agents, 11 commands (prompt-driven workflows) | Works today |
| Marketplace install (`/plugin install researcher@researcher-marketplace`) | Works today |
| Codex support (29 skills via `scripts/install-codex-skills.py`) | Works today |
| Citation commit guard (blocks a commit whose `\cite` keys have no bib entry, including bibliography-only deletions) | Works today; run `python scripts/install-git-hooks.py` once per repo to also cover terminal and IDE commits |
| BibTeX validation: brace-aware parser, CrossRef DOI resolution, title and first-author matching, retraction flags (`scripts/bib-validator.py`) | Works today (network required) |
| LaTeX compile checks with whatever TeX engine you have (`scripts/latex-compile.py` / `.sh`) | Works today (any TeX installation: tectonic, TeX Live, MiKTeX, or MacTeX; `scripts/latex_engine.py` autodetects, and `--engine` or `LATEX_ENGINE` picks one explicitly) |
| Figure style presets (default, Nature, IEEE) across the visualization skills | Works today (`references/figure-styles.md`) |
| Word/DOCX output (`templates/word/build-docx.js`, built on the `docx` library): title page, numbered headings, paragraphs, lists | Works today (node required) |
| DOCX tracked changes, comments, and table emission | Specified in `templates/word/article-imrad.md`, not implemented yet |
| Scite Smart Citations, Zotero library access | Works when you connect those MCP servers yourself; not bundled yet |
| External model reviewers (OpenAI, Gemini, Ollama) | Documented integration point, not implemented |
| Multi-index citation verification (verified / mismatch / unresolvable / inconclusive), retraction and faithfulness axes, PRISMA provenance ledger | Planned (M2, next minor release) |
| Evidence-lineage compiler: every claim and number compiles from a source span or an experiment run, with a research passport export | Planned (M3) |
| Bundled `.mcp.json` (Scite, Zotero, paper-search) | Planned |
| Google Scholar / Mendeley APIs | Not planned (no stable free API); fallbacks documented in `connectors/` |

The integrity rules (never fabricate citations, never invent data) are enforced today in two ways: as
refusal-grade constraints inlined in every skill and agent that produces cited content
(`references/integrity-constraints.md`), and as the mechanical checks listed above (commit guard, DOI
resolution and retraction flags, compile checks). A deterministic engine that verifies every reference
against multiple indexes is the next planned milestone. Until it lands, verification is a shared job
between you and the plugin, and the plugin's job is to make your half easy.

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
| **Image Prompt Crafting** | Prompts for external image generators (ChatGPT/DALL-E, Gemini, Midjourney) for conceptual illustrations, graphical abstracts, and cover art. Never for data or results figures, and always with an AI-disclosure caption. |

All five figure-producing skills share named style presets (default, Nature, IEEE) defined in [`references/figure-styles.md`](references/figure-styles.md). Ask for "Nature style" and the sizing, typography, and palette change; your data never does.

### Publishing & Formatting

| Skill | What it does |
|-------|-------------|
| **Journal Finder** | Recommend best-fit journals. Filter by impact factor, quartile, indexing, open access, APC. Detailed reasoning for each. |
| **Conference Finder** | Find relevant conferences with deadlines, rankings, acceptance rates, locations. |
| **Journal Formatting** | Apply journal requirements from a local database of 16 publisher and journal profiles (Elsevier, Springer, IEEE, ACM, Nature, Science, PLOS, MDPI, Wiley, and more); anything else is looked up from the publisher's author guidelines. Compliance validation. |
| **Word Output** | DOCX generation via `templates/word/build-docx.js` (built on the `docx` library, requires node): title page, numbered headings, paragraphs, lists. Tracked changes, comments, and tables are specified but not yet implemented. |
| **Citation Management** | Maintain .bib files, validate DOIs, detect retractions, flag predatory journals, convert formats. Zotero access via the user-installed zotero-mcp server; Mendeley via manual export. Citation integrity audit. |

### Code & Implementation

| Skill | What it does |
|-------|-------------|
| **Implementation** | Experiment scripts, data pipelines, evaluation code. Reproducibility enforced. Forks into the Sonnet-pinned code agent, so codegen does not spend your Opus budget. |
| **Code Analysis** | Analyze your codebase and generate a methods section with pseudocode, complexity analysis, and algorithm environments. Also forks into the code agent. |

---

## Slash Commands

Plugin commands are namespaced by the plugin name, so they never collide with another plugin's:

| Command | What it does |
|---------|-------------|
| `/researcher:new-manuscript` | Create a new manuscript project with full folder structure |
| `/researcher:draft-section <section>` | Draft a specific section (abstract, introduction, methods, results, discussion, conclusion) |
| `/researcher:review-paper` | Run simulated multi-perspective peer review |
| `/researcher:submit-ready` | Pre-submission checklist: citations, formatting, word count, required sections |
| `/researcher:revise <round>` | Handle revision round (R1, R2, R3) with reviewer comment parsing |
| `/researcher:brainstorm` | Socratic research design refinement |
| `/researcher:find-journal` | Find best-fit journals for your paper |
| `/researcher:find-conference` | Find relevant conferences with deadlines |
| `/researcher:fact-check <claim>` | Verify claims against scientific literature |
| `/researcher:sota <benchmark>` | Find state-of-the-art results for a benchmark |
| `/researcher:design-experiment <question>` | Design an experiment for your research question |

Commands take free-text arguments; Claude asks for anything it still needs.

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

### OpenAI Codex

Codex implements the same open agent-skills standard as Claude Code: a skill is a directory holding a
`SKILL.md` with `name` and `description` frontmatter. Codex scans `$CWD/.agents/skills`,
`$REPO_ROOT/.agents/skills`, and `$HOME/.agents/skills`, in that priority order. The installer copies all
29 skills into one of those locations:

```bash
git clone https://github.com/sokolmarek/researcher.git
cd researcher

python scripts/install-codex-skills.py            # user scope: ~/.agents/skills
python scripts/install-codex-skills.py --repo .   # repo scope: ./.agents/skills
python scripts/install-codex-skills.py --list     # preview what would be installed
python scripts/install-codex-skills.py --uninstall
```

Skills install as `researcher-<name>` (for example `researcher-literature-search`), so you can invoke one
explicitly (`$researcher-literature-search`) or let Codex match it from the description. The installer
rewrites plugin-relative paths (`references/...`, `templates/...`, `scripts/...`, and the
`CLAUDE_PLUGIN_ROOT` variable) to absolute paths under a shared asset directory (`~/.agents/researcher`),
so an installed skill still resolves everything it points at; its test suite asserts every referenced file
exists after install. It also writes an `AGENTS.md` template carrying the integrity rules into that shared
directory, for you to copy into your project's `AGENTS.md`.

What carries over: the skills, the Python scripts (bib validation, LaTeX compile, git hooks are
agent-agnostic and run standalone), and the citation commit guard. What does not: the 9 subagents (Codex
has none, so the two skills that fork into the Sonnet code agent under Claude simply run in the main
session, and the installed copies say so), the Claude tool guards in `hooks/hooks.json` (Codex has no hook
system), and the namespaced slash commands (the installer rewrites `/researcher:draft-section` to
`$researcher-paper-drafting`, the skill that command routed to). The integrity backstop under Codex is the
real git hook: `python scripts/install-git-hooks.py` installs a git `pre-commit` that blocks dangling
`\cite` keys no matter which agent, or no agent, made the commit.

### Local development (against a clone)

```bash
git clone https://github.com/sokolmarek/researcher.git
claude --plugin-dir researcher
```

### Recommended: full commit coverage for the citation guard

The plugin's built-in guard only sees commits that Claude itself runs. To also block dangling
`\cite` keys on terminal and IDE commits, install the git hook once per manuscript repository:

```bash
python scripts/install-git-hooks.py            # idempotent; --uninstall to remove
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
You: "/researcher:fact-check Federated learning always preserves patient privacy"
You: "/researcher:sota Federated learning medical image segmentation"
```

### Design your experiment
```
You: "/researcher:design-experiment Does our federated approach maintain model accuracy within 2% of centralized training?"
You: "What statistical test should I use to compare accuracy across 5 hospital sites?"
```

### Draft and refine
```
You: "/researcher:draft-section introduction"
You: "Analyze my writing style from the papers in author-papers/"
You: "Create a system architecture diagram"
You: "Generate a results comparison table from this CSV data"
You: "Now give me that figure in Nature single-column style"
```

### Review before submission
```
You: "/researcher:review-paper"
You: "/researcher:find-journal Q1, open access, indexed in Scopus"
You: "/researcher:submit-ready"
```

### Handle revisions
```
You: "/researcher:revise R1"
You: "Here are the reviewer comments: [paste]"
You: "Generate the response to reviewers document"
```

---

## Connectors

Connector docs under [`connectors/`](connectors/) describe how each external service is reached today.
Public APIs are called directly by skills at runtime. MCP servers work once you connect them yourself;
the plugin does not bundle an `.mcp.json` yet (planned). Google Scholar and Mendeley are docs-only, with
their fallbacks documented:

| Service | Mechanism today | What it provides |
|---------|-----------------|-----------------|
| **Scite** | MCP server, user-connected | Smart citation context, supporting/contrasting classification |
| **PubMed** | NCBI public API, called by skills | Biomedical literature (20M+ articles) |
| **Semantic Scholar** | S2 public API, called by skills | CS/science papers, citation graphs, author data |
| **arXiv** | Public API, called by skills | Preprints in CS, physics, math, biology |
| **CrossRef** | Public REST API, called by skills and scripts | DOI resolution, metadata validation |
| **Google Scholar** | Docs-only (web-search fallback) | Broadest coverage |
| **Zotero** | zotero-mcp MCP server, user-installed | Reference library access |
| **Mendeley** | Docs-only (manual export fallback) | Reference library sync |

### External reviewer models (planned, not implemented)

The peer-review skill specifies an integration for external reviewer models (OpenAI `OPENAI_API_KEY`,
Google `GOOGLE_AI_API_KEY`, local Ollama `OLLAMA_ENDPOINT`), but no dispatch code ships today. Peer
review currently runs Claude's multi-persona panel only. The specification stays in the skill as the
design for a later release.

---

## Requirements

- **Claude Code** or **Claude Cowork** (paid plan)
- **Model:** any current Claude model. Code-heavy skills fork into a Sonnet-pinned agent, so a higher-tier session model is spent on research, writing, and review rather than codegen.
- **LaTeX compilation:** any TeX installation. `tectonic` is recommended (single binary, fetches packages on demand, reproducible builds) and is what CI uses, but TeX Live, MiKTeX, and MacTeX work out of the box: the compile scripts detect `latexmk` or a raw `pdflatex`/`xelatex`/`lualatex` and run the bibliography passes for you. Set `LATEX_ENGINE` (or pass `--engine`) to choose one explicitly. If no TeX is found, the scripts print install pointers.
- **Word output:** `node` (the `docx` library; run `npm install` in `templates/word/`)
- **Scripts and tests:** Python 3.10+ (standard library only; `pytest` to run the test suite)

---

## Project Structure

```
researcher/
├── .claude-plugin/               # Plugin manifest + marketplace catalog
├── skills/                       # 29 specialized skills
├── agents/                       # 9 orchestration agents
├── commands/                     # 11 slash commands
├── connectors/                   # 8 connector docs (mechanism, env vars, fallbacks)
├── hooks/                        # Claude tool guards (hooks.json) + docs
├── references/                   # Citation guides, journal DB, TikZ patterns, figure styles, integrity constraints
├── templates/                    # LaTeX templates + Word (build-docx.js) generation
├── scripts/                      # Python utilities (compile, validate, hooks, render) + tests
├── examples/                     # Worked examples with real, verified output
├── evals/                        # Freshness eval (DOIs + LaTeX) and compile fixture
├── docs/                         # Astro (Starlight) documentation site
├── assets/                       # Header image and rendered figures
├── CLAUDE.md                     # Contributor notes (not loaded at plugin runtime)
├── CONTRIBUTING.md               # How to contribute
└── SECURITY.md                   # Security policy and reporting
```

---

## Philosophy

1. **Assistant, not author.** This tool guides, assists, and handles logistics. It does not replace your expertise, your thinking, or your judgment (it has none of its own). Every claim needs your verification. Every citation must be real.

2. **Integrity first.** Refusal-grade rules (never fabricate citations, never invent data, flag what cannot be verified) are inlined in every skill and agent that produces cited content (`references/integrity-constraints.md`), and a mechanical commit guard blocks dangling citation keys. Today these are prompt-level safeguards plus targeted mechanical checks, not a full verification engine; deterministic multi-index reference verification is the next planned milestone. Until then, verify every claim yourself, and the plugin will keep making that easy.

3. **Your voice, amplified.** Style Calibration learns how *you* write. The goal is to sound like a better version of you, not like a robot.

4. **LaTeX-first, Word-compatible.** Because some of us chose suffering and some of us had suffering chosen for us by our collaborators.

5. **Token-smart.** The implementation and code-analysis skills fork into a Sonnet-pinned code agent (via `context: fork` in their frontmatter), so your session's higher-tier budget goes to research thinking, writing, and review rather than to generating boilerplate.

6. **Measured, not advertised.** Capabilities ship when they can be demonstrated, and the works-today table above is kept honest on purpose. The next milestone is a deterministic evidence kernel with published benchmarks; the one after that is an evidence-lineage compiler where every claim and number in your manuscript traces back to a source span or an experiment run. The goal is a core you can trust, not a bigger feature list.

---

## Writing Style Rule

This plugin does not use em dashes in generated academic text. Sentences are restructured to avoid them. Use commas, parentheses, colons, or separate sentences instead.

---

## Contributing

Issues and PRs welcome. If you're a PhD student and this saved you even one hour of formatting hell, that's a win.

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md): it covers the development setup, the checks CI will
run on your PR, and the house conventions. By taking part you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md).

One kind of bug matters more than the rest. If the plugin ever fabricates a citation or invents data,
please report it with the
[integrity template](https://github.com/sokolmarek/researcher/issues/new?template=integrity-failure.yml).
That is a failure of the thing this project exists for, and it gets triaged first.

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

## Privacy and security

Researcher collects nothing: no telemetry, no analytics, no accounts. Your manuscript, bibliography,
and data stay on your machine. The only outbound requests are the scholarly lookups you ask for (a DOI
to CrossRef, a query to PubMed, and so on). See [`PRIVACY.md`](PRIVACY.md) for exactly what is sent
and where, and [`SECURITY.md`](SECURITY.md) for what the hooks and scripts execute locally.

## License

MIT

---

*"The best time to start writing was yesterday. The second best time is right now, ideally after a full night of sleep that your tireless assistant quietly made possible."*
