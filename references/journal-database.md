# Journal Requirements Database

Loaded by journal-formatting skill. Use `scripts/journal-lookup.py` for journals not listed here.

## Elsevier Journals

### Generic Elsevier
- **Class:** `elsarticle` (options: `1p`, `3p`, `5p`, `review`, `authoryear`/`number`)
- **Citation:** Varies by journal (check specific journal). Default: numbered.
- **Figures:** EPS, PDF, TIFF (300 DPI min for photos, 600 DPI for line art)
- **Highlights:** Required. 3-5 bullet points, max 85 characters each.
- **Required sections:** Data Availability Statement, CRediT author contributions
- **Supplementary:** Separate file, referenced as "Supplementary Material"

### Pattern Recognition (Elsevier)
- **Word limit:** ~8000 words (excluding references)
- **Citation:** Numbered, [1]
- **Class:** `elsarticle` with `3p` option

### Neural Networks (Elsevier)
- **Word limit:** ~10000 words
- **Citation:** Numbered
- **Class:** `elsarticle` with `3p` option

## Springer Journals

### Generic Springer
- **Class:** `svjour3` (options: `smallextended`, `twocolumn`)
- **Citation:** Varies: numbered or author-year depending on journal
- **Figures:** EPS, PDF, TIFF (300 DPI min). Max width: 84mm (single column), 174mm (double column)
- **Required sections:** Declarations (Funding, COI, Ethics, Consent, Data Availability, Author Contributions)

### Machine Learning (Springer)
- **Word limit:** No strict limit; typical 20-30 pages
- **Citation:** Numbered, [1]
- **Class:** `svjour3` with `smallextended`

### Nature family
- **Word limit:** ~3000 words (Article), ~1500 (Letter/Communication)
- **Abstract:** 150 words max, no references
- **Figures:** Max 8 (including tables). 300 DPI min.
- **Methods:** Separate section after references (up to 3000 words)
- **References:** Max 50 (Article), 30 (Letter)
- **Citation:** Numbered, superscript
- **Required:** Data Availability, Code Availability, Author Contributions, Competing Interests

## IEEE Journals

### Generic IEEE
- **Class:** `IEEEtran` (options: `journal`, `conference`, `compsoc`, `comsoc`)
- **Citation:** Numbered, [1], IEEE style
- **Bibliography:** `IEEEtran.bst`
- **Figures:** EPS, PDF, PNG. Single column: 3.5 in. Double column: 7 in.
- **Biography:** Required for journal papers (photo + 100 words per author)

### IEEE Transactions
- **Page limit:** Typically 10-14 pages (journal), varies by transaction
- **Abstract:** Max 250 words
- **Required:** Index Terms (from IEEE taxonomy)

### IEEE Conference
- **Page limit:** Typically 6-8 pages
- **Class:** `IEEEtran` with `conference` option
- **Format:** Two-column, 10pt

## ACM Journals

### Generic ACM
- **Class:** `acmart` (options: `sigconf`, `sigplan`, `sigchi`, `acmlarge`, `acmsmall`, `acmtog`)
- **Citation:** Author-year (ACM style) or numbered
- **Required:** CCS Concepts, Keywords, ACM Reference Format
- **Figures:** PDF, PNG (300 DPI)

### ACM Conference (SIGCONF)
- **Page limit:** Varies by conference (typically 10-12 pages)
- **Class:** `acmart` with `sigconf`
- **Required:** Abstract ≤ 150 words

## Wiley Journals

- **Submission:** Often Word preferred over LaTeX
- **Citation:** Varies by journal
- **Figures:** TIFF, EPS (300 DPI min). Submit as separate files.
- **Required sections:** Data Availability, COI, Author Contributions

## Taylor & Francis

- **Submission:** Word or LaTeX
- **LaTeX:** Uses `interact` class or standard article
- **Citation:** Varies by journal (most common: APA or numbered)
- **Figures:** EPS, TIFF (300 DPI). Separate files.

## PLOS ONE

- **Class:** Standard `article` (no specific class)
- **Citation:** Vancouver numbered style, [1]
- **Word limit:** No strict limit; concise preferred
- **Figures:** TIFF, EPS (300 DPI). Max 6 main figures.
- **Required:** Data Availability, Funding, COI, Ethics, all in structured declarations
- **LaTeX template:** Available on PLOS website

## Science (AAAS)

- **Word limit:** ~2500 words (Research Article), ~3500 (Review)
- **Abstract:** 125 words max, structured as single paragraph
- **References:** Max 40 (Research Article)
- **Figures:** Max 4 figures + 2 tables
- **Citation:** Numbered, (1), Science style
- **Required:** Supplementary Materials with expanded methods

## MDPI Journals

- **Class:** `mdpi` (provided by MDPI)
- **Citation:** Numbered, [1], Vancouver-like
- **Figures:** TIFF, PNG, JPG (300 DPI min). Embedded in text.
- **Format:** Single column
- **Required sections:** Author Contributions, Funding, Data Availability, COI, Informed Consent, Ethics
- **Special:** Open access. No page/word limit (reasonable length expected).
