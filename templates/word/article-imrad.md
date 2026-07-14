# Article IMRaD: DOCX Generation Spec

Specification for generating an IMRaD research article in DOCX format using `docx-js`.

## Document Properties

- **Page size:** A4 (210mm x 297mm)
- **Margins:** 1 inch (2.54cm) all sides
- **Default font:** Times New Roman, 12pt
- **Line spacing:** Double (480 twips)
- **Paragraph spacing:** 0pt before, 0pt after

## Heading Styles

| Level | Font | Size | Spacing Before | Bold | Numbering |
|-------|------|------|----------------|------|-----------|
| Heading 1 | Times New Roman | 14pt | 24pt | Yes | 1. |
| Heading 2 | Times New Roman | 12pt | 18pt | Yes | 1.1 |
| Heading 3 | Times New Roman | 12pt | 12pt | Italic | 1.1.1 |

## Title Page

1. Title: centered, 16pt bold, 2 inches from top
2. Author names: centered, 12pt, below title with 24pt spacing
3. Affiliations: centered, 10pt, numbered superscripts matching authors
4. Corresponding author: footnote with email
5. Date: centered, below affiliations

## Sections (in order)

1. **Abstract** (Heading 1, unnumbered), followed by body text, then Keywords line in italic
2. **Introduction** (Heading 1, numbered)
3. **Methods / Materials and Methods** (Heading 1, numbered)
4. **Results** (Heading 1, numbered)
5. **Discussion** (Heading 1, numbered)
6. **Conclusion** (Heading 1, numbered)
7. **Acknowledgments** (Heading 1, unnumbered)
8. **References** (Heading 1, unnumbered), formatted per citation style
9. **Appendix** (Heading 1, unnumbered, optional)

## Table Formatting

- Header row: bold, bottom border (1pt black)
- Body rows: no vertical borders, light bottom borders (0.5pt gray)
- Table notes: 10pt italic below table
- Table caption: above table, "Table N." in bold

## Figure Formatting

- Image: centered, max width 6 inches
- Caption: below image, "Figure N." in bold, followed by description
- 10pt font for captions

## Page Numbers

- Bottom center, starting from page 2
- Header: running title (short title) right-aligned, from page 2

## References Section

- Hanging indent: 0.5 inches
- Formatted per selected citation style (APA 7, IEEE, etc.)
