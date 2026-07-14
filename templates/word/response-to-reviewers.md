# Response to Reviewers: DOCX Generation Spec

Specification for generating a point-by-point response document in DOCX format.

## Document Properties

- **Page size:** A4
- **Margins:** 1 inch all sides
- **Default font:** Times New Roman, 11pt
- **Line spacing:** 1.5 (360 twips)

## Title Section

- Title: "Response to Reviewers", centered, 14pt bold
- Subtitle: "Manuscript: [TITLE]", centered, 12pt
- Subtitle: "Manuscript ID: [ID]", centered, 12pt italic
- Date: centered, 11pt

## Cover Paragraph

Opening paragraph thanking the editor for the opportunity to revise. Explain color coding:
- **Blue text** = new/added text
- **Red strikethrough** = removed text

## Reviewer Sections

For each reviewer (Heading 1: "Reviewer N"):

### Comment Block

1. **Comment label** (Heading 2): "Comment N.M"
2. **Reviewer text**: Indented block quote, italic, gray color (#666666)
3. **Response label**: "Response:" in bold
4. **Response text**: Normal paragraph
5. **Location reference**: "(see manuscript, Section X.Y, paragraph Z)" in italic
6. **Revised text quote** (optional): Indented block, new text in blue (#0000CC), removed text in red (#CC0000) with strikethrough

## Color Definitions

| Purpose | Color | Hex |
|---------|-------|-----|
| Reviewer comment text | Dark gray | #666666 |
| New/added text | Blue | #0000CC |
| Removed text | Red | #CC0000 |
| Response label | Black | #000000 |

## Tracked Changes Alternative

If the user prefers actual DOCX tracked changes instead of color coding:
- Use `docx-js` revision tracking API
- Insert revisions as tracked insertions/deletions
- Set author to manuscript author name
- Set date to revision date
