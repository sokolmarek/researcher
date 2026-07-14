---
name: manuscript-setup
description: "Create a new academic manuscript project with organized folder structure. Triggers when user says: 'new manuscript', 'start a paper', 'create manuscript', 'new research project', 'set up paper', 'begin writing paper', 'initialize manuscript'. Creates LaTeX or Word project structure with individual files per section, bibliography, figures folder, and config. Always use this skill when the user wants to start a new academic writing project, even if they don't use the exact word 'manuscript'."
---

# Manuscript Setup

Creates a structured manuscript project in the working directory.

## Workflow

1. **Elicit project details** from user (or accept defaults):
   - Title (required)
   - Author list with affiliations (required)
   - Target journal (optional: affects template, word limits, required sections)
   - Output format: `latex` (default), `word`, or `both`
   - Citation style: `apa7` (default), `ieee`, `chicago`, `vancouver`, `mla`
   - Paper type: `imrad` (default), `review`, `case-study`, `conference`, `theoretical`

2. **Create folder structure:**

```
manuscript/
├── main.tex                    # Master document with \input{} includes
├── abstract.tex                # Abstract (structured or unstructured)
├── introduction.tex            # Introduction section
├── methods.tex                 # Methods / Materials & Methods
├── results.tex                 # Results section
├── discussion.tex              # Discussion section
├── conclusion.tex              # Conclusion section
├── acknowledgments.tex         # Acknowledgments
├── appendix.tex                # Appendix (optional sections)
├── references/
│   └── library.bib             # Bibliography database
├── figures/                    # Figure files (.pdf, .png, .eps)
│   └── .gitkeep
├── tables/                     # Standalone table files (optional)
│   └── .gitkeep
└── config.yaml                 # Project metadata and settings
```

3. **If Word mode**, create equivalent structure:
```
manuscript/
├── sections/
│   ├── abstract.md
│   ├── introduction.md
│   ├── methods.md
│   ├── results.md
│   ├── discussion.md
│   └── conclusion.md
├── references/
│   └── library.bib
├── figures/
├── tables/
└── config.yaml
```

Compile the DOCX with the shipped script, `templates/word/build-docx.js`. Install its one dependency
first (`package-lock.json` is tracked, so `npm ci` is the right command); a clean checkout has no
`node_modules/` and the script will refuse to run without it:

```
cd templates/word && npm ci && cd -
node templates/word/build-docx.js --manuscript <dir> --out paper.docx
```

Today this generates a title page, numbered headings, paragraphs, and bullet lists from
`sections/*.md`. Tables, figures, tracked changes, and comments are specified in
`templates/word/article-imrad.md` but not implemented yet, so do not tell the user those are working.

4. **If "both" mode**, create both structures side by side.

## main.tex Template

The generated `main.tex` must:
- Use appropriate document class based on target journal (default: `article`)
- Include standard packages: `amsmath`, `graphicx`, `hyperref`, `booktabs`, `natbib` or `biblatex`
- Set citation style from config
- Use `\input{}` for each section file
- Include proper `\bibliography{}` command
- If journal specified: use journal's LaTeX class if available (e.g., `elsarticle`, `IEEEtran`)

Read `templates/latex/article-imrad.tex` for the default template.

## config.yaml Format

```yaml
title: "Paper Title"
authors:
  - name: "First Author"
    affiliation: "University"
    email: "author@university.edu"
    corresponding: true
  - name: "Second Author"
    affiliation: "Institute"
journal:
  name: ""                    # Target journal name
  class: "article"            # LaTeX document class
  word_limit: null             # Word limit if known
citation_style: "apa7"
output_format: "latex"         # latex | word | both
paper_type: "imrad"            # imrad | review | case-study | conference | theoretical
created: "2026-04-09"
status: "drafting"             # drafting | review | revision | final
```

## Section File Initialization

Each section `.tex` file should be created with:
- A `\section{}` header
- A brief comment explaining what goes in this section
- Placeholder `% TODO:` markers for key content areas
- Example structure comments based on paper type

Example `introduction.tex`:
```latex
\section{Introduction}
% Structure: Context → Problem → Gap → Contribution → Paper overview

% TODO: Broad context and motivation (1-2 paragraphs)

% TODO: Specific problem statement and existing approaches (1-2 paragraphs)

% TODO: Research gap: what is missing or unsolved (1 paragraph)

% TODO: Your contribution: what this paper does (1 paragraph)
% State contributions as a numbered or bulleted list if appropriate.

% TODO: Paper overview: brief roadmap of remaining sections (1 paragraph)
```

## After Creation

- Inform user of created structure
- Suggest next steps: "You can now `/researcher:draft-section introduction` to start writing, or search literature first"
- If journal specified, mention any journal-specific requirements detected
