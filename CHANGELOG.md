# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-07-14

The evidence kernel. `core/` exists now, so the sentence "a deterministic retrieval core is planned"
is retired from this repository. Citation verification is no longer a promise backed by a DOI lookup:
it is a tested Python package with published benchmarks, measured on gold sets built from real DOIs,
and it is honest about the axis where it is weak.

Every number below was measured by running the benchmark suite offline from snapshots, on the date of
this release. None of them is a target or an estimate. Reproduce them with:

```
uv run --project core python evals/run_axes.py
uv run --project core python evals/run_triggers.py
```

### Added

**`core/` (`researcher_core`): a deterministic evidence kernel.** A small Python package invoked
through a JSON-emitting CLI. Skills never import it; they shell out to it and read its JSON. It does
the reproducible work a language model should not be asked to do: multi-source retrieval,
deduplication, per-axis citation verification, publication-status checks, open-access full-text
extraction, lexical passage retrieval, and an append-only provenance ledger.

- **Eight connectors:** OpenAlex, Crossref, DataCite, arXiv, Semantic Scholar, PubMed, Unpaywall,
  OpenCitations. Keyless by default; the polite-pool mail variables cost nothing and buy rate limit.
- **Content-addressed snapshot record and replay.** Every raw API response is recorded and addressed
  by the SHA-256 of its canonicalized body, so tests and benchmarks replay from a fixed snapshot set
  instead of from whatever the live indexes happen to say today. The governing rule is that **a missing
  snapshot in replay mode raises loudly rather than quietly going live**: an offline suite that could
  silently reach the network would have numbers that mean nothing. This is tested directly, by deleting
  a stored snapshot and confirming a no-flag run reports the item as skipped and never re-fetches it.
  Determinism is claimed only for replay from a fixed snapshot set, configuration, and parser version,
  and is never claimed for live calls, because live indexes change.
- **The install is optional.** The plugin works without `uv` and without core, with the 0.2.0
  stdlib behavior.

**Per-axis verification, and the four axes reported side by side.** The old single "is this citation
good" verdict is gone. A reference can be perfectly `verified` on identity and still be `retracted` on
status, and folding those into one number destroys both.

| Axis | Verdicts |
|---|---|
| (a) reference identity | `verified`, `mismatch`, `unresolvable`, `inconclusive` |
| (b) publication status | `current`, `corrected`, `retracted`, `expression-of-concern` |
| (c) claim faithfulness | `supported`, `partial`, `contradicted`, `insufficient-passage` |
| (d) accessibility | `full-text`, `abstract-only`, `unavailable` |

**The refusal-grade asymmetry, stated once.** Only `unresolvable` and `mismatch` can accuse anyone.
`inconclusive` never does, and no consumer may act on it: it means a source was rate-limited or only
one index holds the paper, so a clean negative could not be asserted. The kernel would rather miss a
fabricated citation than accuse a real one, because telling an honest author that a paper they read and
cited correctly does not exist is the worst thing this system can do, and a missed catch merely leaves
them where they were without the tool.

**Benchmarks, with gold sets built from real, live-harvested DOIs.** Six gold sets, all snapshot-backed
so every run replays offline: identity (150 tuples), status (121 DOIs), accessibility (105),
faithfulness (104 claim-passage pairs), dedup (210 labeled pairs), and retrieval (55 known-item
queries). Measured:

| Axis | Result | 95% Wilson |
|---|---|---|
| (a) identity, refusal-grade false positive | **0/100** | [0.000, 0.037] |
| (a) identity, refusal-grade false negative | 0/50 | [0.000, 0.071] |
| (a) identity, accuracy | 136/150 (0.907) | [0.849, 0.944] |
| (b) status, accuracy | 121/121 (1.000) | [0.969, 1.000] |
| (d) accessibility, accuracy | 104/105 (0.990) | [0.948, 0.998] |
| dedup, pair accuracy | 210/210 (1.000) | [0.982, 1.000] |
| dedup, false merge | 0/100 | [0.000, 0.037] |

Zero refusal-grade false positives in 100 real references, and every one of the 25 invented references
caught. A per-class n of 25 cannot certify an error rate below 0.10 even at 25/25, and
`evals/BENCHMARKS.md` says so for each number rather than letting anyone quote it as if it could.

**Axis (c) is the weak one, and it is weak on purpose.** M2 ships the LEXICAL floor (BM25 retrieval
plus token-overlap and polarity heuristics), and a lexical baseline cannot read:

```
coverage (fraction answered)     78/104   0.750
accuracy over ALL items          67/104   0.644
accuracy over ANSWERED items      41/78   0.526
correct abstentions               26/26   1.000
passage anchoring                 74/78   0.949
AURC (mean risk over the curve)            0.380
```

`partial` recall is 0.269: an overstatement reuses nearly every token of the passage it overstates, so
12 of the 26 `partial` claims were called `supported`. That is the method's failure mode, printed
rather than buried. The deferred semantic layer's start trigger is exactly this measured rate, so the
number is not an embarrassment to be minimized, it is the trigger condition. The one direction that is
clean is the one that must be: no claim over a document without full text was ever emitted as an answer
(26/26 correct abstentions). Accuracy over answered items is reported only next to its coverage,
because an oracle that abstains on everything has perfect accuracy on what it answers and is worthless,
and the risk-coverage curve in `evals/BENCHMARKS.md` prices that trade instead of hiding it.

**Provenance (D19).** An append-only SQLite event ledger. Timestamps are caller-supplied and never
self-generated, which is what keeps replays deterministic. PRISMA flow counts are DERIVED by
aggregating events, never stored as a mutable shape, so the counts cannot drift away from the events
that produced them. JSONL is an export format, not the write path.

**`evals/BENCHMARKS.md`**, which records what the kernel actually does, including where it is red.

### Fixed

Three defects the benchmarks found in the kernel before any user did. A benchmark that finds bugs and
does not report them is decoration.

**An ordinary colon in a title could help manufacture a fabrication verdict.** This is the one that
mattered. Connector queries were not sanitized, and DataCite's search parser reads Lucene syntax, so a
title containing a colon (`Attention:` ...) was parsed as a field name and the search returned **zero
hits**. A zero-hit answer is a CLEAN NEGATIVE, and a clean negative is the only outcome that builds
toward `unresolvable`, the refusal-grade verdict. So a punctuation mark that appears in an enormous
fraction of real paper titles was silently pushing honest references toward "likely fabricated". A
truncated title with an unbalanced parenthesis threw outright (HTTP 400). Every search now sanitizes
its query.

**A source could convict a DOI it had never resolved.** The title-search fallback let an index that
does not hold a DOI find a similar-looking paper by title and report `doi_mismatch` against it. Two
such non-holding indexes could outvote a genuine confirmation and produce a refusal-grade `mismatch` on
a real reference. A Zenodo DOI is not Crossref's to disagree about. Now a source may only report
`doi_mismatch` if it actually resolved that DOI itself: a record found by title search can support a
confirmation but can never convict one, because an index that does not hold a DOI has no opinion about
it. An exact-prefix truncation rule was added alongside it. Refusal-grade false positives went from
3/99 to 0/100, and mismatch and unresolvable recall both stayed at 1.000, so no catch was traded away
to buy it.

**Publication status resolved source disagreements by coin flip.** Crossref's specific `update-type`
now outranks OpenAlex's coarse `is_retracted` boolean, and disagreements between sources are surfaced
rather than silently resolved. Six gold labels were also corrected: they were papers that received an
expression of concern and were LATER RETRACTED, so the harvest had captured the first notice rather
than the current status. Axis (b) is now 121/121.

**PMC's bot interstitial was read as an article.** The OA cascade treats the "Checking your browser"
page as a miss instead of extracting it as a one-segment full-text document.

### Changed

- **Skill descriptions sharpened so overlapping skills discriminate.** Pooled trigger recall went from
  84.1% to 100.0% (145/145, 95% Wilson [97.4%, 100.0%]), and the pooled false-trigger rate went DOWN,
  from 24.1% to 6.9% (6/87, [3.2%, 14.2%]), so the recall was not bought by grabbing prompts that
  belong to other skills. Both pooled gates pass. Per-skill rows are diagnostics only: at n=5 they
  cannot certify anything, and the runner refuses to pretend otherwise.
- **`scripts/bib-validator.py`, `scripts/citation-check-hook.py` and `scripts/draft-integrity-hook.py`
  are now thin wrappers** that prefer core and fall back to their stdlib logic when `uv` or core is
  absent. The plugin never hard-fails for want of `uv`.
- The BibTeX brace-aware tokenizer moved into the kernel (`researcher_core.bib`) and gained a torture
  fixture exercising every construct in one file.

### Known limitations

Stated here because the alternative is pretending otherwise.

- **Axis (c) is a lexical baseline**, with the numbers above. It is not a claim-verification engine,
  and its coverage of 0.750 is the deferred semantic layer's start trigger, not an incidental
  weakness.
- **OpenAlex meters full-text search on a daily budget.** Re-recording the whole retrieval gold set
  in one `--record` pass exhausts it, so `--record-missing` (fill mode) exists to fetch only the
  snapshots that are actually absent. This is an operational note about refreshing snapshots, not a
  gap in the shipped set: all 55 retrieval queries are recorded and score offline today.
- The kernel does **not** do semantic RAG. Embeddings, vector stores, GROBID, and reranking beyond an
  optional lexical extra are deliberately out of scope and stay deferred post-1.0.
- Multi-index verification is wired into the hooks for reporting, but the hard block on retracted
  citations arrives with the M3 compile gate, not here.

## [0.2.0] - 2026-07-14

Release correctness. Everything the README "what works today" table claims is now true when
exercised from a clean profile, and the guards that are supposed to keep it true actually check what
their names say they check. No architectural change: the deterministic retrieval core is still
planned, not shipped.

### Fixed

**Three guards that reported green while checking nothing.** The "fake form-field guard" only matched
an old markdown form-widget syntax, so it could not detect a command file with a missing or
mis-titled inputs section, and two such files were passing it. The tectonic install step was named
"checksum verified" and verified nothing: release 0.16.9 publishes no `SHA256SUMS` asset, so the
fetch was `|| true`-guarded and the verification branch was dead code. The release zip guard asserted
eleven leaf files but never asserted `skills/` or `.claude-plugin/`, so an over-matching exclude
pattern could have shipped an archive with no plugin in it.

**The Word-output skill told the model to run pandoc.** `skills/word-output/SKILL.md` described a
LaTeX-to-DOCX conversion path through pandoc, which is not in this repo and never has been, and its
frontmatter description (the field the plugin system routes on) advertised "Full DOCX with tracked
changes and comments" against a script that generates none of those. It now documents the real
`templates/word/build-docx.js` contract, and the seven capabilities it does not have are listed
together under a "Planned, not implemented" heading. The same overstatement is corrected in the
revision-management, cover-letter, response-to-reviewers, and latex-tables skills, and in three
README rows.

**The citation guard blocked commits it had no business blocking.** It scanned every `.tex` file in
the index whenever any `.tex` or `.bib` was touched, so a dangling citation in one manuscript blocked
a commit that only touched a different, unrelated manuscript. Scanning is now scoped to the
manuscript roots the commit actually touches. It also read bib keys with its own regex rather than
the brace-aware parser, which meant an `@comment{foo, bar}` block yielded a phantom key `foo` that
silently satisfied a `\cite{foo}` real BibTeX would reject; it now shares the parser, and strips
comments.

**Agent model routing was prose, not mechanism.** Five of the nine agents carried no `skills:`
preload at all. `visualization-agent` asserted that it routes code to a Sonnet subagent and plans
figures on Opus, when its own frontmatter pins it to Sonnet and none of its skills fork; the same
false claim appeared in `statistics-agent`. The prose now describes what actually happens.

**Journal lookup presented guesses as hits.** A query for a journal absent from the database returned
a different journal's full profile at exit 0 with no caveat (the script's own docstring example did
this). Fuzzy matches are now labeled as such, and separated from exact hits in JSON output.

**The PRISMA example could not be told from a real search.** Its flow counts carried no provenance
label, while the surrounding prose simultaneously called them illustrative and claimed the provenance
record held "the exact numbers for the run". They are illustrative, they are now labeled so, and the
docs page that asserted them as fact and called the search "reproducible" is corrected to match.

Also fixed: a hard 404 from the agents reference page to a skills catalog that did not exist,
`build-docx.js` dying with a raw `MODULE_NOT_FOUND` stack trace on a fresh clone, and two command
files missing their inputs section.

### Added

- `--check-duplicates` on `scripts/bib-validator.py`, so duplicate detection is selectable like every
  other check rather than always-on.
- Named per-entry DOI verdicts (`confirmed`, `no-doi`, `resolution-failed`): a resolved DOI is now
  stated as confirmed rather than passing in silence.
- `scripts/tests/fixtures/torture.bib`: nested braces, quoted values with commas and braces, bare
  macros, compact `}}` termination, and `@comment` / `@preamble` / `@string` blocks, all in one file.
- An explicit `Style:` invocation contract on the five visualization-family skills, with the
  precedence order stated once: explicit `Style:` line, then trigger phrase, then journal inference
  from `config.yaml`, then `default`.
- A skills catalog page in the docs reference section, covering all 29 skills.
- CI guards for the things that had none: honest command inputs, agent `skills:` preloads whose names
  must resolve, and unbacked `pandoc` / `docx-js` capability claims.
- 24 new tests (56 to 80), including the two the plan named and neither of which existed: a
  staged-only dangling citation with a clean worktree, and an unrelated manuscript that must not
  block.

### Changed

- The two `nature` example figures now use the palette `references/figure-styles.md` actually
  defines, so copying an example reproduces the shipped preset. Restyle only: every plotted number is
  unchanged, which matters because that data is the shared source of truth for the paired t-tests in
  `latex-results-table.md` and the confidence intervals in `response-to-reviewers.md`.
- CI pins Python in every job that uses it, enforces the committed npm lockfile with `npm ci`, and
  verifies the tectonic download against a pinned digest.
- The release workflow runs the test suite before it can publish a tag.

### Note on versioning

This release is 0.2.0, not the 0.2.2 the roadmap names. The 0.2.x numbers in the roadmap predate the
history rewrite that collapsed the never-public 0.2.x entries into 0.1.0, so shipping 0.2.2 as the
successor to 0.1.0 would imply two patch releases that never existed.

## [0.1.0] - 2026-07-14

First public release.

### Added

**The plugin.** 29 skills, 9 agents, and 11 namespaced slash commands (`/researcher:new-manuscript`
and friends) covering the research pipeline: brainstorming, literature search, research gaps,
experiment design, statistical analysis, implementation, manuscript drafting, visualization, citation
management, peer review, revision handling, journal and conference selection, and LaTeX or Word
formatting. Installs with `/plugin install researcher@researcher-marketplace`.

**Integrity you can check, not just promises.** The rules (never fabricate a citation, never invent
data) are inlined into every skill that produces cited content, and they are backed by mechanical
checks:

- A citation commit guard. It blocks a commit whose `\cite{...}` keys have no matching BibTeX entry,
  including the case where a bibliography entry is deleted out from under a citation that is already
  committed. It validates the prospective commit tree and scopes citations to the bibliographies each
  manuscript actually declares. `scripts/install-git-hooks.py` installs it as a real git pre-commit
  hook, so it also covers commits made from a terminal or an IDE.
- BibTeX validation (`scripts/bib-validator.py`): a brace-aware parser, CrossRef DOI resolution,
  title similarity and first-author matching, retraction flags, and duplicate detection. A 404 and a
  network failure are reported differently, because they mean different things.
- LaTeX compile checks that work with whatever TeX you have installed: tectonic, TeX Live, MiKTeX, or
  MacTeX (`scripts/latex_engine.py` resolves the engine; `--engine` or `LATEX_ENGINE` overrides).

**Figure style presets.** `default`, `nature`, and `ieee`, defined once in
`references/figure-styles.md` and shared by the visualization, TikZ, PlotNeuralNet, table, and
figure-suggestion skills. Ask for Nature style and the sizing, typography, and palette change; your
data does not.

**Word output.** `templates/word/build-docx.js` (Node plus the `docx` library) generates a formatted
DOCX from `sections/*.md`: title page, numbered headings, paragraphs, lists.

**Codex support.** `scripts/install-codex-skills.py` installs all 29 skills into `~/.agents/skills`
(or a repository's `.agents/skills`), rewriting plugin-relative paths so they resolve outside the
plugin and dropping the Claude-only routing that Codex has no concept of. Codex implements the same
open agent-skills standard, so the skills themselves port directly.

**Worked examples.** 15 examples with real, DOI-verified output and rendered figures, plus an eval
(`evals/example-freshness.py`) that resolves every DOI and compiles every LaTeX block, so the
examples cannot rot silently. The single fake citation in the set is seeded deliberately, and the
eval fails if it ever starts resolving.

**Documentation.** An Astro site with a cookbook and a per-skill reference, deployed to GitHub Pages,
plus a README that states plainly which capabilities work today and which are planned.

### Known limitations

Stated here because the alternative is pretending otherwise:

- Citation verification today means DOI resolution and retraction flags against CrossRef. Multi-index
  verification with four-state verdicts (verified, mismatch, unresolvable, inconclusive) is the next
  milestone, not a shipped feature.
- DOCX tracked changes, comments, and table emission are specified in
  `templates/word/article-imrad.md` but are not implemented.
- External reviewer models (OpenAI, Gemini, Ollama) are a documented integration point with no
  implementation. Peer review runs Claude's multi-persona panel.
- The journal database carries 16 publisher and journal profiles. Anything else is looked up from the
  publisher's author guidelines.
- Text fetched from papers is untrusted input, and hardened prompt-injection handling is planned work.
  See [SECURITY.md](SECURITY.md).

[0.1.0]: https://github.com/sokolmarek/researcher/releases/tag/v0.1.0
