# Phase 4: Orchestration, Integrity, Evals, Docs, Interoperability

Version target: 0.5.0
Effort: 4-5 focused sessions
Depends on: Phase 3 complete.

## Goal

Tie the skills into a staged pipeline with a mandatory integrity gate, make the event-model provenance ledger (the research passport) a first-class artifact that `/submit-ready` enforces via its DERIVED gate state, stand up the evaluation suite with calibrated thresholds, ship the scheduled interoperability surface (a PyPI package plus a thin stable-core MCP server) and its release CI, and finish the public-facing documentation. This phase takes the plugin from 33 to 34 skills and 14 to 15 commands. After it the plugin is 0.5.0: feature-complete for the hybrid scope, measured, packaged, and honestly documented. The heavy semantic layer (full RAG plus LiteLLM routing) stays scheduled for Phase 5.

## Prerequisites

- Phase 3 delivered 33 skills and 14 commands, with core-powered evidence capabilities (OA full-text extraction, four-state verification, calibrated thresholds) passing their acceptance.
- `core/researcher_core/` is a runnable, offline-tested package (Phase 2, D-D) with the `researcher-core` console script.
- `core/schemas/provenance-event.schema.json` exists and already carries the `retrieval` / `record_lineage` / `dedup_decision` (Phase 2) and `screening_decision` (Phase 3) event types.
- `references/integrity-constraints.md` exists (Phase 1) as the canonical refusal-grade constraint source.

## Tasks

### P4.1 Research pipeline command and skill (skills 33 -> 34, commands 14 -> 15)

Create `commands/research-pipeline.md` and `skills/research-pipeline/SKILL.md`. This is the 34th skill and the 15th command (Phase 3 ended at 33 skills and 14 commands).

Target paths:
- `commands/research-pipeline.md`
- `skills/research-pipeline/SKILL.md`

Stages: Plan (question, scope, protocol) -> Retrieve (core fan-out, ledger) -> Synthesize (outline, evidence mapping) -> Draft (paper-drafting skill) -> Review (peer-review skill, multi-persona) -> **Integrity Gate** -> Format (journal-formatting / word-output).

Gate contents (mandatory, non-skippable):
- Citation-audit existence gate: acts ONLY on `unresolvable` and `mismatch` reference verdicts (four-state verification), NEVER on `inconclusive`.
- Retraction sweep.
- Temporal check: no citation dated after the manuscript's claimed knowledge date; flags "cited as forthcoming" entries.
- Claim-faithfulness audit on flagged claims: never emits a faithful verdict for a claim whose source full text was unavailable (that claim stays `unverified_no_fulltext`).

A failed gate returns the pipeline to Draft or Review with the findings.

The SKILL.md body inlines the load-bearing refusal constraints and points to `references/integrity-constraints.md` (per D-F, references load only when read, so refusal-grade text is also inlined).

Every stage appends events to the passport (P4.2): Review appends `review` events, the gate appends a `gate` event (pass/fail plus findings), and draft/figure/table outputs append `artifact_hash` events. Stages never rewrite prior records.

Human checkpoint after every stage by default: the pipeline presents stage output and waits. A `--auto` note is documented but disabled until the P4.3 gold-set metrics hold (FNR below 0.15 and FPR below 0.10, each reported with its 95% Wilson confidence interval), matching the master plan's human-in-the-loop decision.

Acceptance: a dry run on the examples topic completes Plan through Format on a short manuscript and produces a passport (P4.2) carrying `review`, `gate`, and `artifact_hash` events; a deliberately broken citation forces the `gate` event to record a fail verdict and routes the pipeline back to Draft or Review with the findings.

### P4.2 Research passport (event-model provenance)

The research passport IS the append-only event ledger introduced in Phase 2, not a new artifact. It lives at `manuscript/provenance.jsonl` (JSON Lines; SQLite is an acceptable alternative) and validates against `core/schemas/provenance-event.schema.json`.

Target paths:
- `manuscript/provenance.jsonl` (produced at runtime, not committed)
- `commands/submit-ready.md` (modified consumer)

Each record has the shape `{schema_version, event_id, ts, type, payload}`, where `ts` is stamped by the caller (scripts do not self-generate time). `type` is one of `retrieval`, `record_lineage`, `dedup_decision`, `screening_decision`, `artifact_hash`, `review`, `gate`.

Phase 4 contributes the three remaining event types:
- Pipeline stages and the Claude tool guards / real git hook append `artifact_hash` (draft, figure, and table content hashes), `review` (per-persona peer-review verdicts), and `gate` (integrity-gate pass/fail with findings). All appends are append-only, which avoids concurrent-JSON corruption.

Derived state (nothing is stored as a mutable field):
- PRISMA counts are DERIVED by aggregating events (`identified` = sum of `retrieval` hits, `deduplicated` = `dedup_decision` removals, `screened`/`excluded`/`included` = `screening_decision` events carrying a reason). `researcher-core provenance prisma` performs the aggregation.
- The gate state is the verdict of the latest `gate` event, DERIVED by folding the `gate` event stream.

Modify `commands/submit-ready.md`: `/submit-ready` reads the DERIVED gate state and refuses a "ready" verdict when no `gate` event exists or the latest `gate` verdict is a fail. Its report includes the gate summary and the derived PRISMA counts when `screening_decision` events are present.

Acceptance: `/submit-ready` on a manuscript whose passport has no `gate` event refuses with a clear message; after a passing `gate` event it proceeds; `researcher-core provenance prisma` returns PRISMA counts computed purely from the event stream.

### P4.3 Evaluation suite (`evals/`)

Target paths:
- `evals/README.md`
- `evals/triggers.yaml`
- `evals/run_triggers.py`
- `evals/verification-gold.yaml`
- `evals/run_verification.py`
- `evals/example-freshness.py`

Contents:
- `evals/README.md`: what each eval measures, how to run it, and the thresholds (per-skill recall floor, aggregate recall, false-trigger rate, FNR/FPR with confidence intervals).
- `evals/triggers.yaml`: per skill, 5 should-trigger and 3 shouldn't-trigger prompts, roughly 272 cases across 34 skills (34 x (5 + 3)), seeded from the Phase 1 smoke table and the Phase 3 appendix. The new `research-pipeline` skill is included.
- `evals/run_triggers.py`: headless runner (`claude -p` per prompt) that measures which skill actually fired via DETERMINISTIC skill-invocation telemetry (a logged record of the fired skill), not manual inspection. It computes per-skill recall, aggregate recall, and the false-trigger rate on the shouldn't-trigger prompts. Manual spot-run instructions are documented for environments without headless access.
- `evals/verification-gold.yaml`: 60 to 100 gold claim-citation tuples with expected verdicts, STRATIFIED across the six verdict states (`verified`, `mismatch`, `unresolvable`, `inconclusive`, `retracted`, `unfaithful`), including edge cases: preprint later published, title truncation, author-initials-only, single-index paper, and valid DOI with wrong metadata. The positive class is defined as "citation is problematic" (`unresolvable` OR `mismatch` OR `unfaithful` OR `retracted`); `verified` and `inconclusive` are the negative class.
- `evals/run_verification.py`: scores the gold set and reports a confusion matrix, macro-averaged precision and recall per class, and 95% Wilson confidence intervals; it states FNR and FPR each with its Wilson CI.
- `evals/example-freshness.py`: extracts every DOI and URL from `examples/` and re-resolves them (Crossref for DOIs, HTTP status for URLs); classifies each fenced LaTeX block as STANDALONE (contains `\documentclass`, compiles directly) or FRAGMENT (bare `\section` / `\begin{table}` / section body), wraps fragments in a harness document before compiling, then compiles every block with tectonic; exits nonzero on any failure. The harness wrap matches the examples-spec sections 5 and 6 verification method.

Acceptance: trigger eval passes with per-skill recall at or above 0.80 for every skill AND aggregate recall at or above 0.90, with the false-trigger rate reported; gold-set FNR below 0.15 and FPR below 0.10 (point estimates and their 95% Wilson CIs reported), plus the confusion matrix and macro precision/recall; example freshness eval green.

### P4.4 Documentation

Target paths:
- `README.md`
- `CHANGELOG.md`
- `CLAUDE.md`
- `.claude-plugin/plugin.json`

Contents:
- `README.md` rewrite: architecture section (the hybrid diagram from the master plan), install (plugin via `/plugin install researcher@researcher-marketplace`, `uv` / `pip install researcher-core`, MCP servers, env vars), a pipeline walkthrough with the examples topic, an eval results table (recall floors, false-trigger rate, FNR/FPR with CIs), a note that the PyPI package and thin MCP server are the scheduled interoperability surface (D-H), and a credits section acknowledging idea provenance (ARS integrity-gate and passport concepts, PaperQA2 retrieval patterns, STORM synthesis, Elicit extraction; no code copied).
- `CHANGELOG.md`: Keep a Changelog format, backfilled 0.2.0 through 0.5.0.
- `CLAUDE.md`: final structure update (core/, evals/, plans/, examples/, 34 skills, 15 commands), bumping the stated skill count from 28 to 34 across the phases.
- Version 0.5.0 in `plugin.json`.

Acceptance: a newcomer can install and run the pipeline from `README.md` alone; `CHANGELOG.md` matches git history; `CLAUDE.md` states 34 skills and 15 commands.

### P4.5 Interoperability surface: PyPI package and thin stable-core MCP server (D-H) plus release CI (D-L)

Scheduled into Phase 4 now that the core stabilized in Phase 2. Phase 5 keeps ONLY the heavy semantic layer (GROBID, embeddings, vector store, RCS retrieval, reranking, and LiteLLM multi-provider routing).

Target paths:
- `core/pyproject.toml` (modified: PyPI metadata, `mcp` extra, `researcher-mcp` script)
- `core/researcher_core/mcp_server.py`
- `.mcp.json` (modified: register the thin stable-core stdio server)
- `.github/workflows/release.yml`

Contents:
- PyPI packaging of `researcher-core`: `core/pyproject.toml` gains PyPI-ready metadata (distribution name `researcher-core`, license, classifiers, project URLs, long description from `README.md`), building on the hatchling backend from Phase 2.
- Thin FastMCP server `core/researcher_core/mcp_server.py` exposing ONLY the STABLE core subset: `search_papers`, `get_paper`, `verify_citations`, `export_bibliography`, `download_oa`. Each tool is a thin re-export of an existing core function (no new logic). Add `[project.optional-dependencies] mcp = [fastmcp]` and `[project.scripts] researcher-mcp = "researcher_core.mcp_server:main"`. Register the stdio server in `.mcp.json` so plugin users get it too.
- `.github/workflows/release.yml`: on a version tag, build the sdist and wheel, publish to PyPI via OIDC trusted publishing (no stored token), then create a GitHub Release with notes drawn from `CHANGELOG.md`.

Acceptance: `pip install researcher-core` exposes both the `researcher-core` and `researcher-mcp` entry points (validated against TestPyPI in a dry run); the FastMCP server answers the 5 stable tools over stdio; tagging `v0.5.0` runs `release.yml` end to end (build -> PyPI publish via OIDC -> GitHub Release from CHANGELOG).

## Files created

- `commands/research-pipeline.md`, `skills/research-pipeline/SKILL.md`
- `evals/README.md`, `evals/triggers.yaml`, `evals/run_triggers.py`, `evals/verification-gold.yaml`, `evals/run_verification.py`, `evals/example-freshness.py`
- `CHANGELOG.md`
- `core/researcher_core/mcp_server.py`
- `.github/workflows/release.yml`

## Files modified

- `commands/submit-ready.md` (reads the DERIVED gate state from the event ledger)
- `README.md`, `CLAUDE.md` (34 skills, 15 commands), `.claude-plugin/plugin.json` (version 0.5.0)
- `hooks/hooks.json` and hook scripts (append `gate` and `artifact_hash` events to the passport)
- `core/pyproject.toml` (PyPI metadata, `mcp` optional extra, `researcher-mcp` script)
- `.mcp.json` (register the thin stable-core stdio server)

## Phase acceptance checklist

- [ ] Pipeline dry run completes Plan through Format; the passport gains `review`, `gate`, and `artifact_hash` events; a broken citation records a fail `gate` event and routes back to Draft or Review
- [ ] `/submit-ready` reads the DERIVED gate state and refuses when no `gate` event exists or the latest `gate` verdict is a fail
- [ ] Trigger eval: per-skill recall at or above 0.80 for every skill AND aggregate at or above 0.90, with the false-trigger rate reported, across 34 skills (about 272 cases), measured via deterministic skill-invocation telemetry
- [ ] Verification gold set of 60 to 100 tuples: confusion matrix, macro precision/recall per class, and 95% Wilson CIs reported; FNR below 0.15 and FPR below 0.10 with their CIs
- [ ] Example freshness eval green: standalone blocks compile directly, fragments compile inside a harness document
- [ ] `researcher-core` published via `release.yml` (OIDC trusted publishing); the thin FastMCP server exposes the 5 stable tools; `.mcp.json` registers it
- [ ] README, CHANGELOG, and CLAUDE.md current (34 skills, 15 commands); version 0.5.0

## Risks and fallbacks

- Headless trigger runs may be slow or unavailable: `run_triggers.py` is optional; the yaml plus the deterministic skill-invocation telemetry is the deliverable and can be spot-checked manually.
- Gold-set curation is real work (60 to 100 tuples with verified ground truth, stratified across six verdicts): reuse the examples bibliography, known-retracted papers from Retraction Watch coverage, and deliberately mangled DOIs (valid DOI with wrong metadata) to bound curation.
- Wilson CIs widen on small per-class counts: keep roughly 10 or more tuples per verdict so the 95% interval stays informative.
- PyPI trusted publishing needs a one-time OIDC publisher configuration on PyPI: document the setup in `release.yml` comments and dry-run against TestPyPI first.
- Thin MCP server drift: the server re-exports only the 5 stable core functions with no new logic, so it stays a thin wrapper and moves with core versioning.
- Pipeline length versus context limits: each stage summarizes into the passport, so later stages read the passport events rather than full transcripts.
