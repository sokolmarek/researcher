# MLA 9th Edition: Quick Reference

Loaded by citation-management and journal-formatting skills. Standard for humanities (literature, languages, arts).

## In-Text Citations

- Parenthetical: (Smith 45), author + page, no comma
- Two authors: (Smith and Jones 112)
- Three+ authors: (Smith et al. 78)
- Narrative: Smith argues that "quoted text" (45).
- No page: (Smith), for web sources or entire works
- Multiple works: (Smith 45; Jones 78)
- Corporate author: (United Nations 12)

## Works Cited Format

### Core Elements (in order)
1. Author.
2. "Title of Source."
3. *Title of Container*,
4. Other contributors,
5. Version,
6. Number,
7. Publisher,
8. Publication date,
9. Location (pages, URL, DOI).

### Journal Article
Smith, John, and Jane Doe. "Title of Article." *Journal Name*, vol. 12, no. 3, 2023, pp. 45-67. https://doi.org/xxxxx.

### Book
Smith, John. *Title of Book*. Publisher, Year.

### Book Chapter
Smith, John. "Title of Chapter." *Title of Book*, edited by Jane Doe, Publisher, Year, pp. 45-67.

### Website
Smith, John. "Title of Page." *Website Name*, Publisher, Day Month Year, URL.

### Conference Paper
Smith, John. "Title of Paper." *Conference Name*, Day Month Year, City. Publisher, Year.

## Key Rules

- Italicize titles of containers (journals, books, websites)
- Quotation marks for titles of sources within containers (articles, chapters)
- No "p." or "pp." in parenthetical citations; use "pp." in Works Cited
- Hanging indent: 0.5 inches
- Double-spaced
- Alphabetical by author surname
- Use DOI when available; otherwise URL
- Access date only when no publication date exists
- Title case for all titles

## LaTeX Implementation

```latex
\usepackage[style=mla-new]{biblatex}
\addbibresource{references/library.bib}
```

## Page Formatting (MLA standard)
- 1-inch margins all sides
- 12pt Times New Roman
- Double-spaced throughout
- Header: Last name + page number, right-aligned
- First page: name, instructor, course, date (left-aligned, double-spaced)
- Title: centered, no bold/italic/underline
- Indent paragraphs 0.5 inches
