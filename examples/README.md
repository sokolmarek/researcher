# Researcher Examples

Worked examples of selected skills, each showing a real invocation and its output. They serve two purposes: they show newcomers what the plugin produces, and they act as regression references (the Phase 4 freshness eval re-validates every DOI and LaTeX block here).

The normative specification for this directory is `plans/06-examples-spec.md`.

## Index

| Example | Skill | Category |
|---|---|---|
| [literature-search-prisma](research-verification/literature-search-prisma.md) | literature-search | Research and verification |
| [fact-checking-report](research-verification/fact-checking-report.md) | fact-checking (`/researcher:fact-check`) | Research and verification |
| [sota-benchmark-table](research-verification/sota-benchmark-table.md) | sota-finder (`/researcher:sota`) | Research and verification |
| [citation-audit](research-verification/citation-audit.md) | citation-management / citation-audit | Research and verification |
| [manuscript-setup](writing-review/manuscript-setup.md) | manuscript-setup (`/researcher:new-manuscript`) | Writing and review |
| [paper-drafting-introduction](writing-review/paper-drafting-introduction.md) | paper-drafting (`/researcher:draft-section`) | Writing and review |
| [peer-review-report](writing-review/peer-review-report.md) | peer-review (`/researcher:review-paper`) | Writing and review |
| [response-to-reviewers](writing-review/response-to-reviewers.md) | response-to-reviewers (`/researcher:revise`) | Writing and review |
| [tikz-architecture-diagram](visualization-latex/tikz-architecture-diagram.md) | tikz-diagrams | Visualization and LaTeX |
| [plotneuralnet-cnn](visualization-latex/plotneuralnet-cnn.md) | plotneuralnet | Visualization and LaTeX |
| [latex-results-table](visualization-latex/latex-results-table.md) | latex-tables | Visualization and LaTeX |
| [visualization-plot](visualization-latex/visualization-plot.md) | visualization | Visualization and LaTeX |
| [journal-finder-report](publishing/journal-finder-report.md) | journal-finder (`/researcher:find-journal`) | Publishing and discovery |
| [conference-finder-cfp](publishing/conference-finder-cfp.md) | conference-finder (`/researcher:find-conference`) | Publishing and discovery |
| [cover-letter](publishing/cover-letter.md) | cover-letter | Publishing and discovery |

## Running scenario

All examples share one research scenario: **self-supervised contrastive pretraining for ECG arrhythmia classification**, evaluated on the PTB-XL benchmark. The visualization examples include rendered figures (diagrams, a results table, and a chart) alongside their source. The set is internally consistent: the systematic search produces the bibliography; the drafted introduction cites it; the peer review critiques the draft; the response answers the review; the journal chosen by the finder receives the cover letter; and the CNN in the diagrams is the manuscript's model.

## Style variants

Two visualization examples, `visualization-plot` and `tikz-architecture-diagram`, each show a default
variant and a Nature-preset variant of the same figure, both rendered, with identical underlying data.
The presets (`references/figure-styles.md`) restyle typography, sizing, and color, never the plotted
values or the diagram topology: asking for a journal style changes presentation, not results.

## Common format

Every example uses the same header:

1. A metadata table (Skill, Command, Trigger phrase, Connectors used, Generated date).
2. **Invocation**: the user prompt, verbatim.
3. **Input**: files or data given to the skill, or "None".
4. **Output**: the skill's output, unabridged or with elisions marked `[...]`.
5. **What this demonstrates**: a few bullets on the behaviors and constraints shown.

## Grounding and honesty rules

- **Real citations only.** Every DOI, author, year, venue, and reported number comes from an actual retrieval performed while authoring the examples (OpenAlex, Crossref, arXiv, and Scite). Nothing is entered from memory. Every DOI resolves.
- **Volatile facts are tagged.** Impact factors, APCs, and conference deadlines carry a "confirm at source, as of 2026-07-12" marker instead of a fabricated value.
- **Synthetic content is labeled.** Reviewer comments, manuscript prose, illustrative experimental tables, and the single deliberately fake bibliography entry in the citation-audit example are all marked `(synthetic, for demonstration)`. That fake entry is the only invented reference anywhere in this directory, and it exists so the citation gate has something to reject.
- **House style.** No em dashes; LaTeX blocks are compile-verified with your TeX engine (tectonic, TeX Live, MiKTeX, or MacTeX) before inclusion.

## Regenerating

When a skill's behavior changes, regenerate the affected example and re-run the acceptance checklist in `plans/06-examples-spec.md` section 6 (DOIs resolve, LaTeX compiles, volatile facts tagged, synthetic content labeled, no em dashes). Phase 4's `evals/example-freshness.py` automates the DOI and compile checks.
