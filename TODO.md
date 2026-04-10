# Researcher Plugin — Build TODO

## Phase 1: Scaffolding & Configuration
- [x] Create directory structure
- [x] Create `.claude-plugin/plugin.json`
- [x] Create `CLAUDE.md`
- [x] Create `TODO.md`
- [x] Create `README.md` (user-facing documentation with installation instructions, usage examples, supported features)
- [x] Create `LICENSE` (MIT)
- [x] Create `.gitignore` (ignore `node_modules/`, `*.aux`, `*.log`, `*.synctex.gz`, `*.pdf`, `.DS_Store`)

## Phase 2: Core Skills (build these first — everything else depends on them)

### 2.1 manuscript-setup/SKILL.md
- [x] Write SKILL.md frontmatter (name, description with trigger phrases)
- [x] Implement manuscript folder creation logic:
  - [x] Generate `main.tex` with `\input{}` includes for all sections
  - [x] Generate individual section files: `abstract.tex`, `introduction.tex`, `methods.tex`, `results.tex`, `discussion.tex`, `conclusion.tex`, `acknowledgments.tex`
  - [x] Generate `references/library.bib` with header template
  - [x] Create `figures/` and `tables/` subdirectories
  - [x] Generate `manuscript/config.yaml` (title, authors, journal, citation-style, output-format)
  - [x] Support Word mode: create `.md` section files + `build-docx.js` build script
  - [x] Support "both" mode: create LaTeX + Word scaffolding together
- [x] Create default `main.tex` template in `templates/latex/article-imrad.tex`
- [x] Create elicitation flow: ask user for title, authors, journal, format, citation style

### 2.2 paper-drafting/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement outline mode:
  - [x] Generate hierarchical outline with section → subsection → key points
  - [x] Include word allocation per section (respecting journal limits if set)
  - [x] Include figure/table placement suggestions
  - [x] Include argument flow map (claim → evidence → citation)
- [x] Implement section drafting mode:
  - [x] Abstract: structured vs unstructured format
  - [x] Introduction: funnel structure pattern (broad context → specific problem → gap → contribution → paper overview)
  - [x] Methods: reproducibility-focused, appropriate detail level
  - [x] Results: data-driven narrative, figure/table references
  - [x] Discussion: interpretation → literature comparison → limitations → implications → future work
  - [x] Conclusion: summary → contributions → outlook
- [x] Implement cross-referencing: maintain `\label`/`\ref` consistency
- [x] Implement terminology tracker: ensure consistent term usage across sections
- [x] Load style profile from `style-profile.yaml` if it exists
- [x] Support drafting requirements (user can specify constraints like "emphasize novelty", "keep under 500 words")

### 2.3 literature-search/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement search query construction from natural language research question
- [x] Implement multi-source search dispatcher:
  - [x] Scite (via MCP connector if available)
  - [x] PubMed (via NCBI E-utilities API)
  - [x] Semantic Scholar (via S2 API)
  - [x] arXiv (via API)
  - [x] Google Scholar (via Claude web search)
  - [x] CrossRef (via API)
- [x] Implement result deduplication (by DOI, title similarity)
- [x] Implement result ranking (relevance, recency, citation count)
- [x] Implement result presentation format: title, authors, year, abstract snippet, citations, DOI, source
- [x] Implement auto-add to `library.bib`
- [x] Implement systematic review mode with PRISMA tracking
- [x] Add integrity constraint: NEVER fabricate or hallucinate citations
- [ ] Add reference to `references/search-strategies.md` for advanced search patterns

### 2.4 citation-management/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement `library.bib` read/write/update operations
- [x] Implement DOI resolution via CrossRef API
- [x] Implement citation key generation (authorYear format)
- [x] Implement Zotero import (via connector)
- [x] Implement Mendeley import (via connector)
- [x] Implement citation format conversion (APA ↔ IEEE ↔ Chicago ↔ Vancouver ↔ MLA)
- [x] Implement predatory journal detection (check against Beall's list criteria)
- [x] Implement retraction check (flag retracted papers)
- [x] Implement unused citation detection (bib entries not referenced in any .tex file)
- [x] Implement missing citation detection (`\cite{key}` where key not in .bib)
- [x] Create `scripts/bib-validator.py` for batch validation

## Phase 3: Output Skills

### 3.1 latex-tables/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement `booktabs`-style table generation (no vertical rules)
- [x] Support multi-column (`\multicolumn`) and multi-row (`\multirow`)
- [x] Support automatic column width calculation
- [x] Support statistical significance markers (*, **, ***)
- [x] Support bold-best-result highlighting
- [x] Support table notes and footnotes (`\tablenote{}`)
- [x] Support landscape tables (`sidewaystable`)
- [x] Support longtable for multi-page data
- [x] Implement CSV/JSON → LaTeX table conversion
- [x] Implement Word table equivalent output (via docx-js)
- [ ] Include common table patterns in `references/table-patterns.md`

### 3.2 tikz-diagrams/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement diagram type detection from description
- [x] Create TikZ generation for each diagram type:
  - [x] System architecture (boxes, arrows, layers)
  - [x] Neural network architecture
  - [x] Flowchart / pipeline
  - [x] Experimental setup
  - [x] State machine / FSM
  - [x] Data flow diagram
  - [x] Comparison framework
  - [x] Timeline / Gantt chart
  - [x] Tree structures
  - [x] Mathematical plots (pgfplots)
  - [x] Commutative diagrams (tikz-cd)
- [x] Output standalone `.tex` file in `figures/`
- [x] Compile to PDF preview via tectonic
- [x] Create `references/tikz-patterns.md` with reusable patterns
- [x] Support `forest`, `pgfplots`, `circuitikz` packages

### 3.3 word-output/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement LaTeX → DOCX conversion pipeline:
  - [x] pandoc conversion as base
  - [x] Post-process with docx-js for formatting fidelity
- [x] Implement native DOCX creation for non-LaTeX workflows:
  - [x] Heading styles (Heading 1-4)
  - [x] Body text with proper font/spacing
  - [x] Table formatting
  - [x] Image embedding
  - [x] Page numbers, headers/footers
  - [x] Table of contents
- [x] Implement tracked changes for revisions (using DOCX XML tracked changes)
- [x] Implement comment annotations for review feedback
- [x] Support journal Word templates (download template → apply)
- [x] Create `templates/word/article-imrad.md` with DOCX generation spec

### 3.4 journal-formatting/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Create `references/journal-database.md` with requirements for 50+ journals:
  - [x] Elsevier journals (elsarticle class)
  - [x] Springer journals (svjour3 class)
  - [x] IEEE journals (IEEEtran class)
  - [x] ACM journals (acmart class)
  - [x] Wiley journals
  - [x] Taylor & Francis
  - [x] PLOS ONE
  - [x] Nature family
  - [x] Science family
  - [x] MDPI journals
- [x] For each journal, document: document class, word/page limits, figure format, reference limits, required sections, supplementary guidelines
- [x] Implement journal requirement lookup (from database or web search)
- [x] Implement automatic formatting application to manuscript
- [x] Implement compliance validation checklist
- [x] Create `scripts/journal-lookup.py` for web-based requirement fetching

## Phase 4: Analysis Skills

### 4.1 writing-style-analysis/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement local file analysis (read papers from `author-papers/` folder):
  - [x] Parse PDF papers to extract text
  - [x] Analyze sentence length distribution
  - [x] Analyze vocabulary complexity (Flesch-Kincaid, academic word list frequency)
  - [x] Analyze hedging patterns (may, might, suggests, potentially, arguably)
  - [x] Analyze transition word preferences
  - [x] Analyze active vs passive voice ratio
  - [x] Analyze paragraph length patterns
  - [x] Analyze citation density per section type
  - [x] Analyze section structure patterns
- [x] Implement Google Scholar profile analysis:
  - [x] Accept profile URL or author name
  - [x] Fetch available papers (titles, abstracts, and full text where accessible)
  - [x] Run same analysis pipeline
  - [x] Create `scripts/scholar-scraper.py`
- [x] Generate `style-profile.yaml` output
- [x] Implement style comparison (author style vs target journal style)
- [x] Implement style application during drafting (loaded by paper-drafting skill)

### 4.2 code-analysis/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement codebase scanning:
  - [x] Identify main algorithms and data structures
  - [x] Trace data processing pipeline
  - [x] Extract hyperparameters and configuration
  - [x] Identify evaluation metrics
  - [x] Map dependencies and frameworks
- [x] Implement methods section generation:
  - [x] Algorithm description at appropriate abstraction level
  - [x] Pseudocode generation (using `algorithm2e` or `algorithmicx`)
  - [x] Computational complexity analysis
  - [x] Framework and library documentation
  - [x] Data preprocessing documentation
- [x] Implement results section support:
  - [x] Extract evaluation configurations
  - [x] Document experimental setup from code
- [x] Create `scripts/codebase-analyzer.py` for automated extraction
- [x] Ensure this skill routes to **Sonnet subagent** for code reading

### 4.3 figure-suggestions/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement content analysis for figure needs:
  - [x] Methods section → architecture diagrams, setup diagrams
  - [x] Results section → chart type recommendation (bar, line, scatter, heatmap, box plot, violin)
  - [x] Discussion section → comparison frameworks, conceptual diagrams
- [x] Implement figure caption generation (journal-appropriate style)
- [x] Implement figure placement recommendation
- [x] Implement panel layout suggestions (Figure 2a-d arrangements)
- [x] Link to tikz-diagrams skill for actual generation
- [ ] Include data visualization best practices in references

## Phase 5: Review & Revision Skills

### 5.1 peer-review/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement multi-persona review within Claude:
  - [x] Editor-in-Chief persona: scope, novelty, significance, journal fit
  - [x] Methodology Reviewer: research design, statistical validity, reproducibility
  - [x] Domain Reviewer: literature coverage, theoretical framework, positioning
  - [x] Writing Reviewer: clarity, structure, argumentation, grammar
  - [x] Devil's Advocate: challenges core thesis, identifies logical gaps, strongest counter-arguments
- [x] Implement scoring rubric (0-100 per dimension):
  - [x] Define behavioral indicators for each score range
  - [x] Decision mapping: Accept ≥80, Minor Revision 65-79, Major Revision 50-64, Reject <50
- [x] Implement external model review (optional configuration):
  - [x] ChatGPT integration: construct review prompt → send via OpenAI API → parse response
  - [x] Gemini integration: construct review prompt → send via Google API → parse response
  - [x] Ollama integration: construct review prompt → send to local endpoint → parse response
  - [x] Review synthesis: combine all reviews into unified report
- [x] Implement review report generation (structured, actionable)
- [x] Implement re-review mode (verify revisions address original comments)
- [x] Track review history across rounds

### 5.2 revision-management/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement reviewer comment parsing:
  - [x] From plain text
  - [x] From PDF with annotations
  - [x] From Word document with comments
  - [x] From structured editorial system format
- [x] Implement revision roadmap generation:
  - [x] Map each comment to specific manuscript location
  - [x] Categorize: must-address, should-address, optional, out-of-scope (with justification)
  - [x] Priority ordering
- [x] Implement tracked changes generation:
  - [x] LaTeX: `latexdiff` integration or `changes` package markup
  - [x] Word: DOCX tracked changes (insertions, deletions, formatting changes)
- [x] Implement revision log (links each change to the triggering reviewer comment)
- [x] Support multiple rounds (R1, R2, R3) with state tracking
- [x] Implement rebuttal strategy suggestions for unfair/incorrect comments

### 5.3 response-to-reviewers/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement point-by-point response generation:
  - [x] Quote reviewer comment (italicized)
  - [x] Describe action taken
  - [x] Reference specific manuscript location (page, line, section)
  - [x] Show new text in blue / removed text in red or strikethrough
- [x] Implement diplomatic disagreement templates (with evidence)
- [x] Implement "thank reviewer" patterns (genuine but not sycophantic)
- [x] Output in LaTeX (using `templates/latex/response-to-reviewers.tex`)
- [x] Output in Word (using docx-js with appropriate formatting)
- [x] Cross-reference revision document
- [x] Maintain consistent numbering (Reviewer 1 Comment 3, etc.)

### 5.4 cover-letter/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Implement cover letter generation:
  - [x] Editor address (by name if known)
  - [x] Paper title and author list
  - [x] Contribution summary (2-3 sentences)
  - [x] Journal fit justification
  - [x] Originality and exclusivity statement
  - [x] Suggested reviewers section (optional)
  - [x] Excluded reviewers section (optional)
  - [x] Conflict of interest declaration
  - [x] Data/code availability statement
  - [x] Funding acknowledgment
- [x] Adapt tone to journal tier
- [x] Output in LaTeX and Word
- [x] Create `templates/latex/cover-letter.tex`
- [x] Create `templates/word/cover-letter.md`

## Phase 6: Implementation Skill

### 6.1 implementation/SKILL.md
- [x] Write SKILL.md frontmatter
- [x] Document that this skill dispatches to **Sonnet subagent**
- [x] Implement experiment script generation
- [x] Implement data processing pipeline generation
- [x] Implement evaluation code generation
- [x] Implement visualization script generation (matplotlib, seaborn, plotly)
- [x] Enforce reproducibility patterns:
  - [x] Random seed management
  - [x] Config file externalization
  - [x] Environment specification (requirements.txt, environment.yml, Dockerfile)
  - [x] Logging and experiment tracking
- [x] Generate `requirements.txt` / `environment.yml` / `Dockerfile` as needed

## Phase 7: Agents

### 7.1 agents/research-agent.md
- [x] Define agent role and capabilities
- [x] Specify which skills this agent orchestrates: literature-search, citation-management
- [x] Define search session state management
- [x] Define annotated bibliography building workflow
- [x] Define research gap identification logic

### 7.2 agents/writing-agent.md
- [x] Define agent role and capabilities
- [x] Specify skills: paper-drafting, writing-style-analysis, figure-suggestions
- [x] Define document-level coherence tracking
- [x] Define word count management
- [x] Define cross-referencing consistency checks

### 7.3 agents/review-agent.md
- [x] Define agent role and capabilities
- [x] Specify skills: peer-review
- [x] Define reviewer persona management
- [x] Define review synthesis workflow
- [x] Define external model coordination (ChatGPT, Gemini, Ollama)

### 7.4 agents/formatting-agent.md
- [x] Define agent role and capabilities
- [x] Specify skills: journal-formatting, latex-tables, tikz-diagrams, word-output
- [x] Define compilation validation workflow
- [x] Define journal compliance checking
- [x] Define format conversion workflow

### 7.5 agents/code-agent.md
- [x] Define agent role and capabilities
- [x] Specify skills: implementation, code-analysis
- [x] **Specify Sonnet model routing**
- [x] Define code → paper translation workflow
- [x] Define pseudocode generation workflow

### 7.6 agents/style-agent.md
- [x] Define agent role and capabilities
- [x] Specify skills: writing-style-analysis
- [x] Define style profile management
- [x] Define style application workflow
- [x] Define style comparison workflow

## Phase 8: Slash Commands

### 8.1 commands/new-manuscript.md
- [x] Define `/new-manuscript` command
- [x] Structured form: title, authors, journal, format (latex/word/both), citation style
- [x] Routes to manuscript-setup skill

### 8.2 commands/draft-section.md
- [x] Define `/draft-section` command with section parameter
- [x] Validates section name (abstract, introduction, methods, results, discussion, conclusion)
- [x] Loads manuscript context before drafting
- [x] Routes to paper-drafting skill

### 8.3 commands/review-paper.md
- [x] Define `/review-paper` command
- [x] Options: full review, quick assessment, methodology focus, re-review
- [x] Routes to peer-review skill

### 8.4 commands/submit-ready.md
- [x] Define `/submit-ready` command
- [x] Runs pre-submission checklist:
  - [x] Citation validation (all cited, all resolved)
  - [x] Formatting compliance (against target journal)
  - [x] Figure quality check
  - [x] Word count validation
  - [x] Required sections present
  - [x] Cover letter exists
  - [x] Data availability statement
- [x] Generates submission readiness report

### 8.5 commands/revise.md
- [x] Define `/revise` command with round parameter (R1, R2, R3)
- [x] Accepts reviewer comments input
- [x] Routes to revision-management + response-to-reviewers skills

## Phase 9: Connectors

### 9.1 connectors/scite.md
- [x] Document Scite MCP connector (already exists as MCP server)
- [x] Define usage patterns: smart citation search, citation context, tallies

### 9.2 connectors/zotero.md
- [x] Document Zotero integration approach:
  - [x] Check if Zotero MCP server exists; if not, use Zotero Web API v3
  - [x] Define collection listing, item retrieval, attachment access
  - [x] Define BibTeX export from Zotero collections

### 9.3 connectors/pubmed.md
- [x] Document PubMed integration via NCBI E-utilities
- [x] Define search (esearch), fetch (efetch), link (elink) operations
- [x] Include API key setup instructions

### 9.4 connectors/semantic-scholar.md
- [x] Document Semantic Scholar API integration
- [x] Define paper search, citation graph traversal, author lookup
- [x] Include API key setup instructions

### 9.5 connectors/arxiv.md
- [x] Document arXiv API integration
- [x] Define search, metadata retrieval, PDF access
- [x] Note: no API key required

### 9.6 connectors/crossref.md
- [x] Document CrossRef REST API integration
- [x] Define DOI resolution, metadata lookup, reference validation
- [x] Include polite pool (mailto parameter) setup

### 9.7 connectors/google-scholar.md
- [x] Document Google Scholar search via Claude web search
- [x] Define search patterns, result parsing
- [x] Note limitations (no official API, rate limiting)

### 9.8 connectors/mendeley.md
- [x] Document Mendeley API integration
- [x] Define library access, document retrieval, annotation sync
- [x] Include OAuth setup instructions

## Phase 10: Hooks

### 10.1 hooks/pre-commit-citation-check.md
- [x] Define hook trigger (pre-commit in manuscript folder)
- [x] Implement: scan all .tex files for \cite{} keys
- [x] Cross-check against library.bib
- [x] Flag: missing keys, uncited entries, entries without DOI
- [x] Block commit on critical issues, warn on non-critical

### 10.2 hooks/post-draft-integrity.md
- [x] Define hook trigger (after any section drafting completes)
- [x] Implement: scan drafted text for claims without citations
- [x] Check for hallucinated references (cite keys that don't resolve)
- [x] Validate \ref{}/\label{} consistency
- [x] Report integrity score (0-100)

## Phase 11: Reference Documents

- [x] Create `references/apa7-guide.md` — APA 7th edition formatting rules
- [x] Create `references/ieee-guide.md` — IEEE citation and formatting rules
- [x] Create `references/chicago-guide.md` — Chicago style (Notes & Author-Date)
- [x] Create `references/vancouver-guide.md` — Vancouver numbered citation rules
- [x] Create `references/mla-guide.md` — MLA formatting rules
- [x] Create `references/journal-database.md` — requirements for 50+ journals
- [x] Create `references/tikz-patterns.md` — reusable TikZ diagram patterns
- [ ] Create `references/table-patterns.md` — common academic table patterns
- [ ] Create `references/search-strategies.md` — literature search best practices

## Phase 12: Templates

### LaTeX Templates
- [x] Create `templates/latex/article-imrad.tex` — standard IMRaD research article
- [x] Create `templates/latex/article-review.tex` — literature review / survey paper
- [x] Create `templates/latex/conference-paper.tex` — conference submission
- [x] Create `templates/latex/response-to-reviewers.tex` — reviewer response document
- [x] Create `templates/latex/cover-letter.tex` — journal submission cover letter

### Word Template Specs
- [x] Create `templates/word/article-imrad.md` — DOCX generation specification
- [x] Create `templates/word/response-to-reviewers.md` — reviewer response DOCX spec
- [x] Create `templates/word/cover-letter.md` — cover letter DOCX spec

## Phase 13: Scripts

- [x] Create `scripts/bib-validator.py` — validate .bib entries against CrossRef DOI API
- [x] Create `scripts/latex-compile.sh` — compile LaTeX via tectonic with error handling
- [x] Create `scripts/scholar-scraper.py` — fetch author papers from Google Scholar for style analysis
- [x] Create `scripts/codebase-analyzer.py` — extract algorithms, pipelines, config from source code
- [x] Create `scripts/journal-lookup.py` — fetch journal requirements from web

## Phase 14: Testing & Polish

- [ ] Write test prompts for each skill (3-5 per skill)
- [ ] Run test prompts through skills, evaluate quality
- [ ] Iterate on skill instructions based on test results
- [ ] Write comprehensive README.md with:
  - [ ] Installation instructions (Claude Code, Cowork, standalone)
  - [ ] Quick start guide
  - [ ] Feature overview with examples
  - [ ] Configuration guide (external APIs, model routing)
  - [ ] Troubleshooting
- [ ] Optimize skill descriptions for triggering accuracy
- [ ] Package plugin for distribution
- [ ] Test installation via `/plugin install`

## Notes

- Build skills in dependency order: manuscript-setup and literature-search first, then skills that depend on their outputs
- Each SKILL.md should be under 500 lines; use references/ for long content
- Test LaTeX compilation with tectonic after every template change
- Test DOCX generation with docx-js validation after every Word output change
- External model review (ChatGPT/Gemini/Ollama) is optional — plugin must work fully with Claude alone
