# Cover Letter: DOCX Generation Spec

Specification for generating a journal submission cover letter in DOCX format.

## Document Properties

- **Page size:** A4
- **Margins:** 1 inch all sides
- **Default font:** Times New Roman, 12pt
- **Line spacing:** Single (240 twips)
- **Paragraph spacing:** 6pt after

## Layout

### Sender Address Block (top right)
- Author name, bold
- Department, University
- Address line
- City, Country
- Email (hyperlinked)
- Right-aligned, 11pt

### Date
- Left-aligned, one blank line below sender block
- Format: Month DD, YYYY

### Recipient Address Block
- Editor name, bold
- "Editor-in-Chief"
- Journal name, italic
- Left-aligned, one blank line below date

### Salutation
- "Dear [Editor Name]," or "Dear Editor,"
- One blank line below recipient

### Body Paragraphs

1. **Submission statement**: "We are pleased to submit..." with manuscript title in italic
2. **Contribution summary**: 2-3 sentences on what the paper does and why it matters
3. **Journal fit**: Why this journal is appropriate
4. **Originality statement**: Not published elsewhere, not under concurrent review
5. **Suggested reviewers** (optional): Numbered list with name, affiliation, email, expertise
6. **Conflict of interest**: Declaration
7. **Data availability**: Statement on data/code access
8. **Funding** (optional): Funding sources and grant numbers

### Closing
- "Sincerely," followed by blank line
- Author name, bold
- "On behalf of all authors" (if multiple)

## Style Notes

- Professional, formal tone
- No bullet points in body (use flowing paragraphs)
- Keep to one page if possible
- Reviewer suggestions as numbered list (exception to no-bullets rule)
