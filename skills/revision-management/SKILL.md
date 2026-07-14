---
name: revision-management
description: "Handle paper revisions from reviewer comments. Triggers: revise paper, address comments, reviewer asked, revision round, tracked changes. Generates tracked changes in LaTeX and Word."
---

# Revision Management

Parse reviewer comments and orchestrate manuscript revisions with full traceability.

## Workflow

1. **Ingest reviewer comments** from any supported format:
   - Plain text or markdown pasted directly
   - PDF review report (extract text)
   - Word document with inline comments (parse comment anchors)
   - Structured review from the peer-review skill (`manuscript/reviews/review-R*.md`)

2. **Parse and number** every discrete reviewer comment:
   - Assign identifiers: `R1.C1` (Reviewer 1, Comment 1), `R2.C3`, etc.
   - Preserve original wording exactly (quote verbatim in the revision log)
   - Group by reviewer, then by section if reviewer organized that way

3. **Categorize** each comment into one of four priority levels:

| Category | Criteria | Action |
|----------|----------|--------|
| **Must-address** | Methodological flaw, missing data, factual error, major logic gap | Revise immediately; explain change in response |
| **Should-address** | Clarity issue, suggested analysis, minor structural concern | Revise unless strong reason not to; explain either way |
| **Optional** | Stylistic preference, minor wording suggestion, nice-to-have | Revise if easy; acknowledge in response |
| **Out-of-scope** | Requests new experiments beyond scope, contradicts other reviewers | Do not revise; provide diplomatic justification |

4. **Create revision roadmap** in `manuscript/revisions/roadmap-R{N}.md`:

```markdown
# Revision Roadmap: Round {N}

## Reviewer 1
| ID | Comment Summary | Category | Target Section | Action |
|----|----------------|----------|---------------|--------|
| R1.C1 | Missing baseline comparison | Must-address | results.tex | Add Table 3 |
| R1.C2 | Unclear notation in Eq. 2 | Should-address | methods.tex | Rewrite paragraph |

## Reviewer 2
...
```

5. **Apply revisions** to manuscript files, one comment at a time:
   - Edit the relevant `.tex` or `.md` section file
   - After each edit, record what changed and why in the revision log

6. **Generate tracked-changes output:**

### LaTeX Tracked Changes
- Use the `changes` package (`\added{}`, `\deleted{}`, `\replaced{}`) with author labels
- Alternatively, produce a `latexdiff` output comparing `manuscript-R{N-1}/` to current
- Color scheme: blue for additions, red with strikethrough for deletions
- Compile-check both clean and tracked-changes PDFs by running `scripts/latex-compile.py` (or `latex-compile.sh` on POSIX), which uses whichever TeX engine is installed (tectonic recommended, or latexmk / pdflatex from TeX Live, MiKTeX, or MacTeX)

### Word Tracked Changes
- Generate DOCX with actual Word revision marks (insertions, deletions)
- Use `docx-js` revision tracking API for proper change markers
- Include comment annotations linking back to reviewer comment IDs

## Revision Log

Maintain `manuscript/revisions/log-R{N}.md` linking every change to its source:

```markdown
# Revision Log: Round {N}

| Comment ID | File Changed | Lines | Change Description |
|-----------|-------------|-------|-------------------|
| R1.C1 | results.tex | 45-62 | Added baseline comparison table |
| R1.C2 | methods.tex | 23-28 | Clarified notation for loss function |
| R2.C1 | introduction.tex | 10-15 | Expanded motivation paragraph |
```

## Multi-Round Support

- Support rounds R1, R2, R3 (and beyond if needed)
- Each round gets its own roadmap and log in `manuscript/revisions/`
- When starting R2, load R1 review and previous roadmap for context
- Track cumulative changes across rounds
- Flag comments that repeat from earlier rounds (reviewer unsatisfied)

## Rebuttal Strategy Suggestions

When a reviewer comment is categorized as out-of-scope or appears unfair:
- Suggest diplomatic language that acknowledges the concern
- Provide evidence-based justification for not making the change
- Reference literature or methodology standards that support the current approach
- Never dismiss a reviewer; always thank them and explain reasoning
- Flag genuinely incorrect reviewer claims with citations to correct information

## After Revision

- Run post-draft-integrity hook to validate cross-references and citations
- Suggest running `/researcher:review-paper` in re-review mode to self-check
- Remind user to prepare response-to-reviewers document next
- Report summary: number of comments addressed, deferred, and out-of-scope
