# Phase 5: Deferred Semantic Layer (Verified RAG + LiteLLM)

Version target: 1.0.0
Status: NOT SCHEDULED. This file exists so scope pressure has somewhere to point. Nothing here starts until its trigger fires and the maintainer opts in.

## Why deferred

The hybrid decision (D1) keeps the plugin as the product, and the interoperability surface (PyPI packaging of `researcher-core` plus the thin stable-core FastMCP server) is now scheduled work in Phase 4, once the core stabilizes. What remains deferred here is the heavy semantic layer only: a full retrieval-augmented-generation stack (GROBID, embeddings, a vector store, RCS retrieval, reranking) and LiteLLM multi-provider routing. These add real operational weight (services, embedding-model choices, vector-store lifecycle, a provider matrix) that is not justified until demand shows up. Recording the design now costs little and prevents Phase 2-4 decisions from accidentally blocking it. In particular, the Phase 2 OA full-text extraction (`core/researcher_core/fulltext.py`, see D-B) is deliberately the substrate this phase builds on: the semantic stack is added on top of that extraction, not a parallel reimplementation.

## 5A. Verified RAG over full text

**Start trigger:** users repeatedly need question answering over full paper text (beyond abstracts and metadata), for example claim-faithfulness anchoring keeps degrading to abstract-level (the `unverified_no_fulltext` per-claim state from D-B) often enough that abstract-level anchoring is no longer sufficient, so a semantic index over full text is warranted.

**Explicit dependency:** this capability is built ON TOP of the Phase 2 minimal OA full-text extraction. `core/researcher_core/fulltext.py` already resolves the OA PDF/HTML via the OA cascade and returns `{section, text, char_offsets}`. The RAG stack consumes that output as its ingestion entry point and adds higher-fidelity structure plus semantic indexing on top. It does not re-resolve or re-extract sources independently.

Sketch:
- `core/researcher_core/rag/ingest.py`: consumes `fulltext.py` output; adds GROBID structure extraction (Dockerized) for higher-fidelity section and reference parsing where the heuristic split is too coarse, with the Phase 2 heuristic split as the always-available fallback; semantic chunking by section.
- `core/researcher_core/rag/index.py`: embeddings (configurable: local bge or nomic via sentence-transformers, or API), LanceDB vector store under the platformdirs data dir.
- `core/researcher_core/rag/answer.py`: metadata-aware retrieval, rerank, contextual summarize (the PaperQA2 RCS pattern), span-anchored answers (quote plus `char_offsets` section locator carried through from `fulltext.py`), abstain when evidence is thin.
- CLI: `ingest <pdf-or-doi>`, `ask "<question>" [--corpus name]`.
- New optional dependency group `[rag]` in `core/pyproject.toml` (embeddings, vector store, GROBID client); the base install stays three dependencies (`httpx`, `rapidfuzz`, `platformdirs`) and the `[fulltext]` extra stays as shipped in Phase 2.
- Optional MCP tool: if the Phase 4 thin stable-core FastMCP server is running, add a single `rag_query` tool ON TOP of it (reusing that server's transport and auth). This is the only MCP work in Phase 5; the base server, its stable tool set, and PyPI publishing already shipped in Phase 4.
- Eval: LitQA2-style subset before announcing numbers; the research targets PaperQA2's published precision as the bar.

Deferred because: GROBID service operations, embedding-model choices, and vector-store lifecycle are heavy, and abstention-based quality needs eval infrastructure that only exists after Phase 4.

## 5B. LiteLLM multi-provider routing

**Start trigger:** a maintained workflow genuinely needs non-Claude models (cost-controlled batch verification, local-only privacy mode), not hypothetically.

Sketch: `core/researcher_core/llm.py` LiteLLM wrapper used only by core-side judgment steps (faithfulness LLM-judge, RAG rerank); provider config via env; Ollama or vLLM for local. Skills continue to run on Claude; this touches only core-internal LLM calls, so it pairs naturally with the 5A RCS rerank and faithfulness scoring.

Deferred because: today the only core-side LLM need (faithfulness judging) runs fine inside the plugin session; adding a provider matrix multiplies the test surface.

## Exit criteria for calling it 1.0.0

Whichever subset ships, 1.0.0 requires: SemVer commitment, CHANGELOG discipline held since 0.2.x, published eval numbers for any RAG claim (5A), and a README quickstart for each newly shipped semantic surface (RAG CLI, and LiteLLM provider config if it ships). The plugin, CLI, PyPI, and MCP-server surfaces are already documented as of Phase 4, so 1.0.0 only adds the RAG and provider quickstarts on top.
