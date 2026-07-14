# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**Researcher** is a Claude Code / Cowork plugin for academic research workflows. It covers the full pipeline from brainstorming and literature search through experiment design, manuscript drafting, peer review, revision handling, journal selection, and publication formatting. Supports both LaTeX and Word (DOCX) output.

Architecture follows `.claude-plugin/` conventions (same structure as `obra/superpowers`). The plugin manifest is `.claude-plugin/plugin.json`, and the marketplace catalog is `.claude-plugin/marketplace.json` (so it installs via `/plugin install researcher@researcher-marketplace`).

## Build Status

This plugin is under active development. Worked examples with real, DOI-verified output live in `examples/`, and the documentation site is in `docs/` (Astro plus Starlight, deployed to GitHub Pages). The roadmap and task tracker live in `plans/` (start at `plans/00-MASTER-PLAN.md`); `plans/`, `research/`, and `TODO.md` are kept local and are not tracked in git. A deterministic retrieval and verification core (`core/`) is planned but does not exist yet.

## Key Architecture

- **Skills** (`skills/*/SKILL.md`): 28 independent skills, each with its own SKILL.md containing frontmatter (name, description with trigger phrases) and workflow instructions. Skills are the primary unit of functionality.
- **Agents** (`agents/*.md`): 9 sub-agent definitions with YAML frontmatter (name, description, model) that orchestrate multiple skills.
  - `code-agent`, `visualization-agent`, `formatting-agent`: frontmatter pins them to **Sonnet** for code and formatting work
  - `statistics-agent`: inherits the session model for reasoning, delegates generated code to code-agent
  - `discovery-agent`: orchestrates journal/conference finding, gaps, SOTA
- **Commands** (`commands/*.md`): 11 slash commands with YAML frontmatter (description, argument-hint) that route to skills.
- **Connectors** (`connectors/*.md`): docs for external services (Scite, Zotero, PubMed, Semantic Scholar, arXiv, CrossRef, Google Scholar, Mendeley) on a common template: what it provides, mechanism (user-connected MCP, direct API, or docs-only), install and env vars, consuming skills, fallback. No `.mcp.json` is bundled yet (planned).
- **Hooks** (`hooks/hooks.json` + `hooks/*.md`): auto-discovered Claude tool guards. PreToolUse on Bash blocks Claude-run `git commit` commands with dangling `\cite` keys (`scripts/citation-check-hook.py`, exit 2); PostToolUse on Write|Edit prints a draft integrity report (`scripts/draft-integrity-hook.py`, never blocks). `scripts/install-git-hooks.py` installs a real git pre-commit for terminal/IDE commits.
- **References** (`references/*.md`): Citation style guides, journal database, TikZ patterns, PlotNeuralNet layers, table patterns, search strategies, and `integrity-constraints.md` (the canonical runtime copy of the critical constraints). Loaded on demand by skills.
- **Templates** (`templates/`): LaTeX templates (IMRaD, review, conference, response-to-reviewers, cover letter) and Word DOCX generation specs.
- **Scripts** (`scripts/`): Python/bash utilities for bib validation, LaTeX compilation, scholar scraping, codebase analysis, journal lookup.
- **Examples** (`examples/*.md`): worked examples of selected skills with real, DOI-verified output and rendered figures. Grouped into research-verification, writing-review, visualization-latex, and publishing.
- **Docs** (`docs/`): Astro (Starlight) documentation site with a full cookbook and showcases; deployed to GitHub Pages via `.github/workflows/docs-deploy.yml`.
- **Assets** (`assets/img/`): the README header image and rendered example figures (diagrams, tables, charts).
- **Evals** (`evals/`): `example-freshness.py` (resolves every example DOI/arXiv ID and compiles every fenced LaTeX block, standalone directly and fragments in a harness) and `fixtures/manuscript-min/` (a generated multi-file manuscript compiled as the LaTeX acceptance fixture).
- **Workflows** (`.github/workflows/`): `validate.yml` (official `claude plugin validate`, JSON parse, em-dash and placeholder guards, freshness eval), `docs-deploy.yml` (GitHub Pages), `release.yml` (validates, then GitHub Release on tags).

## Skill Categories (29 total)

### Research & Discovery (6)
literature-search, research-convergence, fact-checking, sota-finder, research-gaps, citation-context

### Planning & Design (4)
brainstorming, experiment-design, statistical-analysis, manuscript-setup

### Writing & Revision (6)
paper-drafting, writing-style-analysis, peer-review, revision-management, response-to-reviewers, cover-letter

### Visualization & Figures (6)
visualization, tikz-diagrams, plotneuralnet, figure-suggestions, latex-tables, image-prompt-crafting

### Publishing & Formatting (3)
journal-finder, conference-finder, journal-formatting

### Code & Implementation (2)
implementation, code-analysis

### Output & Management (2)
word-output, citation-management

## Technical Decisions

- **LaTeX compilation:** `tectonic` (auto-downloads packages, single binary, reproducible builds)
- **Word generation:** `templates/word/build-docx.js`, Node plus the `docx` library (not pandoc alone). Ships today: title page, numbered headings, paragraphs, lists from `sections/*.md`. Not yet implemented: tables, tracked changes, comments (specified in `templates/word/article-imrad.md`).
- **BibTeX management:** brace-aware tokenizer in `scripts/bib-validator.py` (never regex; the old regex parser could not read compact entries), plus CrossRef validation with title similarity, first-author, and year comparison; 404 and network failures are reported distinctly.
- **Style analysis output:** `style-profile.yaml` (YAML format)
- **Multi-model review:** specified in the peer-review skill (OpenAI, Google, Ollama) but NOT implemented; peer review ships as Claude's multi-persona panel only.
- **Token optimization:** the implementation and code-analysis skills carry `context: fork` + `agent: code-agent` frontmatter, so they execute inside the Sonnet-pinned code agent. Prose cannot switch models; only that frontmatter can.
- **Figure style presets:** default, nature, ieee, defined once in `references/figure-styles.md` and consumed by the visualization-family skills. Presets restyle only; they never alter data.
- **NN architecture diagrams:** PlotNeuralNet-style self-contained .tex files (see `references/plotneuralnet-layers.md`)
- **Scite integration:** Primary citation context source when MCP connected; provides supporting/contrasting/mentioning classification
- **Manuscript structure:** `manuscript/` folder with per-section `.tex` files, `config.yaml`, `terminology.yaml`, `brainstorm-log.md`
- **Command namespacing:** installed plugin commands are always `/researcher:<name>`. User-facing docs must show the namespaced form (CI enforces this).

## Critical Constraints

Note: this CLAUDE.md is contributor documentation and is NOT loaded at plugin runtime. The runtime copy
of these constraints is `references/integrity-constraints.md`, referenced and inlined by every skill and
agent that produces cited content, data, LaTeX, or DOCX. Keep the two in sync.

1. **Never fabricate citations.** Every reference must come from an actual source.
2. **Never invent data.** Results sections describe only actual data/results.
3. **Never use em dashes in generated text.** Restructure sentences to use commas, parentheses, colons, or separate sentences instead.
4. **Compile-check all LaTeX** via tectonic before delivery.
5. **Validate all DOCX** before delivery.
6. **Route code tasks to the Sonnet-pinned code agent** (`context: fork` + `agent: code-agent` frontmatter) to preserve the session's higher-tier budget.
7. **Each SKILL.md should stay under 500 lines.**
8. **Never claim a capability the repo cannot back.** Every user-facing statement is either demonstrably working today or explicitly labeled planned.

## Plugin Conventions

- Each skill directory contains a single `SKILL.md` with YAML frontmatter (`name`, `description`) followed by markdown workflow instructions.
- The `description` field in SKILL.md frontmatter must include trigger phrases so the plugin system can match user intent.
- Agent `.md` files define role, model routing, orchestrated skills, and workflows.
- Command `.md` files define slash command behavior and routing to skills.
- Connector `.md` files document API integration approach and configuration.

## Slash Commands

Installed plugin commands are namespaced: `/researcher:new-manuscript`, `/researcher:draft-section`,
`/researcher:review-paper`, `/researcher:submit-ready`, `/researcher:revise`, `/researcher:brainstorm`,
`/researcher:find-journal`, `/researcher:find-conference`, `/researcher:fact-check`, `/researcher:sota`,
`/researcher:design-experiment`.

Commands accept free-text arguments plus an `argument-hint`; there is no typed form UI, so command
files document inputs as prose gathered conversationally.

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
