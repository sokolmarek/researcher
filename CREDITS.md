# Credits & Acknowledgments

Researcher is an original, MIT-licensed project, but it did not appear out of nowhere. It was shaped by a generation of open academic-tooling work. This file records the projects, tools, and data sources that inspired its design or that it builds on directly.

**On originality.** Where a project below is credited for an *idea* (an integrity gate, a retrieval pattern, a provenance ledger), that idea was re-implemented from its public description as original code. No source code was copied from any CC-licensed or non-permissive project. Where a project is a *dependency* or an integrated service, it is used through its public interface under its own license.

## Direct inspiration

- **[academic-research-skills](https://github.com/Imbad0202/academic-research-skills)** by Cheng-I Wu. The prompt-driven Claude Code skill suite that demonstrated the shape of a deliberately human-in-the-loop, integrity-first research assistant. Ideas re-implemented as original code include deterministic citation-existence checking, claim-faithfulness anchoring, a provenance "passport", mandatory integrity gates, and multi-persona review panels. (That project is CC BY-NC 4.0; nothing was copied from it.)

## Reference designs (systems we learned from)

- **[PaperQA2](https://github.com/Future-House/paper-qa)** (FutureHouse). Verified retrieval-augmented answering over scientific PDFs, with metadata-aware retrieval, reranking, contextual summarization, and citation-graph traversal. The reference design for deterministic, verified retrieval.
- **[FutureHouse platform](https://www.futurehouse.org)**. Multi-agent research over real scientific databases, continuous literature monitoring, and scaled claim/contradiction verification.
- **[STORM / Co-STORM](https://github.com/stanford-oval/storm)** (Stanford OVAL). Multi-perspective question-asking to outline to grounded long-form synthesis with citations.
- **[GPT Researcher](https://github.com/assafelovic/gpt-researcher)** and **[LangChain Open Deep Research](https://github.com/langchain-ai/open_deep_research)**. Configurable, model- and search-agnostic multi-agent deep-research pipelines with export and benchmarking.

## Commercial reference points (feature targets)

- **[Elicit](https://elicit.com)** for systematic screening and structured evidence extraction.
- **[Consensus](https://consensus.app)** for evidence synthesis and quality filtering.
- **[Scite](https://scite.ai)** for Smart Citations (supporting / contrasting / mentioning classification).
- **[Semantic Scholar](https://www.semanticscholar.org)** for TLDRs and citation-graph data.

## MCP servers and integrations

- **[Scite MCP](https://scite.ai)** for Smart Citation context.
- **[zotero-mcp](https://github.com/54yyyu/zotero-mcp)** for reference-library round-trip.
- **[paper-search-mcp](https://github.com/openags/paper-search-mcp)** for multi-source search coverage.

## Bibliographic data sources

Free, open scholarly infrastructure that makes deterministic retrieval and verification possible: **[OpenAlex](https://openalex.org)**, **[Crossref](https://www.crossref.org)**, **[arXiv](https://arxiv.org)**, **[PubMed / Europe PMC](https://europepmc.org)**, **[Unpaywall](https://unpaywall.org)**, **[OpenCitations](https://opencitations.net)**, and **[Retraction Watch](https://retractionwatch.com)**. The worked examples in `examples/` are grounded against OpenAlex, Crossref, and arXiv.

## Tooling

- **[tectonic](https://tectonic-typesetting.github.io)** for reproducible, single-binary LaTeX compilation.
- **[PlotNeuralNet](https://github.com/HarisIqbal88/PlotNeuralNet)** for the neural-network architecture diagram style (adapted for self-contained single-file compilation).
- **[docx-js](https://docx.js.org)** for Word (DOCX) generation.
- **[Astro](https://astro.build)** and **[Starlight](https://starlight.astro.build)** for the documentation site.
- **[matplotlib](https://matplotlib.org)** for the rendered example charts.

## Standards and methodology

- **[PRISMA](https://www.prisma-statement.org)** for systematic-review reporting.
- **[CSL / citeproc](https://citationstyles.org)** for citation formatting.

---

*If your project should be here and is not, please open an issue. Credit is cheap and gratitude is free, unlike journal APCs.*
