# Examples Specification (normative)

This file is the spec for `examples/`. The examples were authored together with this plan; this spec stays normative for regenerating or extending them. Phase 1 task P1.10 and the freshness eval (`evals/example-freshness.py`, created in Phase 1 and extended in Phase 4) verify against it.

## 1. Purpose

`examples/` shows, per selected skill, exactly what an invocation looks like and what output the plugin produces. The examples double as regression references: if a future change alters output shape or quality, diffing against these files shows it.

## 2. Layout

```
examples/
├── README.md                          # index, format, grounding protocol summary
├── research-verification/
│   ├── literature-search-prisma.md
│   ├── fact-checking-report.md
│   ├── sota-benchmark-table.md
│   └── citation-audit.md
├── writing-review/
│   ├── manuscript-setup.md
│   ├── paper-drafting-introduction.md
│   ├── peer-review-report.md
│   └── response-to-reviewers.md
├── visualization-latex/
│   ├── tikz-architecture-diagram.md
│   ├── plotneuralnet-cnn.md
│   └── latex-results-table.md
└── publishing/
    ├── journal-finder-report.md
    ├── conference-finder-cfp.md
    └── cover-letter.md
```

14 examples plus the index: 15 files.

## 3. Running scenario

All examples share one research scenario: **self-supervised learning for ECG arrhythmia classification** (PTB-XL and related benchmarks). The set is internally consistent:

- the PRISMA search's included set becomes the bibliography used by the drafting example,
- the drafted introduction is what the peer-review example reviews,
- the review's comments feed the response-to-reviewers example,
- the journal chosen by journal-finder is addressed in the cover letter,
- the CNN diagram is the manuscript's model.

A future re-grounding may substitute another topic only if it has equally dense verifiable literature, and must apply it consistently across all 14 files.

## 4. Common format

Every example starts with this header structure:

```markdown
# Example: <Title>

| Field | Value |
|---|---|
| Skill | <skill-name> |
| Command | </command or n/a> |
| Trigger phrase | "<exact user wording>" |
| Connectors used | <Scite MCP, direct APIs, or none> |
| Generated | <YYYY-MM-DD>, citations verified on this date |

## Invocation
> <user prompt, verbatim>

## Input
<files or data given to the skill, or "None">

## Output
<the skill's output, unabridged or with elisions marked [...]>

## What this demonstrates
<2-4 bullets: behaviors, constraints, integrations on display>
```

## 5. Grounding protocol (binding)

1. Every citation, DOI, author list, year, venue, citation tally, and benchmark number comes from an actual retrieval performed at authoring time (Scite MCP search, Crossref/OpenAlex/arXiv API fetches). Nothing is entered from model memory.
2. Volatile facts (CFP deadlines, APCs, review-speed statistics) carry an inline tag: "verified as of <date>, source: <url>".
3. Synthetic content is allowed only for things that are inherently authored rather than cited: reviewer comments, manuscript prose, example experimental data, and the single seeded fake bib entry in the citation-audit example. All of it is labeled `(synthetic, for demonstration)`.
4. House style inside outputs: no em dashes, no invented data, LaTeX compiled before inclusion.
5. Every fenced `latex`/`tex` block is classified by shape before compiling, because not every block is a complete document:
   - **standalone**: the block contains a `\documentclass` line and is a full document (for example the tikz-architecture-diagram and plotneuralnet-cnn examples). It compiles directly with tectonic, no wrapping.
   - **fragment**: the block is a bare snippet with no `\documentclass`, for example a `\section`/`\subsection`, a `\begin{table}...\end{table}` or `\begin{tikzpicture}...\end{tikzpicture}` float, or a section-body such as an `introduction.tex` that a real `main.tex` would `\input{}`. Before compiling, the fragment is wrapped in a minimal harness document: a `\documentclass{article}` preamble that loads the packages the fragment references (booktabs, tikz, graphicx, natbib/biblatex, siunitx as needed) plus a stub bibliography resolving any `\cite{}` keys, with the fragment placed inside `document`.
   `evals/example-freshness.py` performs this standalone-vs-fragment classification and applies the harness wrap. This is exactly the verification method already used to validate the current examples.
6. Before committing changes to examples/: resolve every DOI against Crossref (or every arXiv ID via the arXiv API), and compile every fenced `latex`/`tex` block per rule 5 (standalone blocks directly, fragments inside the harness wrap) with tectonic. (Automated by `evals/example-freshness.py`, created in Phase 1 and extended in Phase 4; the same checks run manually during authoring.)

## 6. Acceptance checklist

- [ ] 15 files present, layout as in section 2
- [ ] Every example uses the common format header
- [ ] Every DOI resolves via `https://api.crossref.org/works/<doi>` (or arXiv ID via arXiv API)
- [ ] Every fenced LaTeX block is classified standalone vs fragment per section 5
- [ ] Every standalone block (contains `\documentclass`) compiles directly under tectonic
- [ ] Every fragment (bare `\section`/`\begin{table}`/`\begin{tikzpicture}`/section-body) compiles inside the `evals/example-freshness.py` harness wrap under tectonic
- [ ] Every volatile fact carries a verified-as-of tag
- [ ] Every synthetic element is labeled
- [ ] No em dashes anywhere
- [ ] Internal consistency: bib keys in drafting example resolve to the PRISMA example's included set; review/rebuttal/cover-letter facts match the manuscript examples

## 7. Per-file content specs

### research-verification/

**literature-search-prisma.md** (skill: literature-search). Systematic-mode search on the running topic. Shows per-source query table (queries actually run), PRISMA flow counts (identified, deduplicated, screened, included), ranked top-10 with real DOIs and 1-2 sentence relevance notes, Scite supporting/contrasting tallies where available, and the search-provenance record. Its included set is the canonical bibliography for the writing examples.

**fact-checking-report.md** (skill: fact-checking). Four claims about deep learning for ECG chosen so verdicts differ: one Supported, one Contested (with real contrasting citations), one Unsupported (honest empty-handed verdict, no invented sources), one Partially Supported. Each verdict: evidence quotes, sources, confidence, reasoning.

**sota-benchmark-table.md** (skill: sota-finder). SOTA table for PTB-XL superclass classification: method, paper (real DOI or arXiv ID), year, metric value, peer-reviewed vs preprint flag, verified flag. Notes explain that numbers appear only when retrieved from the actual paper and that leaderboard claims that cannot be traced are marked unverified. Today the flag column is a binary verified/unverified marker; once Phase 3 lands, sota-finder emits the four-state verdict (verified / mismatch / unresolvable / inconclusive) per row, so this example is regenerated from the CLI at that point (see section 8).

**citation-audit.md** (skill: citation-management today, citation-audit after Phase 3). Verification report over a 10-entry bibliography: 9 real entries from the PRISMA example, each shown verified with the indexes that confirmed it, plus 1 seeded fake entry labeled `(synthetic, for demonstration)` flagged `unresolvable`, plus a retraction-check line. Demonstrates the gate output shape Phase 2 makes deterministic.

### writing-review/

**manuscript-setup.md** (skill: manuscript-setup, command: /new-manuscript). Filled form fields, the elicitation exchange, the generated `manuscript/` tree matching CLAUDE.md's structure, excerpts of `main.tex` and `config.yaml`.

**paper-drafting-introduction.md** (skill: paper-drafting). A 500-700 word funnel-structure Introduction for the running manuscript, `(synthetic, for demonstration)` as prose, with real `\cite{}` keys resolving to the PRISMA example's bibliography, plus a claim-to-citation mapping table.

**peer-review-report.md** (skill: peer-review). Five personas (Editor-in-Chief, Methodology, Domain Expert, Writing, Devil's Advocate) reviewing the drafted introduction and manuscript skeleton: per-dimension rubric scores (0-100), decision mapping, actionable comments labeled `(synthetic reviewer content)`. Any literature a persona invokes must be a real retrieved paper.

**response-to-reviewers.md** (skill: response-to-reviewers). Point-by-point responses to five comments from the review example: quoted comment, response, action taken, manuscript location, changed text; includes one polite, evidence-backed disagreement citing a real paper. Follows `templates/latex/response-to-reviewers.tex` conventions.

### visualization-latex/

**tikz-architecture-diagram.md** (skill: tikz-diagrams). Standalone compilable `.tex` for the SSL pretrain, fine-tune, evaluate pipeline, in `references/tikz-patterns.md` style, with a compiled-with-tectonic note. Classified standalone under section 5 (carries its own `\documentclass`).

**plotneuralnet-cnn.md** (skill: plotneuralnet). Self-contained PlotNeuralNet-style `.tex` for a small 1D-CNN ECG encoder per `references/plotneuralnet-layers.md`, compilable without the PlotNeuralNet repository. Classified standalone under section 5.

**latex-results-table.md** (skill: latex-tables). Input CSV snippet labeled `(synthetic, for demonstration)` converted to a booktabs table: multicolumn header, bold-best, significance markers, table notes; short note on the docx-js Word equivalent. The table block is a fragment under section 5 and compiles inside the harness wrap.

### publishing/

**journal-finder-report.md** (skill: journal-finder). Ranked shortlist of 5 real journals for the running manuscript: fit rationale, scope match, OA/APC facts with verified-as-of tags, formatting notes. No fabricated impact metrics.

**conference-finder-cfp.md** (skill: conference-finder). Table of 5-6 real venues relevant to the topic: deadlines, dates, location, format, each row with source URL and verified-as-of date. Rows whose next cycle is unannounced say so instead of guessing.

**cover-letter.md** (skill: cover-letter). Cover letter to the top journal from the finder report following `templates/latex/cover-letter.tex`: editor address, contribution summary, fit justification, originality and data-availability statements. Manuscript facts match the writing examples; letter prose labeled synthetic where it asserts unbuilt results.

## 8. Maintenance

- Touching any example re-triggers the section 6 checklist (automated by `evals/example-freshness.py`, created in Phase 1 and extended in Phase 4, which classifies each LaTeX block standalone vs fragment and harness-wraps fragments before compiling).
- When Phase 2 lands, `literature-search-prisma.md`'s search-provenance record (shown today as a single `provenance.json` object) becomes the append-only event-model `provenance.jsonl` (D10), with PRISMA counts derived by aggregation; regenerate it from the CLI then.
- When Phase 3 lands, `citation-audit.md` moves from "shape demonstration" to actual `verify-bib` output, and `sota-benchmark-table.md`'s flag column becomes the four-state verdict; regenerate both from the CLI then.
- Keep example outputs in sync with skill behavior changes; the examples are documentation, and stale documentation is worse than none.
