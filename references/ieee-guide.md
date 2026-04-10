# IEEE Citation Style — Quick Reference

Loaded by citation-management and journal-formatting skills.

## In-Text Citations

- Numbered in square brackets: [1], [2], [3]
- Ordered by first appearance in text (NOT alphabetical)
- Multiple: [1], [3], [5] or ranges: [1]–[3]
- "As shown in [4]..." or "Smith et al. [4] demonstrated..."
- Same reference cited multiple times uses same number

## Reference List Format

### Journal Article
[1] A. A. Author, B. B. Author, and C. C. Author, "Title of article," *Abbrev. Journal Title*, vol. X, no. Y, pp. xxx–xxx, Month Year, doi: 10.xxxx/xxxxx.

### Conference Paper
[2] A. A. Author, "Title of paper," in *Proc. Conf. Name (ABBREV)*, City, Country, Year, pp. xxx–xxx.

### Book
[3] A. A. Author, *Title of Book*, Edition. City, Country: Publisher, Year.

### Book Chapter
[4] A. A. Author, "Title of chapter," in *Title of Book*, E. E. Editor, Ed. City, Country: Publisher, Year, pp. xxx–xxx.

### Technical Report
[5] A. A. Author, "Title of report," Dept., Univ., City, Country, Rep. XXX, Year.

### Thesis
[6] A. A. Author, "Title of thesis," Ph.D. dissertation, Dept., Univ., City, Country, Year.

### Online/Website
[7] A. A. Author. "Title of page." Website Name. URL (accessed Month Day, Year).

### arXiv Preprint
[8] A. A. Author, "Title of paper," arXiv:XXXX.XXXXX, Year.

## Key Rules

- Author initials before surname: A. B. Smith (not Smith, A. B.)
- Use "and" before last author (not "&")
- Abbreviate journal titles per IEEE standard abbreviations
- Italicize journal and book titles
- Month abbreviations: Jan., Feb., Mar., Apr., May, Jun., Jul., Aug., Sep., Oct., Nov., Dec.
- Up to 6 authors: list all; 7+: list first 3, then "et al."
- Include DOI when available
- No hanging indent (standard paragraph indent)
- Single-spaced reference list (conference-dependent)

## LaTeX Implementation

Document class: `\documentclass[conference]{IEEEtran}` or `\documentclass[journal]{IEEEtran}`

Bibliography: `\bibliographystyle{IEEEtran}` with `\bibliography{references/library}`

Or use `biblatex` with IEEE style:
```latex
\usepackage[style=ieee]{biblatex}
\addbibresource{references/library.bib}
```

## Common IEEE Journal Abbreviations

- IEEE Transactions on Pattern Analysis and Machine Intelligence → *IEEE Trans. Pattern Anal. Mach. Intell.*
- IEEE Transactions on Neural Networks and Learning Systems → *IEEE Trans. Neural Netw. Learn. Syst.*
- IEEE Access → *IEEE Access*
- IEEE Journal of Selected Topics in Signal Processing → *IEEE J. Sel. Topics Signal Process.*
