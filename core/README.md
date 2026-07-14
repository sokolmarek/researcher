# researcher-core

The deterministic evidence kernel behind the Researcher plugin. Skills call it through a
JSON-emitting CLI; it does the reproducible work that a language model should not be asked
to do: multi-source literature retrieval, deduplication, per-axis citation verification,
publication-status checks, open-access full-text extraction, passage retrieval, and an
append-only provenance ledger.

Status: under construction (milestone M2). This README documents what exists today.

## What "deterministic" means here

Replayable given three things: a source snapshot, a configuration, and a parser version.
Identical inputs under those three produce byte-identical `--json` output. Determinism is
never claimed for live calls, because live indexes change: OpenAlex adds a citation, a
publisher fixes a title, a paper gets retracted. So every raw API response is recorded as a
content-addressed snapshot, the test suite and the benchmarks replay exclusively from
snapshots, and a scheduled live canary reports drift without gating CI.

The rule that makes this real: **replaying a request with no stored snapshot raises
`SnapshotMissingError`.** It never falls back to a live call. If the offline suite could
quietly reach the network, its numbers would mean nothing.

## Install

With uv (recommended, and what skills use):

```
uv sync --project core
uv run --project core python -m researcher_core --help
```

Without uv:

```
pip install -e core/                # base runtime
pip install -e "core/[fulltext]"    # plus OA PDF and HTML extraction
pip install -e "core/[dev]"         # plus the test, lint, and type toolchain
```

A base install exposes a `researcher-core` console command and pulls exactly three runtime
dependencies: `httpx`, `rapidfuzz`, `platformdirs`. `jsonschema` is a development
dependency only; schema validation is a test-time concern, and no runtime import needs it.

The plugin never hard-fails when uv or core is absent: the stdlib-only scripts in
`scripts/` keep working on their own.

## Extras

| Extra | Pulls | Needed for |
|---|---|---|
| `dev` | pytest, jsonschema, ruff, mypy, respx | tests, lint, type gate |
| `fulltext` | pymupdf, selectolax | OA PDF and HTML text extraction |
| `rerank` | rank-bm25 | optional lexical reranking over the BM25 passage index |

Embeddings, vector stores, and GROBID are deliberately out of scope.

## Environment variables

Keyless by default. The mail variables put requests in the polite pool of each API, which
buys higher rate limits and costs nothing.

| Variable | Purpose |
|---|---|
| `OPENALEX_MAILTO` | polite-pool contact for OpenAlex |
| `CROSSREF_MAILTO` | polite-pool contact for Crossref |
| `UNPAYWALL_EMAIL` | required by the Unpaywall API |
| `S2_API_KEY` | optional; raises Semantic Scholar rate limits |
| `NCBI_API_KEY` | optional; raises PubMed E-utilities rate limits |

Kernel behavior:

| Variable | Purpose |
|---|---|
| `RESEARCHER_CORE_SNAPSHOT_MODE` | `live` (default), `record`, or `replay` |
| `RESEARCHER_CORE_SNAPSHOT_DIR` | override the snapshot store root |
| `RESEARCHER_CORE_CACHE_DIR` | override the response-cache directory |
| `RESEARCHER_CORE_CACHE_TTL` | override the default cache TTL, in seconds |
| `RESEARCHER_CORE_NO_CACHE` | set to `1` to bypass the response cache entirely |

## Two stores, and why they are separate

**The response cache** is a TTL'd SQLite database in the platformdirs user cache directory
(7-day default TTL, per-source overrides). Its only job is to keep the kernel polite to
public APIs during ordinary use. It never feeds the evaluation suite.

| Platform | Location |
|---|---|
| Windows | `%LOCALAPPDATA%\researcher\researcher-core\Cache\responses.sqlite3` |
| macOS | `~/Library/Caches/researcher-core/responses.sqlite3` |
| Linux | `~/.cache/researcher-core/responses.sqlite3` |

**The snapshot store** is content-addressed JSON, one directory per source, and it comes in
two flavors: the eval store in the repository at `core/tests/snapshots/`, which is the only
thing offline tests and benchmark runs read, and a runtime store in the user cache
directory, written by `--record` during ordinary use. Runtime snapshots never feed evals.

## Modes

| Mode | What it does |
|---|---|
| `live` | ordinary use: consult the cache, call the API, write no snapshot |
| `record` | `--record`: call the API (bypassing the cache read) and write the snapshot |
| `replay` | tests and eval runners: snapshots only; a missing snapshot raises, loudly |

## Development

```
uv sync --project core
uv run --project core python -m pytest core/tests -q     # offline; replay is the default
uv run --project core ruff check core
uv run --project core mypy core/researcher_core
```

Tests run offline and never touch the user's real cache or snapshot directories: the shared
fixtures redirect both into a temporary directory and force replay mode. Live tests are an
opt-in marker (`-m live`) and are deselected by default.

Windows is a first-class target (D5): every path goes through `pathlib`, cache and snapshot
roots go through `platformdirs`, snapshot filenames are 64-character hex digests, snapshot
writes are atomic (`os.replace`) with LF line endings, and CI runs the suite on Windows and
Linux.
