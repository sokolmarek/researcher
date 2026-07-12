# Researcher Upgrade: Master Plan

Status: approved
Created: 2026-07-12
Supersedes: `TODO.md` (which becomes a pointer to this directory in Phase 1)
Evidence base: `research/research1.md` (SOTA analysis of academic-research AI tooling)

## 1. Vision

Researcher stays a Claude Code plugin. Skills, commands, and agents remain the primary user experience. What changes is what sits underneath them: a deterministic Python retrieval and verification engine (`core/`) that skills invoke through a JSON-emitting CLI, real MCP wiring for interactive and licensed sources, runtime integrity constraints carried inside the skills themselves (not the plugin-root `CLAUDE.md`, which does not load at plugin runtime), commit-time citation guards, worked examples, and an evaluation suite backed by CI.

The division of labor, stated once and reused everywhere:

- **Claude (skills, agents, commands):** judgment, synthesis, writing, review.
- **`core/` CLI:** reproducible retrieval, deduplication, four-state citation verification, retraction checks, minimal OA full-text extraction, event-model provenance. Deterministic, testable, offline-testable.
- **MCP servers:** interactive and licensed data sources (Scite Smart Citations, the user's Zotero library) plus stopgap search coverage until `core/` lands, with a thin stable-core FastMCP server exposing the engine to non-Claude hosts from Phase 4.

This is the HYBRID decision (D1 below): not a greenfield pivot, not a plugin-only content pass.

## 2. Current state (verified inventory, 2026-07-12)

| Layer | Count | State |
|---|---|---|
| Skills (`skills/*/SKILL.md`) | 28 | Complete, 100-290 lines each, valid frontmatter with trigger phrases |
| Agents (`agents/*.md`) | 9 | Prose only, no YAML frontmatter, model routing not machine-readable |
| Commands (`commands/*.md`) | 11 | Thin but present; `new-manuscript.md` has a blank "Routes to  skill" placeholder |
| Connectors (`connectors/*.md`) | 8 | Three-line descriptive stubs, no real MCP configuration |
| Hooks (`hooks/*.md`) | 2 | Descriptive only, not registered, not executable; `pre-commit-citation-check.md` has a blank placeholder |
| References (`references/*.md`) | 10 | Substantive |
| Templates (`templates/`) | 8 | Complete (5 LaTeX, 3 Word specs) |
| Scripts (`scripts/`) | 5 | Substantive, stdlib-only Python plus one bash script, not in manifest |
| Manifest (`.claude-plugin/plugin.json`) | 1 | Placeholder author and homepage; nonstandard `"connectors"` key |
| `TODO.md` | 1 | Stale: Phase 14 (testing, packaging) untouched; several checked items contradict disk |
| `plans/` | | This directory |
| `examples/` | 15 | Worked examples (created together with this plan, see `06-examples-spec.md`) |

Known defects to fix in Phase 1: the two blank placeholders, manifest placeholders, the nonstandard `connectors` manifest key, a missing `.claude-plugin/marketplace.json`, agent frontmatter, connector stubs, unwired hooks, stale TODO, no Windows twin for `latex-compile.sh`.

## 3. What we adopt, defer, and reject from the research

`research/research1.md` analyzed the incumbent skill suite (`Imbad0202/academic-research-skills`, "ARS") and the SOTA landscape (PaperQA2, FutureHouse, STORM, GPT Researcher, LangChain Open Deep Research, Elicit, Consensus, Scite, zotero-mcp, paper-search-mcp).

### Adopt (re-implemented as original code, ideas credited in README)

| Idea | Source pattern | Lands in |
|---|---|---|
| Deterministic multi-source retrieval (fan-out, dedup, rank) | PaperQA2, paper-search-mcp | Phase 2 |
| Four-state citation verification (verified / mismatch / unresolvable / inconclusive) | ARS verification gate | Phase 2 |
| Retraction checks (OpenAlex `is_retracted`, Crossref update-to) | PaperQA2, zotero-mcp | Phase 2 |
| Citation-graph traversal for discovery | PaperQA2, FutureHouse Owl | Phase 2 |
| Minimal OA full-text extraction (OA cascade, heuristic section split) | PaperQA2 parsing | Phase 2 |
| Event-model provenance ledger (append-only, PRISMA counts derived) | ARS Material Passport, PRISMA | Phase 2 |
| Three-layer claim-faithfulness anchors (quote, page, section) over OA full text | ARS claim audit | Phase 3 |
| Contradiction mining | FutureHouse ContraCrow, Scite contrast tallies | Phase 3 |
| Structured extraction tables | Elicit | Phase 3 |
| Literature monitoring (diff-on-rerun) | FutureHouse monitoring | Phase 3 |
| Staged pipeline with a mandatory integrity gate | ARS academic-pipeline | Phase 4 |
| Research passport (event-model provenance consumed by `/submit-ready`) | ARS Material Passport | Phase 4 |
| Should-trigger and shouldn't-trigger skill evals, gold-set gate metrics (FNR below 0.15, FPR below 0.10) | ARS calibration, skill-creator pattern | Phase 4 |
| Human-in-the-loop by default, automation opt-in | ARS philosophy | Phases 3-4 |

### Defer (Phase 5, optional, with explicit start triggers)

- Verified semantic RAG over full text (GROBID, chunking, embeddings, vector store, RCS retrieval, reranking, span-anchored answers), built on the Phase-2 full-text extraction
- LiteLLM multi-provider model routing

(PyPI packaging of `researcher-core` and a thin stable-core FastMCP server are no longer deferred: they are scheduled in Phase 4, see D13.)

### Reject

- Relicensing or license changes: the repo stays MIT (D2). The research's "start greenfield under Apache-2.0" recommendation addressed forking CC BY-NC ARS code, which does not apply here because nothing is forked.
- Abandoning the plugin form factor: rejected by the binding HYBRID decision.
- Copying any ARS text or code: ARS is CC BY-NC. Ideas only, credited in README (Phase 4 docs task).

## 4. Target architecture

```
User
 │  natural language / slash commands
 ▼
Claude Code + Researcher plugin
 ├── commands/ (15 after Phase 4: 11 existing + systematic-review,
 │             verify-citations, watch-topic, research-pipeline)
 ├── skills/   (34 after Phase 4: judgment, synthesis, writing, review;
 │             refusal-grade integrity constraints inlined in-skill from
 │             references/integrity-constraints.md, not plugin-root CLAUDE.md)
 ├── agents/   (9, frontmatter-routed: sonnet for code/viz/formatting)
 └── hooks/hooks.json (citation check on commit, draft integrity on edit)
        │                                   │
        │ uv run --project core             │ MCP protocol (.mcp.json)
        ▼                                   ▼
 core/ researcher_core CLI            MCP servers
 ├── search (fan-out, dedupe, rank)   ├── scite (Smart Citations, licensed)
 ├── verify-bib / verify-ref          ├── zotero-mcp (user library, write-back)
 │     four-state verdict:            └── paper-search-mcp (stopgap until
 │     verified / mismatch /              core/ covers its sources)
 │     unresolvable / inconclusive
 ├── citations / references (graph)
 ├── oa-pdf + fulltext (OA cascade, extract, heuristic section split)
 ├── retractions
 └── provenance (append-only event ledger; PRISMA counts derived)
        │ HTTPS, keyless polite pool by default
        ▼
 OpenAlex · Crossref · Semantic Scholar · arXiv · PubMed · Unpaywall · OpenCitations

 Phase 4 also publishes researcher-core to PyPI and stands up a thin FastMCP
 server over the STABLE core subset (search_papers, get_paper, verify_citations,
 export_bibliography, download_oa) for non-Claude hosts.
```

## 5. Phases

| Phase | Goal (one line) | Key deliverables | Depends on | Version | Effort |
|---|---|---|---|---|---|
| 1 | Fix and finish what exists, on a correct manifest | Manifest + `.claude-plugin/marketplace.json`, runtime integrity constraints in skills (`references/integrity-constraints.md`), accurately scoped hooks + real `.git/hooks/pre-commit`, generated populated LaTeX fixture, basic CI (`validate.yml`), placeholder + em-dash sweep, agent frontmatter, connector docs, `.mcp.json`, examples verification | (this plan) | 0.2.1 | 3-4 sessions |
| 2 | Deterministic retrieval, verification, and evidence core | Runnable `core/` package + CLI, event-model provenance (`provenance.jsonl`), four-state verification + gold-subset calibration, minimal OA full-text extraction, 6 connectors, dedupe, retractions, offline tests, Windows/Linux CI (`core.yml`) | 1 | 0.3.0 | 5-7 sessions |
| 3 | Core-powered and new skills | 6 skill upgrades, 5 new skills (systematic-review, citation-audit, contradiction-detection, extraction-tables, literature-monitoring), 3 new commands; ends at 33 skills / 14 commands, only after Phase 2 evidence capabilities pass acceptance | 2 | 0.4.0 | 4-5 sessions |
| 4 | Orchestration, integrity, evals, docs, interoperability | `/research-pipeline` with mandatory integrity gate, research passport (event model), stronger eval suite, README rewrite, CHANGELOG, PyPI packaging of `researcher-core`, thin stable-core FastMCP server, release CI (`release.yml`); ends at 34 skills / 15 commands | 3 | 0.5.0 | 3-4 sessions |
| 5 | Deferred: semantic RAG and LiteLLM | Verified RAG (GROBID, embeddings, vector store, RCS retrieval, reranking) on the Phase-2 full text, LiteLLM multi-provider routing; only on explicit start triggers, see `05-...md` | 4 | 1.0.0 | not scheduled |

Examples (`examples/`, spec in `06-examples-spec.md`) were built alongside this plan and double as regression references: Phase 4's freshness eval re-validates them.

## 6. Decision log

- **D1 HYBRID architecture.** Keep the plugin as primary UX; add a deterministic Python core invoked by skills. Rationale: the research shows retrieval delegated to LLM WebSearch is the decisive weakness of prompt-only suites, but a full pivot (PyPI-first, MCP-server-first) abandons the plugin's working UX for months. Hybrid captures the differentiator without the rewrite. The interoperability surface the research urged (PyPI packaging plus a thin MCP server over the stable core) is not dropped, only scheduled: it lands in Phase 4 once the core stabilizes, so the plugin stays the primary UX while non-Claude hosts get access soon after. See D13.
- **D2 License stays MIT.** Nothing is forked from ARS, so the CC BY-NC blocker does not apply. Ideas are re-implemented and credited.
- **D3 Python dependencies via uv.** `core/` gets its own `pyproject.toml` (base deps kept to `httpx`, `rapidfuzz`, `platformdirs`; optional `[fulltext]` extra adds `pymupdf`, `selectolax`). Skills invoke `uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core ...` so users need only uv; it resolves the environment on first run, identically on Windows and POSIX. Fallback documented: `pip install -e "core/[fulltext]"`. Existing stdlib-only scripts keep working when uv or core is absent, so the plugin never hard-fails.
- **D4 CSL-JSON is the canonical record format.** Every connector normalizes to it; BibTeX and RIS are emitters. This matches citeproc tooling and keeps a single dedupe and verify surface.
- **D5 Windows-first.** The maintainer develops on Windows. No bash-only tooling in hooks or skill snippets; `latex-compile.sh` gets a Python twin; cache paths via `platformdirs`; `${CLAUDE_PLUGIN_ROOT}` instead of relative paths; core tests must pass on Windows (and the CI matrix pins Windows plus Linux).
- **D6 SKILL.md files stay under 500 lines.** Upgrades swap hand-written API walkthroughs for short core-CLI calls; the full CLI reference lives once in `references/core-cli.md`. Current maximum is 290 lines, so there is headroom, and the cap is a per-task acceptance check in Phase 3.
- **D7 plans/ is the single task tracker.** TODO.md drifted from disk (checked items missing, done items unchecked). Phase 1 reconciles it once, then truncates it to a pointer here. Two live task lists are one too many.
- **D8 Examples contain only real, resolvable citations.** Every DOI, author, year, tally, and benchmark number in `examples/` comes from an actual retrieval at authoring time. The single permitted fake is the seeded `(synthetic, for demonstration)` bib entry in the citation-audit example, which exists precisely to be flagged. Volatile facts carry "verified as of" tags. Enforced by `evals/example-freshness.py` from Phase 4.
- **D9 Four-state citation verification.** Each queried source resolves to `confirmed`, `negative` (query succeeded, no match), or `source_error` (timeout / rate limit / 5xx / network). The reference-level verdict is one of `verified` (>= 2 sources confirmed, title similarity >= 0.70, year +/-1, first-author surname overlap), `mismatch` (a source resolves the id but metadata disagrees beyond thresholds), `unresolvable` (ALL queried sources returned a clean negative and none confirmed), or `inconclusive` (thin or dirty evidence, e.g. one confirming source or any `source_error`). Only `unresolvable` and `mismatch` are refusal-grade; `inconclusive` is NEVER refusal-grade. Thresholds are calibrated on a gold subset in Phase 2 BEFORE Phase 3 makes any refusal-grade decision.
- **D10 Event-model provenance.** Provenance is an append-only `provenance.jsonl` (JSON Lines; SQLite acceptable) of `{schema_version, event_id, ts, type, payload}` records with `type` in {retrieval, record_lineage, dedup_decision, screening_decision, artifact_hash, review, gate}. PRISMA counts are DERIVED by aggregating events (`provenance prisma`), never stored as a single mutable shape, which avoids concurrent-JSON corruption. Schema: `core/schemas/provenance-event.schema.json`. Phase 2 emits retrieval / record_lineage / dedup_decision; Phase 3 adds screening_decision; Phase 4 adds review / gate / artifact_hash.
- **D11 Minimal OA full-text in Phase 2, semantic RAG in Phase 5.** `core/researcher_core/fulltext.py` (resolve OA PDF/HTML via the cascade, extract with pymupdf or an HTML parser, heuristic section split, return `{section, text, char_offsets}`) lands in Phase 2 behind the optional `[fulltext]` extra. Embeddings, vector store, GROBID, and reranking stay Phase 5. Phase 3 claim-faithfulness, contradiction-detection, and extraction-tables anchor against this OA full text; when it is unavailable a claim degrades to abstract level with verdict `unverified_no_fulltext` and MUST NOT be emitted as clean or faithful.
- **D12 Runtime integrity constraints live in skills, not CLAUDE.md.** The plugin-root `CLAUDE.md` is contributor context and is explicitly NOT loaded at plugin runtime. `references/integrity-constraints.md` is the canonical copy (never fabricate citations; never invent data; no em dashes; compile-check LaTeX via tectonic; validate DOCX; human-in-the-loop refusal classes). Every applicable SKILL.md and agent references it in-body AND inlines the load-bearing refusal-grade constraints; the Phase 4 integrity gate restates the refusal classes inline. Phase 1 creates the file and wires the references.
- **D13 Interoperability surface scheduled in Phase 4.** PyPI packaging of `researcher-core` and a thin FastMCP server over the STABLE core subset (search_papers, get_paper, verify_citations, export_bibliography, download_oa) ship in Phase 4 after the core stabilizes in Phase 2. Only the heavy semantic layer (full RAG, LiteLLM) defers to Phase 5. This honors the research's "lead with MCP + PyPI" push while keeping the plugin as primary UX.
- **D14 marketplace.json plus CI.** Ship `.claude-plugin/marketplace.json` (name `researcher-marketplace`, plugin `researcher`, source `./`) so `/plugin install researcher@researcher-marketplace` works from a clean profile. GitHub Actions CI lands in phases: `validate.yml` in Phase 1 (manifest + marketplace JSON validation, JSON/markdown lint, em-dash guard, example DOI resolution + LaTeX freshness), `core.yml` in Phase 2 (ruff + mypy + pytest on a Windows and Linux matrix, optional nightly live-API canary), `release.yml` in Phase 4 (tag -> build -> PyPI publish via OIDC trusted publishing -> GitHub Release from CHANGELOG).

## 7. Global acceptance criteria

The upgrade is done (0.5.0) when all of the following hold:

1. Plugin installs cleanly via `/plugin install researcher@researcher-marketplace` from a fresh profile with no manifest warnings and no placeholder strings anywhere in the repo (local-dev install via `claude --plugin-dir .` also works).
2. `python -m researcher_core search` returns deduplicated CSL-JSON from at least 3 sources on a live query; `verify-bib` classifies a seeded fake reference as `unresolvable`; `fulltext` extracts and section-splits an OA source; pytest passes offline on Windows and Linux.
3. All 34 skills trigger correctly on at least 90 percent of the eval prompt set; the verification gold set meets FNR below 0.15 and FPR below 0.10.
4. `/research-pipeline` completes a dry run on the examples topic, producing an event-model research passport, and `/submit-ready` refuses a "ready" verdict when the integrity gate has not run.
5. Every DOI in `examples/` resolves and every fenced LaTeX block compiles under tectonic (freshness eval green).
6. README documents architecture, install (including MCP servers, the FastMCP surface, and uv), and credits ARS ideas; CHANGELOG covers 0.2.1 through 0.5.0; CI (`validate.yml`, `core.yml`, `release.yml`) is green.

## 8. Out of scope

- Anything in Phase 5 (semantic RAG, LiteLLM routing) until its start trigger fires.
- Google Scholar and Mendeley API integrations (docs-only connectors; no stable free API worth the maintenance).
- Autonomous end-to-end paper generation. The pipeline keeps human checkpoints by default; `--auto` style flags arrive only after gate metrics hold on the gold set (Phase 4).
- Non-English literature workflows, institutional access integration (EZproxy etc.), and reference-manager backends other than Zotero (Mendeley stays docs-only).
