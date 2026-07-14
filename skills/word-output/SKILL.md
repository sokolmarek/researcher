---
name: word-output
description: "Generate Microsoft Word DOCX output. Triggers: word format, docx output, Microsoft Word, not latex, convert to word. Full DOCX with tracked changes and comments."
---

# Word Output

Convert manuscript outputs to professional Microsoft Word DOCX format using `docx-js` (Node.js).

## Conversion Modes

### LaTeX to DOCX (pandoc + post-processing)
1. Run `pandoc` to convert `.tex` source to `.docx` baseline
2. Post-process with `docx-js` to fix formatting pandoc mishandles:
   - Table borders and shading
   - Figure sizing and placement
   - Heading numbering and styles
   - Citation formatting
   - Page headers and footers
3. Validate final output

### Native DOCX Creation
For manuscripts authored in Word mode from the start:
1. Read section `.md` files from `manuscript/`
2. Build DOCX programmatically via `docx-js`
3. Apply all formatting directly without pandoc intermediary

## Document Structure

### Headings
- Title: custom title style (centered, bold, 16pt)
- Section headings: Heading 1 (bold, 14pt, numbered)
- Subsection headings: Heading 2 (bold, 12pt, numbered)
- Sub-subsection: Heading 3 (italic, 12pt, numbered)
- Maintain automatic heading numbering via Word outline levels

### Body Text
- Font: Times New Roman 12pt (default) or journal-specified font
- Line spacing: double (default) or as journal requires
- Paragraph spacing: 0pt before, 6pt after
- First-line indent: 0.5in (or as journal requires)
- Justified alignment

### Page Setup
- Page numbers: bottom center or top right (journal-dependent)
- Running header: short title on left, page number on right
- Margins: 1 inch all sides (default) or journal-specified
- Paper size: Letter (default) or A4

## Table Formatting

- Map `booktabs` rules to Word border styles:
  - `\toprule` and `\bottomrule` → thick top/bottom borders (1.5pt)
  - `\midrule` → thin border (0.5pt)
  - No vertical borders
- Preserve cell alignment (left, center, right, decimal)
- Bold best results carry over from LaTeX source
- Table captions placed above the table
- Auto-number tables (Table 1, Table 2, ...)

## Figure Handling

- Embed figures as inline images (PNG or PDF-to-PNG conversion)
- Center figures with caption below
- Auto-number figures (Figure 1, Figure 2, ...)
- Maintain aspect ratio; scale to column width
- Alt text for accessibility

## Tracked Changes (Revisions)

For revision rounds, generate DOCX with actual Word tracked changes:
- **Insertions:** shown in blue underlined text with author tag
- **Deletions:** shown in red strikethrough text with author tag
- **Moved text:** tracked as delete + insert pair
- Compare original and revised section files to generate change markup
- Each change tagged with revision round (R1, R2, R3)

## Comment Annotations

- Attach Word comments to specific text ranges
- Used for: reviewer comment references, editorial notes, integrity flags
- Format: `[Reviewer X, Comment Y]: original comment text`
- Comments appear in the review pane and print in margin

## Cross-References

- Figure references: `Figure 1`, `Figure 2` as Word cross-reference fields
- Table references: `Table 1`, `Table 2` as cross-reference fields
- Equation references: `Equation (1)` with field codes
- Section references: link to heading bookmarks
- All references are updateable fields (right-click > Update Field)

## Bibliography

- Generate bibliography section from `library.bib`
- Format citations according to `config.yaml` citation style
- In-text citations as formatted text (Word native bibliography is unreliable)
- Alternatively, generate Zotero-compatible citation fields if user prefers

## Journal Template Support

- Download and apply journal-provided `.dotx` or `.docx` templates
- Map heading styles to template-defined styles
- Respect template margins, fonts, and spacing
- If no template available, use sensible defaults matching journal specs

## Output Validation

Before delivering any DOCX:
1. Verify file opens without corruption (valid ZIP/OOXML structure)
2. Check all images are embedded (no broken links)
3. Confirm heading numbering is sequential
4. Verify page numbers are present and correct
5. Check tracked changes render properly if revision mode

## Workflow

1. Determine source format (LaTeX sections or Markdown sections)
2. Choose conversion path (pandoc + post-process or native docx-js)
3. Read `manuscript/config.yaml` for journal and formatting preferences
4. Build DOCX with all structural elements
5. Apply tracked changes if this is a revision round
6. Add comments if review annotations are present
7. Validate output integrity
8. Save to `manuscript/output/<filename>.docx`

## Integrity constraints

- Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it; never invent a DOI, author list, venue, or year.
- Never invent data: only user-provided or actually computed numbers may appear as results. Anything illustrative must be labeled "(synthetic, for demonstration)".
- Validate the generated DOCX (generation script exits cleanly, file opens) before delivery.
- Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).

Canonical copy: `references/integrity-constraints.md`.
