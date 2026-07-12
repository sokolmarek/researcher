# Phase 1: Polish and Packaging

Version target: 0.2.1
Effort: 3-4 focused sessions
Architectural change: none. This phase makes the existing plugin correct, complete, installable, and demonstrated.

## Goal

Fix every known defect in the current plugin and make it honestly shippable as 0.2.1. Concretely: correct the manifest to supported fields only and add a marketplace entry (D-E); move the runtime integrity constraints out of the non-loaded CLAUDE.md into skills and agents (D-F); name the hooks honestly as Claude tool guards and add a real git pre-commit for full commit coverage (D-G); make the LaTeX acceptance compile a generated populated manuscript fixture instead of the bare template (D-J); add basic CI (D-L); and finish the placeholder and em-dash sweep, agent frontmatter, connector docs, cross-platform compile twin, doc reconciliation, examples verification, and a smoke trigger test.

## Prerequisites

- `plans/00-MASTER-PLAN.md` approved.
- `examples/` exists (built with this plan per `06-examples-spec.md`); P1.10 only verifies it.

## Tasks

### P1.1 Manifest and marketplace correctness (D-E)

Confirmed against the plugin docs (code.claude.com/docs/en/plugins, plugins-reference, plugin-marketplaces): `connectors` is NOT a supported `plugin.json` field, and the `commands` and `agents` arrays REPLACE the default convention scan when present (a partial or stale array silently drops components). `skills/`, `commands/`, `agents/`, `hooks/hooks.json`, and `.mcp.json` are all auto-discovered by convention with no manifest entry needed.

1. Rewrite `.claude-plugin/plugin.json` to keep ONLY supported fields. Remove the unsupported `connectors` field and remove the redundant explicit `skills`, `commands`, and `agents` arrays (removal is safer than a partial list because the `commands`/`agents` arrays replace the scan). Keep exactly:
   - `$schema`
   - `name`: `researcher`
   - `version`: `0.2.1`
   - `description`
   - `author`: `{"name": "Marek Sokol", "email": "mareksokol98@gmail.com"}`
   - `homepage`: `https://github.com/sokolmarek/researcher`
   - `repository`: `https://github.com/sokolmarek/researcher`
   - `license`
   - `keywords`: research, academic, latex, citations, peer-review, manuscript, literature-search

   Hooks load from the auto-discovered `hooks/hooks.json` and MCP from the auto-discovered `.mcp.json`; neither needs a manifest entry. Connector docs stay as files under `connectors/` referenced by README, not the manifest.

2. Create `.claude-plugin/marketplace.json` (all paths relative, starting with `./`):

```json
{
  "name": "researcher-marketplace",
  "owner": { "name": "Marek Sokol" },
  "plugins": [
    {
      "name": "researcher",
      "source": "./",
      "description": "Academic research workflow plugin: literature search, experiment design, drafting, peer review, revision, and LaTeX/Word publication formatting."
    }
  ]
}
```

Acceptance (shippable install is the pass criterion): `/plugin install researcher@researcher-marketplace` from a clean profile completes with no warnings; local-dev path `claude --plugin-dir .` loads the plugin; both `plugin.json` and `marketplace.json` parse as valid JSON with no unsupported top-level keys; `grep -ri "yourname\|Your Name" .` (excluding `.git`) returns nothing.

### P1.2 Runtime integrity constraints in skills and agents (D-F)

The plugin root `CLAUDE.md` is contributor context and is explicitly NOT loaded at plugin runtime (docs: "A CLAUDE.md file at the plugin root is not loaded as project context ... To ship instructions that load into Claude's context, put them in a skill"). The critical constraints must therefore live where they load at runtime. References under `references/*.md` load only when a skill actually reads them, so the refusal-grade constraints must be inlined, not only linked.

1. Create `references/integrity-constraints.md` as the canonical copy of the constraints: never fabricate citations; never invent data; no em dashes in generated text; compile-check LaTeX via tectonic; validate DOCX before delivery; human-in-the-loop refusal classes (likely-fabricated citation, unverifiable data, and related). This file is the single source each skill and agent points to.
2. Add an in-body reference to `references/integrity-constraints.md` in every applicable `SKILL.md` and every applicable `agents/*.md` (those that produce cited content, data or results, LaTeX, or DOCX, or that make refusal-grade decisions: literature-search, fact-checking, citation-context, citation-management, paper-drafting, statistical-analysis, journal-formatting, word-output, peer-review, and the research, writing, and review agents).
3. Inline the load-bearing refusal-grade constraints directly in the body of each refusal-grade skill and agent (do not rely on the link alone).

Phase 4's pipeline integrity gate restates the refusal classes inline (tracked in Phase 4).

Acceptance: `references/integrity-constraints.md` exists; every applicable skill and agent both links the file and inlines the refusal-grade constraints; a grep confirms no applicable skill or agent depends on `CLAUDE.md` for a runtime constraint.

### P1.3 Claude tool guards and real git hook (D-G)

Hooks in `hooks.json` fire ONLY inside Claude's agentic loop: a PreToolUse-on-Bash matcher sees only Claude-run commands and a PostToolUse-on-Write|Edit matcher sees only Claude edits. They cannot cover a commit made from the terminal or an IDE. Name them honestly and add a real git hook for full coverage.

1. Create `hooks/hooks.json` (auto-discovered; no `plugin.json` entry) with two entries named "Claude tool guards":
   - PreToolUse matcher on `Bash` commands containing `git commit`: run `python "${CLAUDE_PLUGIN_ROOT}/scripts/citation-check-hook.py"`. The script scans staged `.tex` and `.bib` files, reusing the parse logic of `scripts/bib-validator.py`; exit code 2 blocks the commit when a `\cite{key}` has no matching bib entry.
   - PostToolUse matcher on `Write|Edit` touching `manuscript/**/*.tex`: run `python "${CLAUDE_PLUGIN_ROOT}/scripts/draft-integrity-hook.py"`, which checks `\cite`, `\ref`, `\label` consistency and prints a short integrity report (never blocks).
2. Create `scripts/citation-check-hook.py` and `scripts/draft-integrity-hook.py`: stdlib-only, Windows-safe (no shebang reliance, no bash), fast (under 2 seconds on a typical manuscript).
3. Create `scripts/install-git-hooks.py`: installs a real `.git/hooks/pre-commit` (or a pre-commit-framework `.pre-commit-config.yaml`) that invokes `citation-check-hook.py`, giving full commit coverage for terminal and IDE commits. Idempotent, and documents how to uninstall.
4. Rewrite `hooks/pre-commit-citation-check.md` and `hooks/post-draft-integrity.md` to describe the guard-versus-git-hook split: the Claude tool guard covers Claude-initiated commits and edits with exit-code-2 blocking retained, and the installed git hook covers all commits. Each doc states trigger, script, exit codes, and how to disable.

Acceptance: on Windows, the Claude guard blocks a Claude-run commit with a dangling `\cite`; the installed `.git/hooks/pre-commit` blocks the same dangling `\cite` on a terminal `git commit`; editing a `.tex` file prints the integrity report.

### P1.4 Cross-platform LaTeX compile and generated fixture (D-J)

1. Create `scripts/latex-compile.py`: Python twin of `scripts/latex-compile.sh` (locate tectonic on PATH, compile a given `.tex`, forward diagnostics, nonzero exit on failure). Keep the `.sh` for POSIX users. Update skills referencing the `.sh` (journal-formatting, manuscript-setup, latex-tables, tikz-diagrams, plotneuralnet) to prefer the `.py` invocation.
2. Generate the Phase 1 LaTeX acceptance fixture at `evals/fixtures/manuscript-min/`: run the manuscript-setup skill to produce a `manuscript/` with real section stubs and a small `library.bib`, then use that populated tree as the fixture. Do NOT compile the bare `templates/latex/article-imrad.tex`: it `\input{}`s section files that are absent standalone, so it cannot compile alone.
3. The freshness and examples harness classifies fenced LaTeX blocks as standalone (contain `\documentclass`, compile directly) versus fragment (bare `\section` or `\begin{table}`, wrapped in a harness doc before compiling), encoded in `evals/example-freshness.py` and documented in `06-examples-spec` sections 5 and 6. This file's CI (P1.5) invokes it.

Acceptance: `python scripts/latex-compile.py evals/fixtures/manuscript-min/main.tex` succeeds on Windows and produces a PDF; the bare template is never used as the compile target.

### P1.5 Basic CI (D-L)

Create `.github/workflows/validate.yml` running on push and pull_request, mirroring the checks run manually during authoring:

- Manifest and marketplace JSON validation: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` parse as JSON and match the expected plugin and marketplace shapes (supported fields only).
- JSON and markdown lint across the repo.
- Em-dash guard: fail if any tracked `.md`, `.tex`, or `.json` file contains an em dash (enforces house style).
- Example DOI resolution: resolve the example DOIs (from `examples/` and `evals/`) and fail on any unresolved.
- LaTeX freshness: run `evals/example-freshness.py` (standalone versus fragment classification, harness-wrap) to compile example LaTeX blocks and the `manuscript-min` fixture.

Acceptance: `validate.yml` is green on a clean checkout; each of the five checks runs and can fail independently.

### P1.6 Placeholder and em-dash sweep (D-J)

- `commands/new-manuscript.md` line 14: "Routes to  skill" becomes "Routes to **manuscript-setup** skill".
- `hooks/pre-commit-citation-check.md` line 4: "files in the  directory" becomes "files in the **manuscript/** directory".
- Remove em dashes from the template header comments in `templates/latex/*.tex` (`article-imrad.tex` line 2, `cover-letter.tex`, `response-to-reviewers.tex`) and anywhere else in template or generated text; replace with a colon, comma, parentheses, or two sentences.
- Repo-wide sweep: `grep -rn "  skill\|the  \|TODO\b\|TBD" --include="*.md" --include="*.json"` and fix every genuine blank; separately grep for em dashes across `.md`, `.tex`, and `.json` and remove them all.

Acceptance: the sweep grep returns no unintended blanks; the P1.5 em-dash guard finds zero em dashes repo-wide.

### P1.7 Agent frontmatter

Add YAML frontmatter to all 9 `agents/*.md`, keeping the existing prose bodies (which also carry the integrity-constraints reference added in P1.2). Format per Claude Code subagent conventions:

```yaml
---
name: code-agent
description: <one line, taken from the agent's current prose role>
model: sonnet        # or inherit
---
```

Routing (encodes CLAUDE.md's Technical Decisions, today prose-only):

| Agent | model |
|---|---|
| code-agent, visualization-agent, formatting-agent | `sonnet` |
| research-agent, writing-agent, review-agent, discovery-agent, style-agent | `inherit` |
| statistics-agent | `inherit`, prose note: delegate generated analysis code to code-agent |

Acceptance: all 9 files parse as valid YAML frontmatter; the routing table above matches the files.

### P1.8 Real MCP configuration and connector docs

1. Create `.mcp.json` at the plugin root (auto-discovered):
   - `scite`: remote server (`https://api.scite.ai/mcp` style entry per current Scite MCP docs; requires Scite account).
   - `zotero`: `uvx zotero-mcp`, env `ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE` (check zotero-mcp README for exact names at implementation time).
   - `paper-search`: `uvx paper-search-mcp` (arXiv, PubMed, bioRxiv, Semantic Scholar, Crossref and more). Stopgap for deterministic search until Phase 2 `core/` lands; keep afterwards for sources core does not cover.
2. Rewrite all 8 `connectors/*.md` to a common template:
   - **What it provides** (data, operations)
   - **Mechanism** (MCP server entry in `.mcp.json`, direct API used by `core/`, or docs-only)
   - **Install and environment variables**
   - **Used by** (list of consuming skills)
   - **Fallback when absent** (which skill behavior degrades, to what)
3. `google-scholar.md` and `mendeley.md` are explicitly docs-only (no stable free API; skills fall back to web search and manual export respectively).

Acceptance: with the servers installed, `/mcp` lists scite, zotero, paper-search as connected; every connector doc names its consuming skills and its fallback.

### P1.9 Documentation reconciliation

1. `TODO.md`: reconcile checkboxes against disk once (table-patterns and search-strategies items are done in reality), then truncate the file to roughly 5 lines pointing at `plans/` (decision D7).
2. `CLAUDE.md`: add `core/` (planned), `plans/`, `examples/`, and `references/integrity-constraints.md` to the architecture section; note that the runtime integrity constraints now live in skills and agents (not CLAUDE.md, which does not load at plugin runtime); update the build-status line to point at `plans/00-MASTER-PLAN.md`; keep the critical constraints unchanged.
3. `README.md`: real install instructions leading with `/plugin install researcher@researcher-marketplace` (and `claude --plugin-dir .` for local dev), the `.mcp.json` servers and env vars, the `scripts/install-git-hooks.py` step for full commit coverage, a short `examples/` section with links, and an honest feature-status table (what works today versus what is planned in `plans/`).

Acceptance: no checkbox anywhere contradicts the file system; README install steps reproduce on a clean profile.

### P1.10 Examples

`examples/` (15 files) is specified by `plans/06-examples-spec.md` and was authored together with this plan. In this task, re-run its acceptance checklist (DOIs resolve, LaTeX compiles via the standalone-versus-fragment harness, labels present) and fix any drift.

Acceptance: the checklist in `06-examples-spec.md` section 6 passes.

### P1.11 Smoke trigger test

Manual triggering pass over all 28 skills: 2 prompts per skill (56 prompts). Keep the prompt table in this file's appendix as it is filled in. Also test installation via `/plugin install researcher@researcher-marketplace` from a clean profile (shippable path) and `claude --plugin-dir .` (dev path).

Record every miss (skill did not trigger, or wrong skill triggered) verbatim; these seed `evals/triggers.yaml` in Phase 4.

Acceptance: at least 90 percent of prompts trigger the intended skill; installation from a clean profile via the marketplace succeeds with no warnings.

## Files created

- `.claude-plugin/marketplace.json`
- `references/integrity-constraints.md`
- `hooks/hooks.json`
- `scripts/citation-check-hook.py`
- `scripts/draft-integrity-hook.py`
- `scripts/install-git-hooks.py`
- `scripts/latex-compile.py`
- `.mcp.json`
- `evals/fixtures/manuscript-min/` (generated fixture: `main.tex`, section stubs, `library.bib`)
- `.github/workflows/validate.yml`

## Files modified

- `.claude-plugin/plugin.json`
- `commands/new-manuscript.md`
- `hooks/pre-commit-citation-check.md`, `hooks/post-draft-integrity.md`
- all 9 `agents/*.md` (frontmatter plus integrity-constraints reference)
- all 8 `connectors/*.md`
- applicable `skills/*.md` (integrity-constraints reference and inline refusal-grade constraints; `latex-compile.sh` to `.py` references)
- `templates/latex/*.tex` (em-dash removal from header comments)
- `TODO.md`, `CLAUDE.md`, `README.md`

## Phase acceptance checklist

- [ ] `plugin.json` keeps only supported fields (no `connectors`, no `skills`/`commands`/`agents` arrays); `marketplace.json` valid (P1.1)
- [ ] `/plugin install researcher@researcher-marketplace` from a clean profile succeeds with no warnings; `claude --plugin-dir .` works for dev (P1.1, P1.11)
- [ ] `references/integrity-constraints.md` exists; every applicable skill and agent references it in-body and inlines the refusal-grade constraints (P1.2)
- [ ] Claude tool guards renamed; real `.git/hooks/pre-commit` installed by `scripts/install-git-hooks.py`; both block a dangling `\cite` on Windows (P1.3)
- [ ] Generated fixture at `evals/fixtures/manuscript-min/` compiles via `scripts/latex-compile.py` on Windows; bare template not used (P1.4)
- [ ] `.github/workflows/validate.yml` green: manifest+marketplace JSON validation, JSON/markdown lint, em-dash guard, DOI resolution, LaTeX freshness (P1.5)
- [ ] No placeholder strings and no em dashes repo-wide, including template header comments (P1.6)
- [ ] 9 agents with valid frontmatter and correct model routing (P1.7)
- [ ] `/mcp` lists the three servers; 8 connector docs follow the template (P1.8)
- [ ] TODO.md is a pointer; CLAUDE.md and README current (P1.9)
- [ ] Examples checklist green (P1.10)
- [ ] Trigger smoke test at 90 percent or better, misses recorded (P1.11)
- [ ] Version bumped to 0.2.1 in `plugin.json`

## Risks and fallbacks

- The `commands` and `agents` arrays REPLACE the default convention scan: rely on auto-discovery (P1.1) so a stale array cannot silently drop components. Manifest field support is confirmed against current docs, so schema drift risk is low; re-check the docs if a load warning appears.
- Two-layer hook coverage: the Claude tool guard cannot see terminal or IDE commits, so `scripts/install-git-hooks.py` is required for full coverage (P1.3). Document both as complementary.
- Scite MCP requires a subscription for full access: the connector doc must state the free-tier behavior and the fallback (core CLI or paper-search-mcp).
- Hook false positives (for example, `\cite` inside comments): keep hook logic conservative; the blocking hook fires only on exact dangling-key cases, everything else reports without blocking.

## Appendix: smoke trigger prompt table (fill during P1.11)

| # | Skill | Prompt | Triggered? | Notes |
|---|---|---|---|---|
| 1 | literature-search | "Find recent papers on self-supervised learning for ECG classification" | | |
| 2 | literature-search | "Do a systematic literature search on transformer models for arrhythmia detection" | | |
| ... | (2 per skill, 56 total; fill in during execution) | | | |
