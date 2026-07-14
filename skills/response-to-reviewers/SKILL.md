---
name: response-to-reviewers
description: "Create point-by-point response to reviewer comments. Triggers: response to reviewers, write rebuttal, reviewer response, point by point response."
---

# Response To Reviewers

Generate a structured point-by-point response document addressing every reviewer comment.

## Workflow

1. **Load revision context:**
   - Read `manuscript/revisions/roadmap-R{N}.md` for the comment list and categories
   - Read `manuscript/revisions/log-R{N}.md` for changes actually made
   - If no roadmap exists, parse reviewer comments directly (same as revision-management ingestion)

2. **Collect manuscript diffs:**
   - Compare current manuscript files against the pre-revision snapshot
   - Extract specific passages that changed, with before/after text

3. **Generate response document** with the following structure for each reviewer:

## Response Format

```
Dear Editor and Reviewers,

We sincerely thank the reviewers for their careful reading and constructive
feedback. We have addressed all comments point by point below. Reviewer
comments are shown in **bold**, our responses in regular text, and revised
manuscript text in blue.

---

## Reviewer 1

**R1.C1: [Quoted reviewer comment verbatim]**

We thank the reviewer for this observation. [Explanation of what was done
and why.]

> _Revised text (p. X, lines Y-Z):_
> \textcolor{blue}{The new or modified passage as it now appears in the
> manuscript.}

---

**R1.C2: [Next comment]**

...

## Reviewer 2

...
```

## Point-by-Point Entry Rules

Each response entry must contain:
1. **Comment ID**: consistent with roadmap numbering (R1.C1, R1.C2, etc.)
2. **Verbatim quote**: the reviewer's original comment in bold
3. **Response**: what was done, written in professional academic tone
4. **Revised text**: the actual new/changed text from the manuscript, color-coded
5. **Location reference**: section, page, and line numbers where the change appears

## Tone Guidelines

- Always thank the reviewer, even for critical comments
- Use phrases like "We agree with the reviewer that..." or "We appreciate this suggestion..."
- For disagreements, use evidence-based diplomatic language:
  - "We respectfully note that..." followed by citation or data reference
  - "While we understand the reviewer's concern, our approach is supported by..."
  - Never be dismissive, defensive, or confrontational
- For out-of-scope requests, acknowledge the value and explain scope limitations
- Keep responses concise but complete; avoid unnecessary padding

## Color Coding

### LaTeX Output
- New or modified text: `\textcolor{blue}{added text}`
- Removed text: `\textcolor{red}{\sout{deleted text}}` (using `soul` package)
- Use the template at `templates/latex/response-to-reviewers.tex` as the document base
- Compile-check by running `scripts/latex-compile.py` (or `latex-compile.sh` on POSIX), which uses whichever TeX engine is installed (tectonic, or latexmk / pdflatex from TeX Live, MiKTeX, or MacTeX), to produce the PDF

### Word Output
- New text: blue font color
- Removed text: red font color with strikethrough
- Generate DOCX using `docx-js` with proper formatting runs
- Match the structure defined in `templates/word/response-to-reviewers.md`

## Cross-Referencing

- Reference the tracked-changes manuscript: "Please see the tracked-changes document for all modifications highlighted in context."
- Use consistent page/line numbering that matches the revised manuscript PDF
- If a single reviewer comment triggered changes in multiple sections, list all locations

## Handling Special Cases

### Comment already addressed by another change
"This concern is addressed by the revision described in our response to R1.C2 above (Section 3.2, lines 45-50)."

### Conflicting reviewer comments
"We note that Reviewer 1 (C3) and Reviewer 2 (C5) offer opposing suggestions on this point. We have adopted [chosen approach] because [evidence-based reason], and we hope both reviewers find this acceptable."

### Comment requiring no manuscript change
"We agree with the reviewer's interpretation. No change was needed in the manuscript as the current text already addresses this point (Section 2.1, lines 12-18). We have added a clarifying sentence to make this more explicit."

## Output Files

- LaTeX: `manuscript/response-to-reviewers-R{N}.tex` and compiled PDF
- Word: `manuscript/response-to-reviewers-R{N}.docx`
- Both outputs contain identical content in their respective formats

## After Generation

- Remind user to review the response document for accuracy and tone
- Suggest final proofread of the revised manuscript alongside the response
- Note any comments that were deferred or marked out-of-scope for transparency
- If cover letter update is needed for resubmission, suggest the cover-letter skill
