---
name: word-output
description: "Generate Microsoft Word DOCX output from a manuscript folder. Triggers: word format, docx output, Microsoft Word, not latex, convert to word, build docx, submit as .docx. Ships a title page, numbered headings, paragraphs, and bullet lists via templates/word/build-docx.js; tables, figures, tracked changes, and comments are planned, not implemented."
---

# Word Output

Generate a Microsoft Word DOCX with `templates/word/build-docx.js`, a Node script built on the `docx`
library. It is the only DOCX generator in this plugin. Pandoc is not used anywhere in this repo, so
there is no LaTeX-to-DOCX conversion path: Word output is built natively from Markdown sections.

## What ships today

`build-docx.js` assembles an IMRaD article from a manuscript directory and writes a single `.docx`:

- **Title page:** title, author list, and `Prepared for: <journal>` when a journal is set
- **Numbered headings:** Heading 1-3 with automatic numbering (`1.`, `1.1`, `1.1.1`). Abstract,
  Acknowledgments, References, and Appendix stay unnumbered.
- **Body text:** Times New Roman 12pt, double spaced, A4 page, 1 inch margins
- **Bullet lists**
- **Page numbers:** centered in the footer, starting on page 2 (the title page carries none)
- **Section order:** abstract, introduction, methods, results, discussion, conclusion,
  acknowledgments, references, then any remaining section files alphabetically

## Input contract

The script reads two things from the manuscript directory passed to `--manuscript <dir>`:

- **`<dir>/config.yaml`** for document metadata. A small line-based YAML subset is parsed (no YAML
  dependency): top-level `key: value` pairs plus an `authors:` block list, written either as
  `- name: Ada Lovelace` maps or as plain `- Ada Lovelace` strings. The keys used are `title`,
  `authors`, and `journal`; everything else is read but ignored. A missing `config.yaml` falls back
  to "Untitled Manuscript" with no authors.
- **`<dir>/sections/*.md`**, one Markdown file per section. This is `sections/`, not the manuscript
  root: LaTeX mode keeps `.tex` files at the root, Word mode keeps `.md` files under `sections/`.
  The filename (lowercased, minus `.md`) is both the section key used for ordering and the title of
  the generated Heading 1. A missing `sections/` directory is a hard error (exit 2).

## Invocation

Install the dependency once. `package-lock.json` is tracked, so `npm ci` is the correct command:

```bash
cd templates/word
npm ci
```

Then build from the repo root:

```bash
node templates/word/build-docx.js --manuscript <dir> --out paper.docx
```

`--manuscript` is required. `--out` is optional and defaults to `paper.docx` in the current working
directory. The file is written exactly where `--out` points; there is no `manuscript/output/`
convention and the script creates no directories.

## Supported Markdown subset

Inside each `sections/*.md` file, the script understands:

| Syntax | Result |
|--------|--------|
| `# Heading` | Skipped: the section title is already emitted from the filename |
| `## Heading`, `### Heading` | Heading 2 / Heading 3, numbered unless the section is unnumbered |
| Blank-line separated text | Body paragraph (consecutive lines are joined) |
| `**bold**` | Bold run |
| `*italic*` | Italic run |
| `` `code` `` | Courier New 11pt run |
| `- item` or `* item` | Bullet list item (single level) |
| `<!-- comment -->` | Stripped |

Anything else (tables, images, links, block quotes, numbered lists, nested lists, math) passes
through as literal text. Write section files inside this subset, or the DOCX will contain raw
Markdown syntax.

## Output validation

Before delivering any DOCX:

1. Confirm the script exited 0 and printed `Wrote <path> (<n> sections, <bytes> bytes)`
2. Confirm the section count matches the number of `sections/*.md` files you expected
3. Open the file (or unzip it) to confirm a valid ZIP/OOXML structure, not a truncated write
4. Confirm heading numbering is sequential and that Abstract and References stayed unnumbered
5. Confirm page numbers appear from page 2 onward

## Workflow

1. Confirm the manuscript is in Word mode: `output_format: word` (or `both`) in `config.yaml`
2. Confirm `<dir>/sections/*.md` exists; if the manuscript is LaTeX-only, there is no supported
   conversion path, so tell the user rather than improvising one
3. Read `<dir>/config.yaml` for the title, authors, and journal
4. Rewrite any section content that falls outside the supported Markdown subset above
5. Run `npm ci` in `templates/word/` if `node_modules/` is absent
6. Run `build-docx.js` with `--manuscript` and `--out`
7. Validate the output as above and report the real path written

## Planned, not implemented

The following are specified in `templates/word/article-imrad.md` (and, for the two letter documents,
in `templates/word/cover-letter.md` and `templates/word/response-to-reviewers.md`), but
`build-docx.js` does not generate them today. Never present them to the user as working. If the user
needs one, say plainly that it is not implemented and offer the LaTeX path, which does support all of
them.

- **Table formatting:** mapping `booktabs` rules to Word border styles, cell alignment, captions,
  auto-numbering
- **Figures:** embedded images, captions, auto-numbering, alt text
- **Tracked changes:** real Word revision marks for insertions, deletions, and moves
- **Comment annotations:** Word comments anchored to text ranges
- **Cross-references:** updateable Word fields for figures, tables, equations, and sections
- **Bibliography:** a references list generated from `library.bib` and formatted to the
  `citation_style` in `config.yaml`
- **Journal templates:** applying a journal-provided `.dotx` or `.docx` template
- **Cover letters and response-to-reviewers documents:** `build-docx.js` builds an IMRaD article from
  `sections/*.md` only; it has no other document mode

## Integrity constraints

- Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it; never invent a DOI, author list, venue, or year.
- Never invent data: only user-provided or actually computed numbers may appear as results. Anything illustrative must be labeled "(synthetic, for demonstration)".
- Validate the generated DOCX (generation script exits cleanly, file opens) before delivery.
- Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).

Canonical copy: `references/integrity-constraints.md`.
