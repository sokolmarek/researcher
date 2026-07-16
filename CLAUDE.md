# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**Researcher** is a Claude Code / Cowork plugin for academic research workflows. It covers the full pipeline from brainstorming and literature search through experiment design, manuscript drafting, peer review, revision handling, journal selection, and publication formatting. Supports both LaTeX and Word (DOCX) output.

Architecture follows `.claude-plugin/` conventions (same structure as `obra/superpowers`). The plugin manifest is `.claude-plugin/plugin.json`, and the marketplace catalog is `.claude-plugin/marketplace.json` (so it installs via `/plugin install researcher@researcher-marketplace`).

The same skills also run in **OpenAI Codex**, which implements the same open agent-skills standard (a skill is a directory with a SKILL.md carrying `name` + `description` frontmatter; Codex scans `$CWD/.agents/skills`, `$REPO_ROOT/.agents/skills`, then `$HOME/.agents/skills`). `python scripts/install-codex-skills.py` installs all 35 skills as `researcher-<name>`, rewriting plugin-relative paths to absolute paths under a shared asset directory so an installed skill still resolves everything it points at, and dropping the Claude-only routing (subagents, hooks, namespaced slash commands). As of 0.4.0 the installer also copies `core/` into the shared asset directory (minus its virtualenv and caches), so the `uv run --project "${CLAUDE_PLUGIN_ROOT}/core"` invocation resolves under Codex too. See the Scripts bullet and Technical Decisions below.

## Build Status

This plugin is under active development. Worked examples with real, DOI-verified output live in `examples/`, and the documentation site is in `docs/` (Astro plus Starlight, deployed to GitHub Pages). The roadmap and task tracker live in `plans/` (start at `plans/00-MASTER-PLAN.md`); `plans/`, `research/`, and `TODO.md` are kept local and are not tracked in git.

The deterministic retrieval and verification core (`core/`) **exists as of 0.3.0** and is the evidence kernel described below. The evidence-lineage compiler (M3) **shipped in 0.4.0**: the `researcher_core.lineage` graph, the `researcher compile` gate, and the `researcher passport` exports, also described below. The systematic-review vertical (M4) **shipped in 0.5.0**: protocol locking, dual screening with blinded adjudication, the derived PRISMA 2020 layer, RoB 2 and GRADE worksheets, and living reviews, also described below. All of it is optional at runtime: without `uv` or `core/`, the plugin degrades to the 0.2.0 stdlib behavior and never hard-fails (D3). Do not describe `core/`, the compiler, or the systematic-review vertical as planned anywhere in tracked content. What is still genuinely planned is the semantic RAG layer (embeddings, vector stores, GROBID, reranking) deferred post-1.0, and milestone M5 (production completeness).

## Key Architecture

- **Core** (`core/`, the `researcher_core` package): the deterministic evidence kernel, shipped in 0.3.0. A Python package invoked through a JSON-emitting CLI; skills never import it, they shell out to it and read its JSON. Eight connectors (OpenAlex, Crossref, DataCite, arXiv, Semantic Scholar, PubMed, Unpaywall, OpenCitations), fan-out search with per-source error isolation, dedupe, ranking, citation-graph traversal, a brace-aware BibTeX tokenizer, per-axis verification, OA full-text extraction, a lexical BM25 passage index, and an append-only provenance ledger. Full command reference in `references/core-cli.md`; dev setup in `core/README.md`. **What it does NOT do: semantic RAG.** Embeddings, vector stores, GROBID, and reranking beyond an optional lexical extra are out of scope and deferred post-1.0. Invocation is `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core <cmd> --json`, with `pip install -e core/` as the no-uv fallback.
- **Lineage compiler** (`researcher_core.lineage`, shipped in 0.4.0): the evidence-lineage layer over the kernel. A claim-evidence-result graph (claim nodes hash-anchored to a manuscript span; evidence edges tying a claim to an external source passage with population/intervention/outcome qualifiers and the four axis verdicts, or to an internal experiment run identified by a manifest hash; experiment manifests recording code commit, worktree cleanliness, data hashes, seed, and generated-artifact hashes; three JSON schemas: claim-node, evidence-edge, experiment-manifest). `researcher compile` walks the graph and reports one diagnostic per defect class: C001 orphan claim, C002 altered number, C003 stale evidence, C004 qualifier mismatch, C005 retraction, C006 artifact-code drift. Only C001-C006 on clean evidence are refusal-grade; a source error at compile-time re-check is `inconclusive` and never a defect (D9), and an `insufficient-passage` claim is an open item, never a refusal (D11). The gate is replayable per D15 (byte-identical `--json`). `researcher passport --format ro-crate|prov-jsonld` exports the graph as an RO-Crate 1.1 or W3C PROV-JSON-LD research passport, a pure function of the graph. Skill-facing model doc: `references/lineage-model.md`; command reference in `references/core-cli.md`.
- **Systematic-review vertical** (shipped in 0.5.0): a methodologically defensible systematic-review workflow over the ledger. Four core modules: `protocol.py` (`protocol lock|amend|check`: hashes the protocol and emits a `protocol_locked` event; a deviation is an `amendment` event that bumps `protocol_version`, never an edit, so a post-lock edit without an amendment is caught as a hash mismatch), `screen.py` (`screen decide|conflicts|kappa`: two independent screening streams; `screen conflicts` surfaces disagreements to an adjudicator who sees ONLY the record and the eligibility profile, never the votes, so the second opinion is genuinely blind, verified end to end; Cohen's kappa derived from the ledger; an optional ranked queue that reorders only and never auto-excludes), `sr_prisma.py` (`prisma flow|checklist`: the full PRISMA 2020 flow and checklist derived purely by aggregating events, so deleting a screening event changes the derived flow, which is the D10 proof it is derived not stored), and `monitor.py` (`monitor status`: living reviews from saved verbatim strategies diffed against a seen list, feeding a fresh screening batch under the same locked protocol). **PRISMA 2020 is a derived reporting layer over the append-only event ledger, not the architecture.** The ledger vocabulary gained `protocol_locked`, `amendment`, and `adjudication` (alongside the `screening_decision` type reserved earlier). RoB 2 and GRADE worksheets (`references/rob2-worksheet.md`, `references/grade-worksheet.md`) are human-completed by design with no automated risk-of-bias scoring; completed worksheets are hashed into the ledger. `templates/eligibility-profile.yaml` supports PICO, PECO, and SPIDER; `templates/systematic-review.tex` inlines a ledger-derived PRISMA flow and compiles under latexmk. The meta-analysis handoff (in statistical-analysis) binds every pooled number to a committed script and its inputs, so a hand-edited estimate fails `researcher compile` (C002).
- **The four verification axes** (D16), reported side by side and never folded into one verdict: (a) reference identity (`verified` / `mismatch` / `unresolvable` / `inconclusive`), (b) publication status (`current` / `corrected` / `retracted` / `expression-of-concern`), (c) claim faithfulness (`supported` / `partial` / `contradicted` / `insufficient-passage`), (d) accessibility (`full-text` / `abstract-only` / `unavailable`). **Only `unresolvable` and `mismatch` are refusal-grade.** `inconclusive` NEVER is, and no consumer may act on it: it means a source errored or only one index holds the paper. Accusing an honest author of fabricating a real citation is the worst failure this system has.
- **Determinism** (D15) means replayable given a snapshot, a configuration, and a parser version; it is never claimed for live calls. A missing snapshot in replay mode must raise loudly rather than fall back to the network, which is the rule that makes the claim honest. This is tested directly: deleting a stored snapshot and running `evals/run_axes.py` with no flag reports that item as skipped and re-fetches nothing, and two consecutive `--json` runs are byte-identical. Refreshing snapshots is an explicit `--record` (or `--record-missing`, which fetches only absent snapshots because OpenAlex meters full-text search on a daily budget); no other path writes to the eval store.
- **Evals** (`evals/`): seven gold sets in `evals/gold/` (identity 150, status 120, accessibility 105, faithfulness 104 pairs, dedup 210 pairs, retrieval 55 queries, extraction 147 cells), `run_axes.py` (per-axis confusion matrices with Wilson CIs, plus the axis (c) risk-coverage curve), `run_extraction.py` (cell-level location accuracy plus a "not reported" abstention row, gating extraction-tables and measuring core's anchoring floor, offline and byte-identical across runs), `run_triggers.py` (pooled trigger recall and false-trigger rate), and `example-freshness.py`. Measured results live in `evals/BENCHMARKS.md`. The runner exits 1 when any gold item is skipped, so a job cannot go green over a half-measured set.
- **Skills** (`skills/*/SKILL.md`): 35 independent skills, each with its own SKILL.md containing frontmatter (name, description with trigger phrases) and workflow instructions. Skills are the primary unit of functionality.
- **Agents** (`agents/*.md`): 9 sub-agent definitions with YAML frontmatter (name, description, model) that orchestrate multiple skills.
  - `code-agent`, `visualization-agent`, `formatting-agent`: frontmatter pins them to **Sonnet** for code and formatting work
  - `statistics-agent`: inherits the session model for reasoning, delegates generated code to code-agent
  - `discovery-agent`: orchestrates journal/conference finding, gaps, SOTA
- **Commands** (`commands/*.md`): 15 slash commands with YAML frontmatter (description, argument-hint) that route to skills.
- **Connectors** (`connectors/*.md`): 12 docs on a common template (what it provides, mechanism, install and env vars, consuming skills, fallback). Eight of them are the sources the kernel actually calls (OpenAlex, Crossref, DataCite, arXiv, Semantic Scholar, PubMed, Unpaywall, OpenCitations); the other four are Scite and Zotero (user-connected MCP) and Google Scholar and Mendeley (docs-only, no stable free API). No `.mcp.json` is bundled yet (planned).
- **Hooks** (`hooks/hooks.json` + `hooks/*.md`): auto-discovered Claude tool guards. PreToolUse on Bash blocks Claude-run `git commit` commands with dangling `\cite` keys (`scripts/citation-check-hook.py`, exit 2); PostToolUse on Write|Edit prints a draft integrity report (`scripts/draft-integrity-hook.py`, never blocks). `scripts/install-git-hooks.py` installs a real git pre-commit for terminal/IDE commits.
- **References** (`references/*.md`): Citation style guides, journal database, TikZ patterns, PlotNeuralNet layers, table patterns, search strategies, and `integrity-constraints.md` (the canonical runtime copy of the critical constraints). Loaded on demand by skills.
- **Templates** (`templates/`): LaTeX templates (IMRaD, review, conference, response-to-reviewers, cover letter) and Word DOCX generation specs.
- **Scripts** (`scripts/`): Python/bash utilities for bib validation, LaTeX compilation, scholar scraping, codebase analysis, journal lookup. The bib-validator, latex-compile, and install-git-hooks scripts are agent-agnostic and work standalone, with no agent at all.
- **Codex installer** (`scripts/install-codex-skills.py`): installs all 35 skills into Codex, either user scope (`python scripts/install-codex-skills.py` -> `~/.agents/skills`) or repo scope (`--repo .` -> `./.agents/skills`), with `--list` to preview and `--uninstall` to remove. Skills land as `researcher-<name>` (for example `researcher-literature-search`), invoked explicitly (`$researcher-literature-search`) or matched implicitly from the description. It rewrites plugin-relative paths (`references/...`, `templates/...`, `scripts/...`, and the `CLAUDE_PLUGIN_ROOT` variable) to absolute paths under the shared asset directory, and writes an `AGENTS.md` template carrying the integrity rules for the user to copy into their project. As of 0.4.0 it also copies `core/` into that shared directory (minus its virtualenv and caches) so the kernel invocation resolves under Codex, and the command-to-skill map covers the 0.4.0 commands (`research-pipeline`, `verify-citations`) and the 0.5.0 commands (`systematic-review`, `watch-topic`). What does not carry over: the 9 subagents (Codex has none, so the two skills that fork into the Sonnet code agent under Claude simply run in the main session, and the installed copies say so), the Claude tool guards in `hooks/hooks.json` (Codex has no hook system), and the namespaced slash commands (the installer rewrites `/researcher:draft-section` to `$researcher-paper-drafting`, the skill that command routed to). The integrity backstop in Codex is the real git hook: `python scripts/install-git-hooks.py` installs a git pre-commit that blocks dangling `\cite` keys regardless of which agent, or none, made the commit.
- **Examples** (`examples/*.md`): worked examples of selected skills with real, DOI-verified output and rendered figures. Grouped into research-verification, writing-review, visualization-latex, and publishing.
- **Docs** (`docs/`): Astro (Starlight) documentation site with a full cookbook and showcases; deployed to GitHub Pages via `.github/workflows/docs-deploy.yml`.
- **Assets** (`assets/img/`): the README header image and rendered example figures (diagrams, tables, charts).
- **Eval fixtures**: `evals/example-freshness.py` (resolves every example DOI/arXiv ID and compiles every fenced LaTeX block) and `evals/fixtures/manuscript-min/` (a generated multi-file manuscript compiled as the LaTeX acceptance fixture).
- **Workflows** (`.github/workflows/`): `validate.yml` (official `claude plugin validate`, JSON parse, em-dash and placeholder guards, freshness eval), `core.yml` (ruff, mypy, and the offline core suite on a Windows and Linux matrix, plus the benchmark runners), `docs-deploy.yml` (GitHub Pages), `release.yml` (validates, then GitHub Release on tags).

## Skill Categories (35 total)

### Research & Discovery (8)
literature-search, research-convergence, fact-checking, sota-finder, research-gaps, citation-context, citation-audit, research-pipeline

### Systematic Review (4)
systematic-review, extraction-tables, contradiction-detection, literature-monitoring

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

- **Core invocation (D3):** skills call the kernel with `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core <cmd> --json`. Contributors without `uv` use `pip install -e core/` (base) or `pip install -e "core/[fulltext]"`. The base runtime pulls exactly three dependencies (`httpx`, `rapidfuzz`, `platformdirs`); `jsonschema` is a DEV dependency, because schema validation is a test-time concern. **Core is optional and the plugin must never hard-fail without it**: `scripts/bib-validator.py`, `scripts/citation-check-hook.py`, and `scripts/draft-integrity-hook.py` are thin wrappers that prefer core and fall back to stdlib logic, and CI has a dedicated job that runs the suite with no uv and no core to prove it.
- **Two stores, never crossed:** the TTL'd SQLite response cache (platformdirs user cache dir) keeps the kernel polite during ordinary use and NEVER feeds the evals. The content-addressed snapshot store is what tests and benchmarks replay from. Eval snapshots live in the repo; runtime `--record` snapshots live in the user cache.
- **Faithfulness is a lexical baseline, on purpose.** BM25 plus token-overlap and polarity heuristics. It is weak (measured coverage 0.750, and it calls many overstatements `supported`), and that weakness is in-spec: M2 ships the floor, and the measured rate is the deferred semantic layer's start trigger. Do not describe axis (c) as claim verification.
- **Provenance (D19):** append-only SQLite ledger, caller-supplied timestamps (never self-generated, so replays stay deterministic), PRISMA counts DERIVED by aggregation rather than stored. JSONL is an export format, not the write path.
- **LaTeX compilation:** engine-agnostic, resolved by `scripts/latex_engine.py`. tectonic is the recommended default (single binary, fetches packages on demand, reproducible builds) and is what CI uses, but it is never a requirement: a full TeX distribution (TeX Live, MiKTeX, MacTeX) works out of the box. Resolution order: (1) an explicitly named engine via `--engine` or the `LATEX_ENGINE` env var, (2) tectonic on PATH or via `TECTONIC`, (3) `latexmk` (ships with TeX Live, MiKTeX, and MacTeX; it drives rerun and bibliography passes itself), (4) a raw `pdflatex`, `xelatex`, or `lualatex` with BibTeX or Biber passes run explicitly. If no TeX install is found, the scripts print install pointers for tectonic, TeX Live, MiKTeX, and MacTeX. `scripts/latex-compile.py`, `scripts/latex-compile.sh`, `evals/example-freshness.py`, and `scripts/render-example-figures.py` all accept `--engine` / `LATEX_ENGINE`. Any future script that needs LaTeX must import `scripts/latex_engine.py` rather than re-implementing engine detection.
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
- **Codex compatibility:** shared-asset layout. Each skill installs to its own directory (`~/.agents/skills/researcher-<name>` at user scope), while `references/`, `templates/`, and `scripts/` are copied once into a shared directory (`~/.agents/researcher`) that every installed skill points at. Anything a skill points at must therefore survive the path rewrite; the installer's test suite verifies this by asserting every referenced file exists after install.

## Critical Constraints

Note: this CLAUDE.md is contributor documentation and is NOT loaded at plugin runtime. The runtime copy
of these constraints is `references/integrity-constraints.md`, referenced and inlined by every skill and
agent that produces cited content, data, LaTeX, or DOCX. Keep the two in sync.

1. **Never fabricate citations.** Every reference must come from an actual source.
2. **Never invent data.** Results sections describe only actual data/results.
3. **Never use em dashes in generated text.** Restructure sentences to use commas, parentheses, colons, or separate sentences instead.
4. **Compile-check all LaTeX** before delivery with your TeX engine (tectonic, TeX Live, MiKTeX, or MacTeX); run `scripts/latex-compile.py`, which uses whichever engine you have installed.
5. **Validate all DOCX** before delivery.
6. **Route code tasks to the Sonnet-pinned code agent** (`context: fork` + `agent: code-agent` frontmatter) to preserve the session's higher-tier budget.
7. **Each SKILL.md should stay under 500 lines.**
8. **Never claim a capability the repo cannot back, and never deny one it can.** Every user-facing statement is either demonstrably working today or explicitly labeled planned. This cuts both ways: since 0.3.0, calling `core/` "planned" is as false as claiming a feature that does not exist. When a milestone lands, the status rows in `README.md`, `CLAUDE.md`, and `docs/src/content/docs/reference/roadmap.md` are part of the milestone, not paperwork after it.
9. **Keep new skills Codex-installable.** A new skill needs no extra work for Codex: a SKILL.md with `name` + `description` frontmatter is all the standard requires. But any new plugin-relative path (`references/...`, `templates/...`, `scripts/...`, `CLAUDE_PLUGIN_ROOT`) must still resolve after the installer rewrites it into the shared asset directory, so point only at files that ship in `references/`, `templates/`, or `scripts/`.

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
`/researcher:design-experiment`, `/researcher:research-pipeline`, `/researcher:verify-citations`,
`/researcher:systematic-review`, `/researcher:watch-topic`.

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
