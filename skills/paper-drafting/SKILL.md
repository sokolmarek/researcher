---
name: paper-drafting
description: "Draft academic paper outlines and sections. Triggers: draft outline, write section, draft paper, outline paper, write introduction, write methods, write results, write discussion, write abstract, write conclusion."
---

# Paper Drafting

Structured academic writing skill covering full-paper outlines and individual section drafting with cross-referencing, terminology consistency, and journal-aware formatting.

## Prerequisites

Before drafting, gather the following context:

1. **Manuscript config:** Read `manuscript/config.yaml` for title, authors, target journal, citation style, output format, and word limits.
2. **Style profile:** If `style-profile.yaml` exists in the project root, load it and apply the author's learned voice (sentence length, hedging patterns, vocabulary level, active/passive ratio). See the writing-style-analysis skill.
3. **Bibliography:** Read `manuscript/references/library.bib` to know which citations are available. Never cite a key that does not exist in the bib file.
4. **Existing sections:** Read any already-drafted `.tex` (or `.md`) section files so new content maintains consistency in terminology, notation, and cross-references.
5. **Figures and tables:** Scan `manuscript/figures/` and `manuscript/tables/` to know which assets exist for referencing.

## Modes of Operation

### Outline Mode

Triggered by: "draft outline", "outline the paper", "create paper structure"

Produce a structured outline document (`manuscript/outline.md`) containing:

1. **Section headers** matching the target structure (IMRaD, review, conference, or custom).
2. **Key arguments** per section -- 3-5 bullet points describing what each section must convey.
3. **Word allocation** per section, summing to the journal's total word limit. Default allocation when no journal limit is specified:
   - Abstract: 250 words
   - Introduction: 15% of body
   - Methods: 25% of body
   - Results: 25% of body
   - Discussion: 25% of body
   - Conclusion: 10% of body
4. **Figure/table placement notes** -- which figures or tables appear in which section, with draft captions.
5. **Citation anchors** -- key references to cite in each section, drawn from `library.bib`.

Ask the user to confirm or adjust the outline before proceeding to section drafting.

### Section Drafting Mode

Triggered by: "write section", "draft introduction", "write methods", etc.

Draft one section at a time. Each section follows its own structural conventions below. Always output a `.tex` file (or `.md` if Word mode) into the `manuscript/` directory.

## Section-Specific Conventions

### Abstract

- Detect whether the target journal requires **structured** (Background, Methods, Results, Conclusions) or **unstructured** format. Default to structured.
- Structured abstract: write each subsection as a single concise paragraph. Total length per `config.yaml` limit or 250 words.
- Unstructured abstract: single paragraph covering background, purpose, methods, key findings, and significance.
- Do not introduce abbreviations that are not used in the abstract itself.
- Do not cite references in the abstract unless the journal explicitly requires it.

### Introduction

Follow the **funnel structure**:

1. **Broad context** -- establish the research area and its importance (1-2 paragraphs).
2. **Narrowing focus** -- review relevant prior work, progressively narrowing to the specific problem (2-3 paragraphs). Cite heavily from `library.bib`.
3. **Gap statement** -- clearly identify what is missing, unknown, or unresolved. Use explicit language: "However, ...", "Despite this progress, ...", "No prior work has ...".
4. **Contribution statement** -- state what this paper does to address the gap. Be specific: "In this paper, we propose / demonstrate / analyze ...".
5. **Paper organization** (optional) -- brief roadmap of remaining sections. Include only if the journal convention or paper length warrants it.

### Methods

- Write for **reproducibility**. Another researcher should be able to replicate the study from this section alone.
- Use subsections liberally: Study Design, Participants/Data, Materials/Tools, Procedure, Analysis, Evaluation Metrics.
- Include all hyperparameters, software versions, hardware specs, and random seeds where applicable.
- Reference algorithms formally: "We use Algorithm~\ref{alg:name}" with corresponding `algorithm2e` or `algorithmicx` environments.
- Reference figures showing experimental setup: "The pipeline is illustrated in Figure~\ref{fig:pipeline}".
- Use past tense for completed work, present tense for established truths.

### Results

- Lead with the **most important finding**. Do not bury key results.
- Structure around research questions or hypotheses, not around tables/figures.
- Reference every figure and table: "Table~\ref{tab:main_results} shows ...", "As shown in Figure~\ref{fig:comparison}, ...".
- Report exact numbers with appropriate precision. Never round in a way that loses meaning.
- Include effect sizes, confidence intervals, and p-values where relevant.
- Do not interpret results here -- save interpretation for Discussion.
- Use past tense for describing findings.

### Discussion

Follow this structure:

1. **Key findings summary** -- restate main results without repeating numbers verbatim (1 paragraph).
2. **Interpretation** -- explain what the results mean in context of the research question (1-2 paragraphs).
3. **Comparison with literature** -- relate findings to prior work cited in the Introduction. Agree, disagree, or extend (2-3 paragraphs). Cite from `library.bib`.
4. **Limitations** -- honestly acknowledge weaknesses in methodology, data, or generalizability (1 paragraph).
5. **Implications** -- practical or theoretical implications of the findings (1 paragraph).
6. **Future work** -- concrete next steps, not vague hand-waving (1 paragraph). May be merged into Conclusion if the journal prefers.

### Conclusion

- Summarize the paper's contribution in 1-2 paragraphs. Do not introduce new information.
- Restate the problem, approach, and key findings at a higher level of abstraction than the Abstract.
- End with a forward-looking statement about impact or next steps.
- Keep concise: typically 150-300 words.

## Cross-Referencing System

Maintain consistent `\label` and `\ref` usage throughout all sections:

- **Figures:** `\label{fig:<short-name>}` -- referenced as `Figure~\ref{fig:<short-name>}`
- **Tables:** `\label{tab:<short-name>}` -- referenced as `Table~\ref{tab:<short-name>}`
- **Equations:** `\label{eq:<short-name>}` -- referenced as `Equation~\ref{eq:<short-name>}` or `(\ref{eq:<short-name>})`
- **Sections:** `\label{sec:<short-name>}` -- referenced as `Section~\ref{sec:<short-name>}`
- **Algorithms:** `\label{alg:<short-name>}` -- referenced as `Algorithm~\ref{alg:<short-name>}`

After drafting any section, scan all existing sections for broken or orphaned references and report them.

## Terminology Tracker

Maintain a running terminology map to enforce consistency across sections:

1. On first use of a technical term, record it and its definition.
2. On subsequent uses, verify the same term is used (no unannounced synonyms).
3. Track acronyms: define on first use in the body text (e.g., "convolutional neural network (CNN)"), then use the acronym thereafter. Redefine in the Abstract only if used there.
4. If the user changes a term mid-draft, propagate the change to all previously drafted sections and report what was updated.

Store the map in `manuscript/terminology.yaml` with the format:

```yaml
terms:
  - term: "convolutional neural network"
    acronym: "CNN"
    defined_in: "introduction.tex"
    first_use_line: 12
```

## Iterative Refinement

When the user asks to revise or improve an already-drafted section:

1. Read the current section file.
2. Identify what specifically needs to change (user instruction, review feedback, or self-assessment).
3. Present a summary of planned changes before rewriting.
4. Rewrite the section in place, preserving all valid `\label` tags and cross-references.
5. After rewriting, re-run the cross-reference and terminology checks.

## Journal Adaptation

When a target journal is specified in `config.yaml`:

- Enforce the journal's word limits per section (query the journal-formatting skill if limits are unknown).
- Follow the journal's required section structure (some journals require Data Availability, Author Contributions, etc.).
- Match the journal's heading style (numbered vs. unnumbered, capitalization).
- Adapt citation density to journal norms (e.g., Nature papers cite fewer references in the introduction than review journals).

## Output Format

Each drafted section is saved as a standalone `.tex` file (LaTeX mode) or `.md` file (Word mode) in the `manuscript/` directory. The file must:

1. Begin with a section heading: `\section{Section Title}` with a `\label{sec:name}`.
2. Contain only the section body -- no `\documentclass`, no preamble, no `\begin{document}`.
3. Use `\input{}` compatible structure so `main.tex` can include it directly.
4. End with a blank line for clean concatenation.

After writing, report:
- Word count for the section.
- Number of citations used.
- Number of cross-references (figures, tables, equations).
- Any warnings (broken references, missing citations, terminology inconsistencies).

## Integrity Checks

After every drafting operation, verify:

1. **No fabricated citations.** Every `\cite{key}` must exist in `library.bib`.
2. **No unsupported claims.** Flag any factual assertion that lacks a citation and is not common knowledge.
3. **No orphaned references.** Every `\ref{label}` must have a corresponding `\label{label}` somewhere in the manuscript.
4. **Word count compliance.** Warn if the section exceeds its allocated word budget.

Report the integrity check results to the user after each section is drafted.

## Integrity constraints

1. Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source); if a citation cannot be verified, flag it, do not invent a DOI, author list, venue, or year.
2. Never invent data: only user-provided or actually computed numbers appear as results; anything illustrative is labeled "(synthetic, for demonstration)".
3. Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).
4. Compile-check all LaTeX by running `scripts/latex-compile.py` (or `latex-compile.sh` on POSIX) before delivery; it uses whichever TeX engine is installed (tectonic recommended by default, or latexmk / pdflatex from TeX Live, MiKTeX, or MacTeX).

Canonical copy: `references/integrity-constraints.md`.
