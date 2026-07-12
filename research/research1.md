# Analysis and Improvement Plan: `Imbad0202/academic-research-skills` (ARS)

## TL;DR
- **ARS is a genuinely mature, prompt-driven Claude Code skill suite (v3.12.1, ~553 commits, ~1,500+ passing tests, CI, CONTRIBUTING, Zenodo DOI, multilingual READMEs)** that orchestrates a human-in-the-loop research→write→review→revise→finalize pipeline — it is far more polished than a typical skills repo, so the meaningful "gaps" are architectural, not basic hygiene. Its three decisive weaknesses are: (1) literature *retrieval* is delegated to the LLM's built-in WebSearch (the Semantic Scholar/OpenAlex/Crossref/arXiv Python clients are used only for post-hoc citation-*existence verification*, with no RAG, no vector store, no full-text/GROBID ingestion); (2) a **CC BY-NC 4.0 license that is not OSI open-source and forbids commercial use**; and (3) hard lock-in to Claude Code (not pip-installable, no MCP server, no standalone runtime).
- **State-of-the-art open systems close exactly these gaps:** PaperQA2 (agentic RAG with reranking + citation traversal + GROBID parsing; 85.2% ± 1.1% precision on LitQA2 vs. human annotators' 73.8% ± 9.6%), STORM/Co-STORM (multi-perspective grounded long-form generation), GPT Researcher and LangChain Open Deep Research (configurable multi-agent deep research with MCP support), and a rich MCP ecosystem (paper-search-mcp across 20+ sources, zotero-mcp with Unpaywall/Scite integration, Academix aggregating OpenAlex/Crossref/S2/arXiv/DBLP with BibTeX export).
- **The recommended build is a hybrid, Apache-2.0-licensed system** — a deterministic Python core (multi-source retrieval + verified RAG + citation pipeline) exposed simultaneously as (a) an MCP server, (b) a pip-installable CLI/library, and (c) a thin Agent Skills layer that keeps ARS's best ideas (integrity gates, claim-faithfulness auditing, human-in-the-loop checkpoints). Build it in phases: Phase 1 relicense + MCP wrapper + PyPI packaging (quick wins); Phase 2 verified RAG + Zotero/CSL citation pipeline; Phase 3 multi-agent deep-research orchestration + evals; Phase 4 advanced agentic capabilities (contradiction detection, systematic-review automation, provenance ledger).

---

## Key Findings

1. **ARS is not a toy.** It ships 4 skills / 27 modes, a 10-stage orchestrator, ~1,500+ pytest tests (baseline grew from 694 at v3.8.2 to 1,561 by v3.9.4.1), GitHub Actions CI ("spec-consistency" + pytest workflows), CONTRIBUTING.md, SECURITY.md, CITATION.cff, a Zenodo DOI (10.5281/zenodo.20696614), CHANGELOG, four-language READMEs, and a Claude Code plugin marketplace manifest. Most "missing community infrastructure" one might anticipate is *already present*. The improvement opportunity is therefore about **architecture and openness**, not repo hygiene.

2. **The core architectural limitation is retrieval.** ARS finds papers by instructing Claude to run WebSearch/WebFetch. Its Python clients (`semantic_scholar_client.py`, `arxiv_client.py`, `verify_passport.py`, the four-index `verification_gate`) exist *only* to verify that already-cited references exist and to flag hallucinated/contaminated citations (Levenshtein ≥0.70 title matching, DOI-mismatch detection, `lookup_verified ∈ {true,false,unresolvable}`, SQLite cache at `~/.cache/ars/verification.db`). There is **no vector database, no embeddings, no GROBID/full-text parsing, no reranking, no citation-graph traversal** for *retrieval*. This is the single biggest capability gap versus PaperQA2.

3. **Licensing blocks the stated goal.** ARS is CC BY-NC 4.0. Creative Commons explicitly recommends against using CC licenses for software, and the NonCommercial clause is not OSI-approved and forbids commercial use — so ARS cannot be the base of a truly "open-source tool." A greenfield build under Apache-2.0 or MIT is required.

4. **Distribution is locked to one vendor.** `pyproject.toml` contains only pytest config (no `[project]`/`[build-system]` table), so ARS is **not pip-installable** and not on PyPI. It runs only inside Claude Code (or the sibling Codex distribution / claude.ai Projects) and requires an `ANTHROPIC_API_KEY`. There is no MCP server, no model-agnostic runtime, and the substantive functionality cannot run without an Anthropic model. Dev dependencies are trivial (`pyyaml`, `ruamel.yaml`, `jsonschema[format]`, `pypdf`, `defusedxml`; API clients use stdlib `urllib`).

5. **The competitive frontier is deterministic, model-agnostic, and interoperable.** The best open systems (a) call bibliographic APIs directly for retrieval, (b) parse full text and build local indexes, (c) expose themselves via MCP so any agent host can use them, (d) integrate reference managers (Zotero) and citation standards (CSL/BibTeX/RIS), and (e) publish benchmark numbers (LitQA2, DeepResearchGym, Deep Research Bench).

---

## Details

### (a) What the repo currently is and does

**Identity & scale.** `Academic Research Skills for Claude Code` by Cheng-I Wu (吳政宜), v3.12.1 (2026-06-15), tens of thousands of GitHub stars, ~553 commits, CC BY-NC 4.0, Zenodo DOI. Tagline: "research → write → review → revise → finalize." Explicit philosophy: **"AI is your copilot, not the pilot"** — deliberately human-in-the-loop rather than fully autonomous, motivated by the failure modes of autonomous systems (it cites Sakana's *The AI Scientist* and its enumerated failure modes: hallucinated results, citation hallucination, methodology fabrication, frame-lock).

**The four skills:**
- **deep-research (v2.10.0)** — 13-agent research team; 8 modes (full, quick, review, lit-review, three-way-scan, fact-check, socratic, systematic-review); PRISMA support; Socratic guided mode with intent detection and dialogue-health monitoring; optional cross-model devil's-advocate; Semantic Scholar existence verification.
- **academic-paper (v3.2.0)** — 12-agent writing pipeline; 11 modes (full, plan, outline-only, revision, revision-coach, abstract-only, lit-review, format-convert, citation-check, disclosure, rebuttal-audit); Style Calibration, Writing Quality Check, LaTeX hardening, VLM figure verification, anti-leakage protocol; outputs Markdown + DOCX (Pandoc) + LaTeX/PDF (tectonic, apa7).
- **academic-paper-reviewer (v1.10.0)** — 7-agent peer review; 6 modes; 0–100 rubrics (EIC + 3 reviewers + Devil's Advocate); concession-threshold protocol; R&R traceability matrix; calibration mode with FNR/FPR against a user gold set.
- **academic-pipeline (v3.12.1)** — 10-stage orchestrator with mandatory integrity gates (Stage 2.5 pre-review, Stage 4.5 final), a "Material Passport" artifact ledger, claim-verification, compliance agent (PRISMA-trAIce + RAISE), collaboration-depth observer, and score-trajectory tracking.

**Notable engineering strengths (real and unusual):**
- A **deterministic citation-existence gate** (v3.11.0) that cross-checks every cited reference against S2 + OpenAlex + Crossref + arXiv independently of the LLM, with an opt-in strict terminal policy and a persistent SQLite cache.
- A **claim-faithfulness audit** (v3.8, `ARS_CLAIM_AUDIT=1`): three-layer citation anchors (quote/page/section) plus an audit pass that fetches the cited source and judges whether the claim is actually supported, gate-refusing five HIGH-WARN classes, calibrated against a 20-tuple gold set (FNR<0.15, FPR<0.10).
- A **temporal-integrity verifier** (v3.9.4) covering 5 temporal failure modes.
- A **user-corpus intake port** (`literature_corpus[]` on the Material Passport) with reference adapters for a PDF folder, Zotero (Better BibTeX JSON), and Obsidian.
- Honest engineering discipline: data_access_level / task_type metadata, benchmark-report JSON schema, reproducibility-lock caveats ("configuration documentation, not replay guarantee"), extensive CI lints, and a codex/Gemini cross-model review chain.

**How retrieval actually works.** Prompt-driven: agents like `bibliography_agent` instruct Claude to run systematic WebSearch with Boolean strategies and PRISMA-style flow. The Python API clients do **not** retrieve into a corpus; they verify. The only file ingestion is `scripts/adapters/folder_scan.py` reading a user's own PDFs into the passport (no chunking/embedding).

**Distribution & dependencies.** Installed as a Claude Code plugin (`/plugin marketplace add …`) or via git-clone + symlink. `pyproject.toml` = pytest config only (not a package). Requires Claude Code + `ANTHROPIC_API_KEY`; the substantive research/write/review path cannot run standalone.

### (b) Detailed gap analysis

| Dimension | ARS today | Gap / weakness |
|---|---|---|
| **Literature retrieval** | LLM WebSearch, prompt-driven | No deterministic multi-source API retrieval; no vector store/embeddings; no full-text/GROBID parsing; no reranking; no citation-graph traversal for discovery. Recall/coverage and reproducibility depend on an opaque web-search tool. |
| **Citation/reference management** | Existence verification + LaTeX/APA formatting; Zotero *intake* adapter | No first-class CSL engine; no BibTeX/RIS/CSL-JSON export of the generated bibliography back into Zotero/Mendeley; no round-trip library sync; no `.bib`/`citeproc` pipeline. |
| **Database/API integration** | S2/OpenAlex/Crossref/arXiv for *verification only* | No PubMed/Europe PMC, no Unpaywall OA resolution for full text, no Scite smart-citations, no OpenCitations, no CORE, no DBLP, no institutional/ORCID/ROR enrichment as a retrieval layer. |
| **Interoperability** | Claude Code plugin + Codex sibling | No MCP server; no model-agnostic runtime; can't be consumed by Cursor/Copilot/Gemini CLI/LangGraph without reimplementation. |
| **Packaging/distribution** | Plugin only | Not pip-installable; not on PyPI; no Docker; no standalone CLI for the substantive workflow. |
| **License** | CC BY-NC 4.0 | Not OSI open-source; NonCommercial clause blocks the stated open-source goal; CC advises against CC-for-software. |
| **Automation** | Interactive, human-gated by design | No unattended/batch mode, no scheduled monitoring ("watch new papers on topic X"), no CI-runnable research jobs. |
| **Evaluation** | Strong internal lint/schema tests + claim-audit calibration gold set | No public task-level accuracy benchmark (e.g., LitQA2, DeepResearchGym); tests validate *contracts/schemas*, not *research quality*. |
| **Domain breadth** | Empirical / HSS / Information-Systems-leaning (Basket-of-11 journals, APA/Chicago/MLA/IEEE/Vancouver) | No STEM full-text figure/table/equation extraction pipeline; no data/code-artifact evaluation; biomedical (MeSH/PICO) workflows absent. |
| **Model dependency** | Anthropic-only substantive path | No local/open-weights option; cost tied to Claude; no offline mode for the research itself. |

### (c) Landscape comparison — what better systems do

- **PaperQA2 (Future-House/paper-qa, open source).** Agentic RAG for scientific PDFs with metadata-aware embeddings, LLM re-ranking and contextual summarization (RCS), a citation-traversal tool, retraction checks, and multi-provider metadata backfill. Per Skarlinski et al. (arXiv:2409.13740), PaperQA2 "achieved superhuman precision" on LitQA2 — **precision of 85.2% ± 1.1% and accuracy of 66.0% ± 1.2%**, versus human annotators' **73.8% ± 9.6% precision and 67.7% ± 11.9% accuracy** (t(8.6)=3.49, p=0.0036) — while responsibly answering "insufficient information" on 21.9% ± 0.9% of questions. Its WikiCrow variant "produces summaries that are more accurate on average than actual articles on Wikipedia that have been written and curated by humans, as judged by blinded PhD and postdoc-level biology researchers," at ~$1–3/query. This is the reference design for *verified retrieval*, which ARS lacks entirely.
- **FutureHouse platform (Crow/Falcon/Owl/Phoenix/Finch; Robin orchestrator, open-sourced).** Specialized agents over full-text + specialized DBs (OpenTargets), API-accessible, transparent reasoning traces; Robin chains them into end-to-end discovery (it identified ripasudil as a novel dAMD candidate, published in *Nature*). Its ContraCrow contradiction-detection work found, on average, **2.34 statements per paper contradicted by other papers elsewhere in the biology literature** — demonstrating the *multi-agent-over-real-databases* pattern, API-first automation (continuous literature monitoring), and scaled claim verification.
- **STORM / Co-STORM (stanford-oval/storm).** Multi-perspective question-asking → outline → grounded long-form article with citations; Co-STORM adds human-in-the-loop collaborative discourse. Reference design for grounded long-form synthesis; its known weaknesses (source-bias transfer, spurious connections between independent facts, missing recent events) validate ARS's integrity-gate philosophy.
- **GPT Researcher (assafelovic) & LangChain Open Deep Research.** Configurable, model-/search-agnostic multi-agent deep research (planner/executor/editor/reviewer/reviser/writer/publisher), local + web + MCP sources, export to PDF/DOCX/MD/JSON, and *published benchmark placement* (GPT Researcher cites top DeepResearchGym results; Open Deep Research reports a Deep Research Bench top-ranking with an overall score of 0.4344). Reference design for openness + benchmarking + MCP-native tooling.
- **MCP academic ecosystem.** `paper-search-mcp` / `aigroup-paper-mcp` (search+download across arXiv, PubMed, bioRxiv/medRxiv, Semantic Scholar, Crossref, OpenAlex, PMC/Europe PMC, CORE, DBLP, DOAJ, Zenodo, HAL, SSRN, Unpaywall, with OA-fallback download); `Academix` (OpenAlex/DBLP/S2/arXiv/Crossref aggregation with smart-ID resolution, BibTeX export, citation-network data); `zotero-mcp` (54yyyu) with add-by-DOI, Unpaywall/arXiv/S2/PMC OA cascade, Scite citation tallies, retraction alerts, local + web-API modes. This ecosystem already provides the retrieval + citation-export layer ARS is missing — and does so as reusable MCP servers.
- **Commercial reference points (feature targets, not open source).** Elicit (systematic screening + structured data extraction across **138+ million academic papers and 545,000 clinical trials**, evidence tables up to ~20,000 cells), Consensus (evidence meter, Q1–Q4 + methodology filters over 200M+ papers), Scite (Smart Citations over **1.6 billion citation statements extracted from 280 million articles**: supports/contrasts/mentions), Semantic Scholar (TLDRs, citation-graph, 200M+ papers). These define the *product* features a great open tool should approximate.
- **Autonomy caution.** Sakana's *The AI Scientist-v2* (first AI paper through workshop peer review at ICLR 2025) and its critiques document the failure modes of full autonomy; the "Why LLMs Aren't Scientists Yet" analyses reinforce that verification of AI outputs is time-intensive and that novelty/domain-justification remain weak. ARS's human-in-the-loop stance is *correct*; the improved system should keep it while adding deterministic retrieval and verification.

### (d) The full improvement plan

**Design thesis.** Build a new project — call it **`scholar-forge`** (placeholder) — as an **Apache-2.0**, model-agnostic, deterministic Python core with three co-equal front-ends: an **MCP server**, a **pip-installable CLI/library**, and a thin **Agent Skills** layer. Port ARS's genuinely novel ideas (integrity gates, claim-faithfulness anchors + audit, Material Passport provenance, human-in-the-loop checkpoints) onto a real retrieval + citation engine. Keep humans in the loop by default; add opt-in automation for batch/monitoring.

**Text architecture diagram.**
```
                         ┌──────────────────────────────────────────────┐
   Front-ends            │  MCP server  │  CLI / Python lib  │  Skills    │
   (any of 3)            └──────┬───────┴─────────┬──────────┴─────┬──────┘
                                │                 │                │
                         ┌──────▼─────────────────▼────────────────▼──────┐
   Orchestration         │  Agent orchestrator (LangGraph-style DAG):      │
                         │  Planner → Retriever → Reader → Synthesizer →   │
                         │  Reviewer → Reviser → Integrity Gate → Formatter│
                         └──────┬───────────────┬───────────────┬─────────┘
                                │               │               │
             ┌──────────────────▼──┐  ┌─────────▼────────┐  ┌────▼───────────────┐
   Core      │ Retrieval layer     │  │ Verified RAG     │  │ Citation pipeline  │
   services  │ multi-source fan-out│  │ full-text parse  │  │ CSL/BibTeX/RIS     │
             │ + dedup + rerank    │  │ (GROBID) + chunk │  │ Zotero round-trip  │
             │ + citation graph    │  │ + embed + RCS    │  │ + existence gate   │
             └──────────┬──────────┘  └────────┬─────────┘  └────────┬───────────┘
                        │                       │                    │
             ┌──────────▼───────────────────────▼────────────────────▼──────────┐
   Data      │ Connectors: OpenAlex · Crossref · Semantic Scholar · arXiv ·      │
   sources   │ PubMed/Europe PMC · Unpaywall · CORE · DBLP · OpenCitations ·     │
             │ Scite (opt) · ORCID/ROR · user Zotero library · local PDF corpus  │
             └──────────────────────────────────────────────────────────────────┘
   Cross-cutting: SQLite/DuckDB cache · vector store (LanceDB/Chroma) · provenance ledger · eval harness
```

**Proposed repository structure.**
```
scholar-forge/
├── pyproject.toml            # real [project] + [build-system]; PyPI-publishable
├── LICENSE                   # Apache-2.0
├── README.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md  CITATION.cff
├── CHANGELOG.md              # Keep a Changelog + SemVer
├── docs/                     # mkdocs-material site; ARCHITECTURE.md, tutorials, ADRs
├── src/scholar_forge/
│   ├── connectors/           # one module per source; shared BaseConnector
│   │   ├── openalex.py crossref.py semantic_scholar.py arxiv.py
│   │   ├── pubmed.py europepmc.py unpaywall.py core.py dblp.py opencitations.py
│   │   └── zotero.py         # read + WRITE (round-trip)
│   ├── retrieval/            # fan-out search, dedup (DOI/title/fuzzy), rerank, graph traversal
│   ├── rag/                  # GROBID/pdf parse → chunk → embed → RCS rerank/summarize
│   ├── ingest/               # PDF/HTML/DOCX loaders; local corpus + OA download w/ fallback
│   ├── citations/            # CSL (citeproc), BibTeX/RIS/CSL-JSON, existence + faithfulness gates
│   ├── agents/               # planner, retriever, reader, synthesizer, reviewer, reviser
│   ├── pipeline/             # LangGraph DAG orchestrator; checkpoints; Material-Passport ledger
│   ├── integrity/            # claim-anchor audit, temporal audit, contradiction detection
│   ├── models/               # provider-agnostic LLM router (LiteLLM); local/open-weights support
│   ├── cache/                # SQLite/DuckDB + vector store adapters
│   ├── mcp/                  # FastMCP server exposing tools/resources/prompts
│   ├── cli/                  # `sf search|review|write|verify|monitor` (Typer)
│   └── config.py
├── skills/                   # Agent Skills (SKILL.md) that call the CLI/MCP deterministically
│   ├── literature-review/ systematic-review/ paper-writer/ peer-reviewer/ citation-audit/
├── evals/                    # LitQA2-style QA, retrieval recall@k, citation-faithfulness, DeepResearch tasks
├── tests/                    # unit + integration + connector VCR cassettes
├── benchmarks/               # reproducible harness + published result JSON
├── examples/                 # end-to-end notebooks + showcase artifacts
├── docker/                   # Dockerfile + compose (server + GROBID + vector DB)
└── .github/                  # workflows (ci, release, docs, benchmark), issue/PR templates, dependabot
```

**Feature specs (module by module).**
1. **Connectors.** A `BaseConnector` contract (`search`, `get_by_id`, `resolve_doi`, `get_citations`, `get_references`, `get_oa_pdf`) with per-source rate-limit/polite-pool handling (OpenAlex `mailto` for the polite pool + its ~100k calls/day guidance, S2 key, Crossref etiquette), returning a canonical **CSL-JSON** record. Free-first, key-optional (mirroring paper-search-mcp). OA full-text via Unpaywall → arXiv → PMC → CORE cascade. Note real-world metadata quirks (e.g., Elsevier/ACS deposit no abstracts to Crossref; OpenAlex document-type noise) and surface source-coverage tradeoffs explicitly.
2. **Retrieval.** Concurrent multi-source fan-out; dedup by DOI, then normalized-title Levenshtein/embedding similarity; **reranking** (cross-encoder or LLM); **citation-graph traversal** (forward/backward via OpenAlex/OpenCitations) for recall — the PaperQA2 lesson. Emit a reproducible search-provenance record (query, sources, filters, hit counts) for PRISMA.
3. **Verified RAG.** GROBID (or `pypdf`/`pymupdf` fallback) → structured sections → semantic chunking → embeddings (configurable: OpenAI, local `bge`/`nomic`) → LanceDB/Chroma → **RCS** (metadata-aware retrieval, LLM re-rank, contextual summarize) → answers with span-level citations. Local-only mode fully supported (offline research).
4. **Citation pipeline.** citeproc-py + the CSL styles repo for APA/Chicago/MLA/IEEE/Vancouver + arbitrary `.csl`; export BibTeX/RIS/CSL-JSON; **write-back to Zotero** via the Web API (add-by-DOI with OA-PDF attach, collections, tags) — the zotero-mcp feature set. Port ARS's existence gate + three-layer claim-faithfulness audit + retraction checks (Retraction Watch/OpenAlex `is_retracted`); optionally surface Scite support/contrast signals.
5. **Agents & pipeline.** LangGraph DAG: Planner (decompose question, choose sources) → Retriever → Reader/Extractor (structured data columns, Elicit-style) → Synthesizer (STORM-style multi-perspective outline → grounded draft) → Reviewer (ARS EIC + panel rubric) → Reviser → **Integrity Gate** (mandatory, non-skippable) → Formatter. Human checkpoints on by default; `--auto` for unattended runs; `monitor` for scheduled new-paper alerts (FutureHouse pattern).
6. **MCP server.** FastMCP exposing tools (`search_papers`, `get_paper`, `download_oa`, `rag_query`, `verify_citations`, `export_bibliography`, `zotero_add`), resources (cached corpora), and prompt templates (lit-review, systematic-review). This alone makes the whole system usable from Claude, Cursor, Copilot, Gemini CLI, and LangGraph.
7. **Model router.** LiteLLM-based provider abstraction; supports Anthropic/OpenAI/Google **and** local open-weights (Ollama/vLLM), removing single-vendor lock-in and enabling cost/privacy control.

**Citation pipeline design (end-to-end).** Ingest (connector CSL-JSON or Zotero export) → normalize/dedup → RAG answers carry `{source_id, locator: quote|page|section}` anchors → draft renders `[@key]` markers → citeproc renders the chosen CSL style → **existence gate** (multi-index DOI/arXiv lookup) → **faithfulness gate** (fetch source at anchor, LLM-judge support, refuse HIGH-WARN) → **retraction/temporal audit** → export `.bib`/CSL-JSON + optional Zotero write-back. Every step logged to a provenance ledger (ARS Material Passport, generalized and JSON-Schema'd).

**Evaluation & testing strategy.**
- **Research-quality evals (new, public):** LitQA2 / LAB-Bench-style QA accuracy (target: approach PaperQA2's 85.2% precision on a shared subset); retrieval recall@k and dedup precision on a labeled set; citation-faithfulness FNR/FPR against a gold set (port ARS's calibration harness, thresholds FNR<0.15/FPR<0.10); long-form grounding on a FreshWiki-style set; submit to **DeepResearchGym / Deep Research Bench** for external, comparable numbers.
- **Skill/agent evals:** should-trigger/should-not-trigger query sets (skill-creator pattern), blind A/B with LLM judge, token/cost/latency capture per run.
- **Software tests:** connector tests with recorded HTTP cassettes (VCR) for determinism; schema-validation and lint invariants (port ARS's rigor); integration tests for the full DAG; nightly canary against live APIs.

**Packaging & distribution.**
- **PyPI**: `pip install scholar-forge` (real `[project]`/`[build-system]`); `sf` CLI via Typer; extras `[rag]`, `[zotero]`, `[local-llm]`.
- **Docker/compose**: server + GROBID + vector DB one-command up; `uvx scholar-forge-mcp` for zero-install MCP.
- **Agent Skills**: publishable to a plugin marketplace; skills call the CLI/MCP deterministically so behavior is reproducible across hosts.
- **Homebrew/pipx** for the CLI; versioned Docker images.

**Documentation plan.** mkdocs-material site: quickstart (5-min lit review), how-to guides per workflow, ARCHITECTURE.md, Architecture Decision Records, connector authoring guide, MCP integration guide (Claude/Cursor/Copilot), API reference (auto from docstrings), and a "reproducibility & limitations" page (inherit ARS's honesty about non-determinism).

**Community & governance infrastructure.**
- **LICENSE** Apache-2.0 (patent grant) — or MIT if maximal permissiveness preferred.
- **CONTRIBUTING.md**, **CODE_OF_CONDUCT.md** (Contributor Covenant), **SECURITY.md**, issue/PR templates, `good-first-issue` labels, Discussions.
- **CI/CD (GitHub Actions):** lint (ruff) + type (mypy) + tests + coverage on PR; connector-cassette job; nightly live-API canary; docs build/deploy; **release workflow** (tag → build → PyPI publish via OIDC trusted publishing → Docker push → GitHub Release from CHANGELOG); Dependabot; CodeQL; pre-commit hooks.
- **Versioning:** SemVer + Keep a Changelog; Zenodo integration for citable DOIs per release; CITATION.cff.

**Phased roadmap with concrete deliverables.**

- **Phase 0 — Foundations (Weeks 1–2).** New Apache-2.0 repo; real `pyproject.toml`; CI skeleton; `BaseConnector`; OpenAlex + Crossref + arXiv connectors returning CSL-JSON; SQLite cache; unit tests + cassettes. *Deliverable:* `sf search "<query>"` returns deduped, cited results from 3 sources; published to TestPyPI.
- **Phase 1 — Quick wins & interoperability (Weeks 3–6).** Add Semantic Scholar, PubMed/Europe PMC, Unpaywall (OA download w/ fallback), DBLP. Port ARS's **citation-existence gate** as `sf verify`. Ship the **MCP server** (FastMCP) and BibTeX/RIS/CSL-JSON export + **Zotero read/write**. *Deliverable:* usable from Claude/Cursor/Copilot as an MCP server; PyPI 0.1; Docker image.
- **Phase 2 — Verified RAG & citation faithfulness (Weeks 7–12).** GROBID ingestion, chunk+embed, vector store, RCS retrieval; span-anchored answers; port ARS's **three-layer claim-faithfulness audit** + temporal audit + retraction checks; local-LLM mode via LiteLLM/Ollama. *Deliverable:* `sf ask`/`rag_query` with verified inline citations; first **LitQA2-style eval** numbers published.
- **Phase 3 — Multi-agent deep research & synthesis (Weeks 13–20).** LangGraph DAG (planner→…→integrity gate→formatter); STORM-style outline + grounded long-form; Elicit-style structured extraction tables; reviewer panel + R&R matrix; Material-Passport provenance ledger; human checkpoints + `--auto`. *Deliverable:* end-to-end lit review + systematic review (PRISMA flow), DOCX/LaTeX/MD output; submit to **Deep Research Bench / DeepResearchGym**.
- **Phase 4 — Advanced agentic capabilities (Weeks 21+).** Scaled **contradiction detection** (ContraCrow-style), scheduled literature **monitoring** pipelines, citation-graph hypothesis/gap finding (Owl-style "has anyone done X"), figure/table/equation extraction for STEM, dataset/code-artifact evaluation hooks, multi-agent cross-model verification. *Deliverable:* autonomous-but-audited research jobs runnable in CI, with full provenance and integrity gates.

**Migration/attribution note.** Because ARS is CC BY-NC, its *text* (SKILL.md prose, references) cannot be copied into an Apache-2.0 codebase without permission; re-implement its *ideas* (gates, anchors, passport) as original code/specs, and credit ARS in NOTICE/docs. This keeps the new project cleanly and truly open-source.

---

## Recommendations

1. **Start greenfield under Apache-2.0; do not fork ARS.** The license and the plugin-only, retrieval-by-WebSearch architecture are load-bearing constraints you cannot fix in place. Re-implement ARS's ideas as original code. *Threshold to reconsider:* if the author relicenses ARS under an OSI license, a fork becomes viable.
2. **Lead with the MCP server + PyPI packaging (Phase 1).** This is the highest-leverage quick win: it instantly makes the tool usable from every major agent host and unblocks community contribution, while ARS remains Claude-only. *Benchmark to advance:* MCP server passes an integration test from ≥2 hosts (Claude + Cursor) and `pip install` works on a clean machine.
3. **Make deterministic, verified RAG the core differentiator (Phase 2).** This is where ARS is weakest and PaperQA2 is strongest. *Benchmark:* publish a LitQA2-style accuracy number and retrieval recall@k; target parity with PaperQA2's 85.2% precision on a shared subset before adding breadth.
4. **Keep human-in-the-loop as the default, add automation as opt-in.** The autonomy failure-mode literature (Sakana, "Why LLMs Aren't Scientists Yet") validates ARS's stance. Port the mandatory integrity gates. *Threshold:* only enable `--auto` for a workflow once its faithfulness gate hits FNR<0.15/FPR<0.10 on the gold set.
5. **Integrate Zotero and CSL as first-class citizens, not adapters.** Round-trip library sync + citeproc rendering + retraction/Scite signals is what turns a research agent into a tool researchers adopt daily.
6. **Publish external benchmark numbers early and often.** DeepResearchGym / Deep Research Bench / LitQA2 placement is how GPT Researcher and PaperQA2 earned trust; internal contract tests (ARS's strength) are necessary but not sufficient.

## Caveats
- **Version/date signals in ARS should be read critically.** The README cites numerous 2026-dated papers with forward-looking arXiv IDs (e.g., "Zhao et al. 2605.07723," "PaperOrchestra 2604.05018," "Kong et al. 2605.18661," "Lu et al. 2026 *Nature* 651:914-919") as design *motivations*; several could not be independently verified and may be aspirational — treat them as the project's stated inspirations, not established literature.
- **GitHub star/fork counts vary by cache** (fetches ranged widely); treat popularity as "tens of thousands of stars, rapidly growing," not a precise figure.
- **Direct file-level inspection was partially blocked** (GitHub tree pages and `raw.githubusercontent.com` refused automated access); the internal-architecture findings rest on the README, docs/ARCHITECTURE.md, CHANGELOG, and repo file listing, cross-checked against the project's own release notes. The exact, complete `scripts/`, `evals/`, and `tests/` file enumerations are reported from documented references, not a verified directory crawl.
- **Effort estimates are indicative.** Week ranges assume a small dedicated team; GROBID/vector-store ops and connector rate-limit handling are the most likely to slip.
- **Benchmark comparability is imperfect.** LitQA2 is biology-centric and DeepResearchGym/Deep Research Bench measure general deep research; a humanities/IS-focused tool (ARS's niche) may need a bespoke eval set, which itself is a deliverable.