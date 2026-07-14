# Chicago Manual of Style: Quick Reference

Loaded by citation-management and journal-formatting skills. Covers both Notes-Bibliography (NB) and Author-Date (AD) systems.

## Author-Date System (sciences, social sciences)

### In-Text
- (Smith 2023)
- (Smith 2023, 45), with page
- (Smith and Jones 2023)
- (Smith et al. 2023), for 4+ authors
- Smith (2023) argues...

### Reference List
Author Last, First M. Year. "Article Title." *Journal Title* Volume (Issue): Pages. https://doi.org/xxxxx.

Author Last, First M. Year. *Book Title*. Place: Publisher.

Author Last, First M. Year. "Chapter Title." In *Book Title*, edited by First M. Last, pages. Place: Publisher.

## Notes-Bibliography System (humanities)

### Footnotes (first citation)
1. First M. Last, *Book Title* (Place: Publisher, Year), page.
2. First M. Last, "Article Title," *Journal* Volume, no. Issue (Year): page.

### Footnotes (subsequent)
3. Last, *Short Title*, page.
4. Last, "Short Title," page.

### Bibliography
Last, First M. *Book Title*. Place: Publisher, Year.

Last, First M. "Article Title." *Journal Title* Volume, no. Issue (Year): Pages. https://doi.org/xxxxx.

## Key Rules

- Author-Date: alphabetical by surname, then chronological
- Notes-Bibliography: alphabetical by surname in bibliography; order of appearance in notes
- Up to 10 authors: list all; 11+: list first 7, then "et al."
- Italicize book and journal titles
- Article titles in quotes
- Access dates only for content that may change
- Hanging indent in bibliography/reference list

## LaTeX Implementation

Author-Date: `\usepackage[authordate,backend=biber]{biblatex-chicago}`

Notes-Bibliography: `\usepackage[notes,backend=biber]{biblatex-chicago}`
