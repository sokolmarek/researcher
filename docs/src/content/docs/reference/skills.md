---
title: Skills
description: The 31 skills, what each one does, and which category it belongs to.
sidebar:
  label: Skills
  order: 0
---

Skills are the unit of work. Each one is a directory holding a `SKILL.md`: frontmatter with a name and a description full of trigger phrases, then the workflow the model follows. There are 29 of them, in seven categories.

You do not have to invoke a skill by name. The description is what the model matches your phrasing against, so "find recent papers on X" reaches `literature-search` on its own. The trigger column below is a hint, not a magic word.

The same 31 skills install into OpenAI Codex as `researcher-<name>` (see [Codex](/researcher/start/codex/)), where you can also call one explicitly, for example `$researcher-literature-search`.

## Research & Discovery (8)

| Skill | What it does | Typical trigger |
|---|---|---|
| `literature-search` | Multi-source search across OpenAlex, Crossref, Semantic Scholar, arXiv, PubMed, and Scite. Deduplicates by DOI then title, ranks results, and in systematic mode records a PRISMA flow and a search-provenance record. | "Do a systematic literature search on X" |
| `research-convergence` | Deep research that converges on an argument rather than a pile of PDFs. Three modes: Socratic, Full Research, Flash. | "Help me build the thesis for this" |
| `fact-checking` | Verifies a claim against the literature and returns a verdict (Supported, Contested, Partially Supported, Contradicted, Unsupported) with the evidence behind it. Returns Unsupported rather than invent a source. | `/researcher:fact-check <claim>` |
| `sota-finder` | Finds state-of-the-art results for a benchmark, with performance timelines and comparison tables. Numbers are traced to the paper that reported them. | `/researcher:sota <benchmark>` |
| `research-gaps` | Identifies methodological, empirical, and theoretical gaps in a body of literature, ranked by impact potential. | "What is missing in this literature?" |
| `citation-context` | Classifies citations as supporting, contrasting, or mentioning, and audits a manuscript for sources it misrepresents. | "Check how I framed these citations" |
| `citation-audit` | Audits every citation in a manuscript for existence (does it resolve, is it retracted) and faithfulness (does the source support the claim), refusing a clean verdict on any refusal-grade finding. | `/researcher:verify-citations` |
| `research-pipeline` | Drives a manuscript through Plan, Retrieve, Synthesize, Draft, Review, Compile, and Format, with a checkpoint at every stage and a compile gate before formatting. | "Run the pipeline from question to draft" |

Full walkthrough: [Research & Discovery guide](/researcher/guides/research-and-discovery/).

## Planning & Design (4)

| Skill | What it does | Typical trigger |
|---|---|---|
| `brainstorming` | Socratic refinement, from a vague hunch to a precise research question, hypotheses, and a method. | `/researcher:brainstorm` |
| `experiment-design` | Designs studies with controls, sample sizing, power analysis, ablations, and a reproducibility checklist. | `/researcher:design-experiment <question>` |
| `statistical-analysis` | Test selection, assumption checking, generated analysis code (Python, R, MATLAB), and APA-formatted reporting. | "Which statistical test should I use?" |
| `manuscript-setup` | Scaffolds the project: per-section files, bibliography, figures and tables folders, `config.yaml`, terminology tracking. LaTeX, Word, or both. | `/researcher:new-manuscript` |

Full walkthrough: [Planning & Design guide](/researcher/guides/planning-and-design/).

## Writing & Revision (6)

| Skill | What it does | Typical trigger |
|---|---|---|
| `paper-drafting` | Outline mode and section-by-section drafting, with cross-referencing, consistent terminology, and journal-aware formatting. | `/researcher:draft-section <section>` |
| `writing-style-analysis` | Reads your past papers and produces a reusable `style-profile.yaml` that drafting then writes to. | "Analyze my writing style from these papers" |
| `peer-review` | Five reviewer personas plus an Editor-in-Chief, with a scoring rubric and a decision. External model reviewers (OpenAI, Gemini, Ollama) are a documented integration point, planned and not implemented. | `/researcher:review-paper` |
| `revision-management` | Parses reviewer comments into a tracked roadmap and generates LaTeX tracked changes (the `changes` package or latexdiff). Word tracked changes are planned, not implemented. | `/researcher:revise <round>` |
| `response-to-reviewers` | Point-by-point response document: every comment answered, changes quoted, disagreements argued with evidence. | "Write the response to reviewers" |
| `cover-letter` | Journal-appropriate cover letter, with the tone matched to the journal's tier. | "Write a cover letter for this journal" |

Full walkthrough: [Writing & Revision guide](/researcher/guides/writing-and-revision/).

## Visualization & Figures (6)

| Skill | What it does | Typical trigger |
|---|---|---|
| `visualization` | Publication-quality plots as runnable code: matplotlib, seaborn, ggplot2, plotly, pgfplots. Chart-type selection and statistical annotation included. | "Plot these results" |
| `tikz-diagrams` | Architectures, flowcharts, state machines, timelines, and pipelines in TikZ/PGF. | "Draw the system architecture" |
| `plotneuralnet` | Neural network architecture diagrams with 3D layered boxes, as a self-contained single-file `.tex`. Presets for VGG, ResNet, U-Net, Transformer. | "Make a CNN architecture diagram" |
| `figure-suggestions` | Reads the manuscript and recommends which figures it needs, of what type, and where they go. | "What figures should this paper have?" |
| `latex-tables` | Booktabs tables from CSV or JSON: significance markers, bold best results, multi-column, landscape, longtable. | "Turn this CSV into a results table" |
| `image-prompt-crafting` | Prompts for external image generators, for conceptual illustrations, graphical abstracts, and cover art only. Never for data or results figures, and always with an AI-disclosure caption. | "Draft a graphical abstract prompt" |

All the figure-producing skills share named style presets (default, Nature, IEEE). A preset restyles typography, sizing, and color; it never touches your data. Full walkthrough: [Visualization & Figures guide](/researcher/guides/visualization-and-figures/).

## Publishing & Formatting (3)

| Skill | What it does | Typical trigger |
|---|---|---|
| `journal-finder` | Ranked, reasoned journal recommendations, filtered by impact factor, quartile, indexing, open access, and APC. | `/researcher:find-journal` |
| `conference-finder` | Conferences and workshops with deadlines, rankings, acceptance rates, and locations. | `/researcher:find-conference` |
| `journal-formatting` | Applies a target journal's requirements from a local database of 16 publisher and journal profiles; anything else is looked up from the publisher's author guidelines. Validates compliance. | "Format this for IEEE Access" |

Full walkthrough: [Publishing & Formatting guide](/researcher/guides/publishing-and-formatting/).

## Code & Implementation (2)

| Skill | What it does | Typical trigger |
|---|---|---|
| `implementation` | Experiment scripts, data pipelines, and evaluation code, with reproducibility (seeds, environment, config) enforced. | "Implement this training loop" |
| `code-analysis` | Reads your codebase and drafts the methods section from it: pseudocode, complexity analysis, algorithm environments. | "Write methods from this repo" |

Both carry `context: fork` and `agent: code-agent` in their frontmatter, so they run in the Sonnet-pinned [Code Agent](/researcher/reference/agents/) and your session's higher-tier budget stays on research and writing. They are the only two skills that fork. Full walkthrough: [Code & Implementation guide](/researcher/guides/code-and-implementation/).

## Output & Management (2)

| Skill | What it does | Typical trigger |
|---|---|---|
| `word-output` | DOCX generation through `templates/word/build-docx.js` (node, built on the `docx` library): title page, numbered headings, paragraphs, lists. Tracked changes, comments, and table emission are specified but not implemented yet. | "Give me this in Word" |
| `citation-management` | Maintains `library.bib`: import, DOI validation against Crossref, retraction detection, predatory-venue flags, format conversion, and a citation-integrity audit. Zotero through the user-installed zotero-mcp server; Mendeley by manual export. | "Validate my bibliography" |

Both are covered in the [Publishing & Formatting guide](/researcher/guides/publishing-and-formatting/).

## Where to go next

- The [Commands](/researcher/reference/commands/) that route into these skills.
- The [Agents](/researcher/reference/agents/) that orchestrate several of them at once.
- The [Connectors](/researcher/reference/connectors/) the research skills call out to.
