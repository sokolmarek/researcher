# Phase 2: Deterministic Retrieval and Verification Core

Version target: 0.3.0
Effort: 5-7 focused sessions (largest phase)
Depends on: Phase 1 complete.

## Goal

Build `core/`, a small, tested, Windows-first Python package (`researcher_core`) that gives skills deterministic multi-source literature retrieval and citation verification through a JSON-emitting CLI. This replaces "ask the LLM to web-search" with reproducible API retrieval, which `research/research1.md` identifies as the decisive gap in prompt-only research suites.

Design principles: keyless by default (polite-pool email env vars), optional API keys only add coverage, every command emits JSON with `--json`, all tests run offline against recorded fixtures, live calls are an opt-in marker. Schema validation is a test-time concern (see below): `jsonschema` is a DEV dependency, so the base runtime install stays minimal.

This phase also delivers the two evidence capabilities Phase 3 depends on: four-state citation verification with a calibrated threshold set, and minimal open-access full-text extraction. The heavy semantic RAG stack (embeddings, vector store, GROBID, reranking) is explicitly out of scope and stays in Phase 5.

## Package layout

```
core/
├── pyproject.toml            # [build-system] hatchling
│                             # [project] researcher-core 0.1.0
│                             #   base runtime deps: httpx, rapidfuzz, platformdirs (nothing else)
│                             # [project.scripts]
│                             #   researcher-core = "researcher_core.cli:main"
│                             # [project.optional-dependencies]
│                             #   dev      = [pytest, jsonschema, respx (or vcrpy)]
│                             #   fulltext = [pymupdf, selectolax]
├── README.md                 # dev setup (uv sync, uv run), env vars, cache location,
│                             # and the no-uv fallback: pip install -e "core/[fulltext]"
├── researcher_core/
│   ├── __init__.py
│   ├── __main__.py           # delegates to cli.main so `python -m researcher_core` works
│   ├── model.py              # CSLRecord dataclass (CSL-JSON canonical) + normalizers
│   ├── cache.py              # SQLite response cache in platformdirs user_cache_dir,
│   │                         # TTL per source (default 7 days), --no-cache override
│   ├── connectors/
│   │   ├── __init__.py       # registry: name -> connector class
│   │   ├── base.py           # BaseConnector: search / get_by_id / resolve_doi /
│   │   │                     # get_citations / get_references / get_oa_pdf
│   │   ├── openalex.py       # polite pool via OPENALEX_MAILTO; exposes is_retracted
│   │   ├── crossref.py       # CROSSREF_MAILTO; update-to (retraction/correction) metadata
│   │   ├── semantic_scholar.py  # optional S2_API_KEY; TLDRs, citation graph
│   │   ├── arxiv.py          # Atom API
│   │   ├── pubmed.py         # E-utilities; optional NCBI_API_KEY
│   │   └── unpaywall.py      # UNPAYWALL_EMAIL; OA location resolution
│   ├── search.py             # concurrent fan-out (httpx async), per-source error
│   │                         # isolation: one failing source never fails the query
│   ├── dedupe.py             # DOI exact match first, then normalized-title
│   │                         # similarity (rapidfuzz token_sort_ratio >= 0.90)
│   ├── rank.py               # composite: relevance, recency, citation count
│   ├── graph.py              # forward/backward citation traversal (OpenAlex,
│   │                         # optionally S2), depth-limited, deduplicated
│   ├── verify.py             # four-state existence gate, see below
│   ├── retract.py            # OpenAlex is_retracted + Crossref update-to sweep
│   ├── fulltext.py           # minimal OA PDF/HTML text extraction + heuristic section
│   │                         # split; returns {section, text, char_offsets}.
│   │                         # Requires the [fulltext] extra. NOT the semantic RAG stack.
│   ├── provenance.py         # append-only provenance.jsonl event model:
│   │                         # append(event) / prisma() derives PRISMA counts by aggregation
│   ├── bib.py                # .bib parse/emit (port parse logic from
│   │                         # scripts/bib-validator.py; emit from CSLRecord)
│   └── cli.py                # python -m researcher_core <cmd>, argparse, --json
├── schemas/
│   ├── record.schema.json               # CSLRecord
│   ├── verification-report.schema.json  # four-state verdict + per-source outcomes
│   └── provenance-event.schema.json     # versioned event record {schema_version,event_id,ts,type,payload}
├── CALIBRATION.md            # chosen verify thresholds + gold-subset outcomes (P2.5)
└── tests/
    ├── fixtures/             # recorded JSON responses per connector (no live calls
    │   │                     # in the default run)
    │   └── verify-gold/      # stratified gold subset for threshold calibration (P2.5)
    ├── test_model.py
    ├── test_dedupe.py
    ├── test_verify.py
    ├── test_fulltext.py
    ├── test_provenance.py
    ├── test_bib.py
    └── test_cli.py           # golden-output tests over fixtures; validates every --json
                              # output against core/schemas/*.json using jsonschema (dev dep)
```

## Packaging and schema-validation strategy (P2.1)

`core/pyproject.toml` is a runnable, installable package:

- `[build-system]` uses `hatchling`.
- `[project.scripts]` exposes `researcher-core = "researcher_core.cli:main"`, so an installed environment has a `researcher-core` console command; `researcher_core/__main__.py` delegates to `cli.main` so `python -m researcher_core` works too.
- Base runtime dependencies are only `httpx`, `rapidfuzz`, `platformdirs`. Nothing else is required to run the CLI.
- `[project.optional-dependencies]` defines `dev = [pytest, jsonschema, respx (or vcrpy)]` and `fulltext = [pymupdf, selectolax]`.

Schema-validation strategy: `jsonschema` is a DEV dependency, not a runtime one. Every `--json` CLI output is validated against `core/schemas/*.json` inside the test suite. The runtime does NOT hard-depend on `jsonschema`, keeping the base install minimal. Contributors without `uv` install via `pip install -e "core/[fulltext]"` (or `pip install -e core/` for the base runtime).

## Verification gate semantics (verify.py)

For each reference (from a `.bib` file or a single DOI/title), query OpenAlex, Crossref, Semantic Scholar, arXiv (whichever apply). Each queried source produces a per-source outcome:

- `confirmed`: the source resolves the reference and its metadata matches within thresholds.
- `negative`: the query succeeded but returned no match.
- `source_error`: timeout, rate limit, 5xx, or network failure, so no clean answer was obtained.

The report retains every per-source outcome. The reference-level verdict is exactly one of four states:

1. `verified`: at least 2 sources returned `confirmed`, best-match normalized-title similarity is at least 0.70, publication year is within plus or minus 1, and the first-author surname overlaps.
2. `mismatch`: a source resolves the DOI/ID but the metadata disagrees beyond thresholds (likely a wrong DOI or a mangled entry).
3. `unresolvable`: ALL queried sources returned `negative` and none returned `confirmed`, a true negative lookup. This is the ONLY refusal-grade "likely fabricated" state.
4. `inconclusive`: evidence is too thin to decide, for example exactly one source returned `confirmed` (a legitimate single-index paper) OR any source returned `source_error` so a clean negative cannot be asserted. This is NOT refusal-grade.

Refusal-grade consumers (Phase 3 citation-audit, the Phase 4 integrity gate) may act ONLY on `unresolvable` or `mismatch`, NEVER on `inconclusive`. Thresholds (title 0.70, year plus or minus 1, surname overlap) are calibrated on a gold subset in task P2.5, and that calibration MUST complete before any Phase 3 refusal-grade decision. The FNR below 0.15 and FPR below 0.10 targets from `research/research1.md` are validated against the enlarged Phase 4 gold set.

## CLI surface

All commands accept `--json` (machine output; validated against `core/schemas/` in the test suite). Default output is a compact human table.

| Command | Does |
|---|---|
| `search "<query>" [--sources a,b,c] [--limit N] [--since YEAR]` | fan-out, dedupe, rank; returns CSL-JSON list |
| `get <doi-or-arxiv-or-openalex-id>` | single record, normalized |
| `verify-bib <library.bib>` | four-state verification over every entry, per-source outcomes retained |
| `verify-ref "<doi-or-title>"` | four-state verification for one reference |
| `citations <id> [--depth 1]` | forward citations via graph.py |
| `references <id>` | backward references |
| `oa-pdf <doi>` | OA location cascade: Unpaywall, then arXiv, then PMC |
| `fulltext <doi-or-url> [--sections]` | resolve OA PDF/HTML, extract text, heuristic section split; returns `{section, text, char_offsets}` (requires the `[fulltext]` extra) |
| `retractions <library.bib>` | retraction/correction sweep |
| `provenance append <event-json> \| prisma` | append an event to `provenance.jsonl`; `prisma` derives PRISMA counts by aggregation |

Standard skill invocation snippet (documented once in `references/core-cli.md`, referenced by skills):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<query>" --sources openalex,crossref,arxiv --limit 25 --json
```

## Tasks

### P2.1 Scaffolding, model, cache, packaging
`core/pyproject.toml` with `[build-system]` hatchling, base deps `httpx`/`rapidfuzz`/`platformdirs`, `[project.scripts]` `researcher-core = "researcher_core.cli:main"`, and `[project.optional-dependencies]` `dev` and `fulltext` as specified above. Add `researcher_core/__main__.py` delegating to `cli.main`. `model.py` CSLRecord with normalizers (DOI lowercasing, title NFC normalization and whitespace collapse, author name splitting), `cache.py` SQLite keyed by (source, endpoint, params-hash) with TTL.
Acceptance: `uv run --project core python -c "import researcher_core"` and `python -m researcher_core --help` both work on Windows; a fresh `pip install -e core/` exposes the `researcher-core` console script; `jsonschema` is absent from the base install (runtime imports never require it); cache round-trips a record.

### P2.2 Connectors (one sub-task per source)
Order: OpenAlex and Crossref first (they alone satisfy the 2-index existence gate), then arXiv, Semantic Scholar, PubMed, Unpaywall. Each implements the `BaseConnector` contract, returns CSLRecord, respects rate limits (OpenAlex/Crossref politeness headers, S2 key header), and has recorded fixtures.
Acceptance per connector: fixture test green; live smoke (opt-in `-m live`) returns plausible results for "self-supervised ECG".

### P2.3 Fan-out search, dedupe, rank
`search.py` concurrent fan-out with per-source error isolation; `dedupe.py` (DOI exact, then title similarity 0.90); `rank.py` composite score.
Acceptance: a fixture query with planted duplicates (same DOI from two sources; same title, no DOI) collapses correctly; a source raising an exception yields results from the remaining sources plus a warning field.

### P2.4 Four-state verification and retraction
`verify.py` implements the four-state gate above: per-source outcomes in `{confirmed, negative, source_error}` aggregated into a reference verdict in `{verified, mismatch, unresolvable, inconclusive}`, with per-source outcomes retained in the report. `retract.py` via OpenAlex `is_retracted` and Crossref `update-to`.
Acceptance: a fixture bib with 3 real entries, 1 mangled entry, and 1 invented entry yields `verified`/`mismatch`/`unresolvable` respectively; a fixture where a queried source times out yields `inconclusive` (never `unresolvable`); a single-index-only fixture yields `inconclusive`; a known-retracted fixture DOI is flagged.

### P2.5 Threshold calibration on a gold subset
Assemble `core/tests/fixtures/verify-gold/`, a small stratified gold subset covering `verified`/`mismatch`/`unresolvable`/`inconclusive` with edge cases (preprint later published, title truncation, author-initials-only, single-index paper, valid DOI with wrong metadata). Run `verify` over it, tune the title-similarity, year, and surname-overlap thresholds, and record the chosen values plus the resulting per-class outcomes in `core/CALIBRATION.md`. This task MUST complete before Phase 3 makes any refusal-grade decision.
Acceptance: `core/CALIBRATION.md` records the chosen thresholds and the outcome breakdown on the gold subset, including FNR and FPR for the refusal-grade states (`unresolvable`, `mismatch`); the committed thresholds are the ones `verify.py` uses.

### P2.6 Minimal OA full-text extraction
`fulltext.py`: given a DOI or OA URL, resolve an OA PDF/HTML through the OA cascade (reuse `oa-pdf`), extract text (`pymupdf` for PDF; `selectolax` or the stdlib `html.parser` for HTML), split into sections by heading heuristics, and return a list of `{section, text, char_offsets}`. Gated behind the `[fulltext]` extra. This is minimal extraction to unblock Phase 3 claim-anchoring; it is explicitly NOT the semantic RAG stack (embeddings, vector store, GROBID, reranking stay in Phase 5). Wire the `fulltext` CLI subcommand.
Acceptance: on a recorded OA PDF fixture and an OA HTML fixture, extraction returns non-empty sections with monotonically increasing `char_offsets`; when the `[fulltext]` extra is not installed, the command exits with a clear "install core[fulltext]" message instead of a traceback.

### P2.7 Citation graph
`graph.py` forward/backward traversal, depth-limited (default 1, max 2), deduplicated against the seed set.
Acceptance: fixture traversal returns expected neighbor sets; a cycle in fixtures does not loop.

### P2.8 Provenance event ledger
`provenance.py` maintains an append-only `provenance.jsonl` (JSON Lines). Each event record is `{schema_version, event_id, ts, type, payload}`. Phase 2 emits three event types: `retrieval` (a fan-out search with per-source hit counts and filters), `record_lineage` (which raw source records produced a canonical CSLRecord), and `dedup_decision` (each merge or removal with its reason). Timestamps (`ts`) are passed in by the caller, not self-generated, so runs stay deterministic. `provenance prisma` DERIVES PRISMA flow counts by aggregating events (identified = sum of retrieval hits; deduplicated = `dedup_decision` removals; screened/included are added by later phases). Append-only JSONL avoids the concurrent-write corruption of a single rewritten JSON file.
Acceptance: after two `retrieval` events plus `dedup_decision` events, `provenance prisma` derives the correct identified and deduplicated numbers; every appended line validates against `provenance-event.schema.json`.

### P2.9 CLI and schemas
`cli.py` wiring all commands (including `fulltext` and `provenance append|prisma`); JSON schemas authored (`record.schema.json`, `verification-report.schema.json`, `provenance-event.schema.json`); every `--json` output validated in tests via `jsonschema` (dev dependency).
Acceptance: `test_cli.py` golden tests pass; every `--json` output validates against its schema; invalid arguments exit 2 with usage text.

### P2.10 Test suite
pytest, offline by default (fixtures via `respx`/`vcrpy`), `-m live` marker for the optional canary run. Target: every module has direct tests; CI-runnable on Windows and Linux.
Acceptance: `uv run --project core pytest core/tests` green offline on Windows.

### P2.11 Wrap existing scripts
Rewrite `scripts/bib-validator.py`, `scripts/citation-check-hook.py`, `scripts/draft-integrity-hook.py` as thin wrappers that prefer core (via `uv run`) and fall back to their existing stdlib logic when uv or core is unavailable.
Acceptance: hooks behave identically with and without core installed (core path adds index verification, fallback path keeps local-only checks).

### P2.12 CI workflow
Add `.github/workflows/core.yml`: `ruff` + `mypy` + `pytest` (offline fixtures) on a Windows AND Linux matrix, plus an optional scheduled nightly live-API canary that runs `pytest -m live`.
Acceptance: the offline job is green on both `windows-latest` and `ubuntu-latest`; the nightly `-m live` canary is scheduled and does not gate the offline matrix.

### P2.13 CLI reference doc
Write `references/core-cli.md`: full command reference (including `fulltext` and `provenance append|prisma`), env vars (OPENALEX_MAILTO, CROSSREF_MAILTO, UNPAYWALL_EMAIL, optional S2_API_KEY, NCBI_API_KEY), the standard invocation snippet, JSON output shapes, the `[fulltext]` extra, and failure modes. Skills link here instead of inlining API detail (keeps SKILL.md under 500 lines, decision D6).
Acceptance: every CLI command documented with one worked example.

## Files created

Everything under `core/` (see layout), plus `references/core-cli.md` and `.github/workflows/core.yml`.

## Files modified

- `scripts/bib-validator.py`, `scripts/citation-check-hook.py`, `scripts/draft-integrity-hook.py` (thin-wrapper rewrite, P2.11)
- `.claude-plugin/plugin.json` (version 0.3.0)
- `CLAUDE.md` (core/ moves from planned to present)

## Phase acceptance checklist

- [ ] `python -m researcher_core` and the `researcher-core` console script both run; base install pulls only httpx, rapidfuzz, platformdirs (no jsonschema at runtime)
- [ ] `search` returns deduplicated CSL-JSON from at least 3 sources on a live smoke query
- [ ] `verify-bib` yields `verified` on real entries, `mismatch` on a wrong-DOI entry, `unresolvable` on an invented entry, and `inconclusive` on a single-index or source-error case; refusal-grade acts only on `unresolvable`/`mismatch`
- [ ] Threshold calibration (P2.5) is committed in `core/CALIBRATION.md` before Phase 3 begins
- [ ] `fulltext` extracts sectioned text with `char_offsets` from an OA PDF fixture and an OA HTML fixture
- [ ] `provenance.jsonl` is append-only and `provenance prisma` derives correct PRISMA counts by aggregation
- [ ] `retractions` flags a known-retracted DOI
- [ ] Every `--json` output validates against `core/schemas/*.json` in tests
- [ ] `.github/workflows/core.yml` (ruff + mypy + pytest) green on the Windows and Linux matrix; live canary scheduled
- [ ] pytest green offline on Windows; live canary green when opted in
- [ ] Hooks and bib-validator work with and without core present
- [ ] `references/core-cli.md` complete

## Risks and fallbacks

- Rate limits and API instability: SQLite cache reduces repeat traffic; per-source error isolation keeps searches usable when one API is down (and a downed source yields `source_error` -> `inconclusive`, never a false `unresolvable`); live tests are opt-in so CI never depends on external uptime.
- Windows async quirks (httpx/asyncio event-loop policy): pin the selector policy where needed; test on Windows first, not last.
- Scope creep toward RAG: Phase 2 full-text extraction is deliberately minimal (OA text plus heuristic section split for claim-anchoring). The semantic RAG stack (embeddings, vector store, GROBID, reranking) is Phase 5 only.
- uv absent on user machines: everything degrades per P2.11; README documents the `pip install -e "core/[fulltext]"` (and base `pip install -e core/`) fallback.
