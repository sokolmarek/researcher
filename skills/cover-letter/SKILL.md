---
name: cover-letter
description: "Write journal submission cover letters. Triggers: write cover letter, submission letter, cover letter for journal, letter to editor."
---

# Cover Letter

Generate a professional journal submission cover letter tailored to the target journal.

## Workflow

1. **Gather required information** (from `manuscript/config.yaml` or by asking the user):
   - Paper title
   - Complete author list with affiliations
   - Corresponding author name and contact details
   - Target journal name
   - Editor name (if known; otherwise use "Dear Editor" or "Dear Editor-in-Chief")

2. **Gather optional information** (ask user, use defaults if not provided):
   - Suggested reviewers (3-5 names with affiliations and emails)
   - Excluded reviewers with brief justification
   - Funding sources and grant numbers
   - Conflict of interest declarations (default: "The authors declare no conflicts of interest")
   - Data and code availability statement
   - Prior communication with the editor (e.g., pre-submission inquiry reference)
   - Whether this is a new submission or a revised resubmission

3. **Read manuscript context** to write the letter:
   - Read `abstract.tex` or `abstract.md` for contribution summary
   - Read `config.yaml` for journal and paper type
   - Optionally read introduction for broader motivation

4. **Generate the cover letter** using the structure below.

## Letter Structure

```
[Date]

[Editor Name or "Dear Editor-in-Chief,"]
[Journal Name]

Dear [Editor Name / Editor-in-Chief],

PARAGRAPH 1 — SUBMISSION STATEMENT
We are pleased to submit our manuscript entitled "[Title]" for consideration
as a [article type] in [Journal Name]. This manuscript has not been published
elsewhere and is not under consideration by another journal.

PARAGRAPH 2 — CONTRIBUTION SUMMARY
[2-3 sentences summarizing the key contribution, main finding, and its
significance. Draw from the abstract but do not copy it verbatim. Emphasize
novelty and impact.]

PARAGRAPH 3 — JOURNAL FIT
[Why this journal is the right venue. Reference the journal's scope, recent
relevant publications, or readership. Be specific — generic statements like
"your prestigious journal" are insufficient.]

PARAGRAPH 4 — ADDITIONAL STATEMENTS
[Any combination of: funding acknowledgment, COI declaration, data/code
availability, ethics approval, author contributions summary.]

PARAGRAPH 5 — CLOSING
We believe this work will be of interest to the readers of [Journal Name]
and look forward to your consideration.

Sincerely,
[Corresponding Author Name]
[Affiliation]
[Email]
[ORCID if available]
```

## Tone Adaptation by Journal Tier

### High-impact journals (Nature, Science, Cell, Lancet)
- Emphasize broad significance and cross-disciplinary appeal
- Lead with the most striking finding
- Keep language confident but not overstated
- Mention timeliness and relevance to current discourse

### Field-specific top journals (JACS, Physical Review Letters, NEJM)
- Focus on field-specific contribution and methodological advance
- Reference how the work extends the journal's recent coverage
- Use precise technical language appropriate to the field

### Regional or specialized journals
- Emphasize fit with journal scope and readership
- Highlight practical implications or local relevance
- Maintain professional tone without overstatement

## Resubmission Cover Letters

When submitting a revised manuscript:
- Reference the original manuscript ID
- Briefly summarize the revisions made
- State that a detailed response-to-reviewers document is enclosed
- Thank the editor and reviewers for their constructive feedback
- Note any major changes that were not requested but improve the paper

## Suggested/Excluded Reviewers Section

If the user provides reviewer suggestions, append after the closing:

```
Suggested Reviewers:
1. Dr. [Name], [Affiliation] — [email] (expertise in [area])
2. ...

Excluded Reviewers:
1. Dr. [Name], [Affiliation] — [brief reason, e.g., "recent collaborator"]
```

## Output Files

### LaTeX Output
- Use the template at `templates/latex/cover-letter.tex` as the document base
- Generate `manuscript/cover-letter.tex` and compile PDF via tectonic

### Word Output
- Generate `manuscript/cover-letter.docx` using `docx-js`
- Match the structure defined in `templates/word/cover-letter.md`
- Use professional letter formatting (block style, single-spaced)

## Validation

Before delivering the letter:
- Verify all author names match `config.yaml`
- Verify the paper title matches `config.yaml`
- Check that the journal name is spelled correctly
- Ensure no placeholder text remains (e.g., `[TODO]`, `[Name]`)
- Confirm the date is current

## After Generation

- Present the letter for user review
- Suggest the user verify editor name and any factual claims
- Remind user to attach the cover letter when submitting via the journal portal
- If the journal requires additional statements (ethics, ICMJE forms), flag what is missing
