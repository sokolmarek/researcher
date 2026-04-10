# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**Researcher** is a Claude Code / Cowork plugin for academic research workflows. It covers the full pipeline from brainstorming and literature search through experiment design, manuscript drafting, peer review, revision handling, journal selection, and publication formatting. Supports both LaTeX and Word (DOCX) output.

Architecture follows `.claude-plugin/` conventions (same structure as `obra/superpowers`). The plugin manifest is `.claude-plugin/plugin.json`.

## Build Status

This plugin is under active development. Check `TODO.md` for the current task list. The build follows a phased order.

## Key Architecture

- **Skills** (`skills/*/SKILL.md`): 28 independent skills, each with its own SKILL.md containing frontmatter (name, description with trigger phrases) and workflow instructions. Skills are the primary unit of functionality.
- **Agents** (`agents/*.md`): 9 sub-agent definitions that orchestrate multiple skills.
  - `code-agent`, `visualization-agent`: route to **Sonnet model** for code generation
  - `statistics-agent`: uses Opus for reasoning, Sonnet for code
  - `discovery-agent`: orchestrates journal/conference finding, gaps, SOTA
- **Commands** (`commands/*.md`): 11 slash commands that route to skills.
- **Connectors** (`connectors/*.md`): MCP connector configs for external services (Scite, Zotero, PubMed, Semantic Scholar, arXiv, CrossRef, Google Scholar, Mendeley).
- **Hooks** (`hooks/*.md`): Pre-commit citation validation and post-draft integrity checking.
- **References** (`references/*.md`): Citation style guides, journal database, TikZ patterns, PlotNeuralNet layers, table patterns, search strategies. Loaded on demand by skills.
- **Templates** (`templates/`): LaTeX templates (IMRaD, review, conference, response-to-reviewers, cover letter) and Word DOCX generation specs.
- **Scripts** (`scripts/`): Python/bash utilities for bib validation, LaTeX compilation, scholar scraping, codebase analysis, journal lookup.

## Skill Categories (28 total)

### Research & Discovery (6)
literature-search, research-convergence, fact-checking, sota-finder, research-gaps, citation-context

### Planning & Design (4)
brainstorming, experiment-design, statistical-analysis, manuscript-setup

### Writing & Revision (6)
paper-drafting, writing-style-analysis, peer-review, revision-management, response-to-reviewers, cover-letter

### Visualization & Figures (5)
visualization, tikz-diagrams, plotneuralnet, figure-suggestions, latex-tables

### Publishing & Formatting (3)
journal-finder, conference-finder, journal-formatting

### Code & Implementation (2)
implementation, code-analysis

### Output & Management (2)
word-output, citation-management

## Technical Decisions

- **LaTeX compilation:** `tectonic` (auto-downloads packages, single binary, reproducible builds)
- **Word generation:** `docx-js` via Node.js (not pandoc alone)
- **BibTeX management:** Direct file manipulation + CrossRef API validation
- **Style analysis output:** `style-profile.yaml` (YAML format)
- **Multi-model review:** Optional external API calls (OpenAI, Google, Ollama); defaults to Claude-only multi-persona
- **Token optimization:** Code/formatting/visualization tasks -> Sonnet subagent; research/writing/review -> Opus
- **NN architecture diagrams:** PlotNeuralNet-style self-contained .tex files (see `references/plotneuralnet-layers.md`)
- **Scite integration:** Primary citation context source when MCP connected; provides supporting/contrasting/mentioning classification
- **Manuscript structure:** `manuscript/` folder with per-section `.tex` files, `config.yaml`, `terminology.yaml`, `brainstorm-log.md`

## Critical Constraints

1. **Never fabricate citations.** Every reference must come from an actual source.
2. **Never invent data.** Results sections describe only actual data/results.
3. **Never use em dashes in generated text.** Restructure sentences to use commas, parentheses, colons, or separate sentences instead.
4. **Compile-check all LaTeX** via tectonic before delivery.
5. **Validate all DOCX** before delivery.
6. **Route code tasks to Sonnet** subagent to preserve Opus budget.
7. **Each SKILL.md should stay under 500 lines.**

## Plugin Conventions

- Each skill directory contains a single `SKILL.md` with YAML frontmatter (`name`, `description`) followed by markdown workflow instructions.
- The `description` field in SKILL.md frontmatter must include trigger phrases so the plugin system can match user intent.
- Agent `.md` files define role, model routing, orchestrated skills, and workflows.
- Command `.md` files define slash command behavior and routing to skills.
- Connector `.md` files document API integration approach and configuration.

## Slash Commands

`/new-manuscript`, `/draft-section`, `/review-paper`, `/submit-ready`, `/revise`, `/brainstorm`, `/find-journal`, `/find-conference`, `/fact-check`, `/sota`, `/design-experiment`

## Manuscript Output Structure

When the manuscript-setup skill runs, it creates:
```
manuscript/
├── main.tex              # Master doc with \input{} includes
├── abstract.tex          # Per-section files
├── introduction.tex
├── methods.tex
├── results.tex
├── discussion.tex
├── conclusion.tex
├── acknowledgments.tex
├── config.yaml           # Title, authors, journal, citation style, status
├── terminology.yaml      # Consistent term tracking
├── references/library.bib
├── figures/
└── tables/
```

Word mode uses `sections/*.md` files + `build-docx.js` instead.
