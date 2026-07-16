---
name: fact-checking
description: "Verify scientific claims against published literature. Triggers when user says: 'fact check', 'verify claim', 'is this true', 'check this statement', 'verify citations', 'evidence for', 'is this supported', 'check my claims', 'validate findings', 'source check'. Searches literature to find evidence supporting or contradicting a specific claim, classifies evidence strength, and produces structured fact-check reports. Use this skill whenever the user needs to verify the accuracy of a scientific statement or check claims in a manuscript; reconciling many sources into one thesis is research-convergence."
---

# Fact-Checking

Verify scientific claims and statements against published literature with evidence classification.

## CRITICAL INTEGRITY RULE

**NEVER mark a claim as "Supported" without actual retrieved evidence.** If no evidence is found, classify as "Unsupported", not "Supported" with fabricated sources. Absence of evidence is reported honestly.

## Workflow

### Single Claim Verification

1. **Parse the claim**: extract the core factual assertion, entities, and relationships
2. **Identify searchable components**: key terms, concepts, named entities
3. **Search for evidence**: run the core fan-out (`search` / `get`), then verify each source's identity and status (`verify-ref`). See Deterministic backend below.
4. **Anchor and evaluate**: anchor the claim against each source's passages (`faithfulness`, axis c), then assess relevance, quality, and stance toward the claim. See Deterministic backend below.
5. **Classify the claim**: assign evidence category and confidence level
6. **Report findings**: structured output with sources and reasoning

### Manuscript Section Scan

1. **Extract claims**: identify all factual assertions in the provided text
2. **Categorize claims**: empirical facts, statistical claims, causal claims, definitional claims
3. **Prioritize**: check empirical and causal claims first (highest risk of error)
4. **Verify each**: run single claim workflow for each extracted claim
5. **Produce report**: consolidated fact-check report for the section

## Deterministic backend

Evidence retrieval, source identity, and claim anchoring run through the `researcher-core` CLI, so a fact-check is reproducible and its verdicts rest on actual retrievals rather than recall. Skills never import the kernel; they shell out and read `--json`. Full command and field reference: `references/core-cli.md`.

Standard invocation (two fallbacks documented in the reference, for a Codex install or a checkout without `uv`):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core <cmd> ... --json
```

**1. Retrieve evidence** (`search`, `get`). For each claim, pull candidate sources:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<claim key terms>" --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core get <doi-or-arxiv-id> --json
```

Consume `records[]` (CSL-JSON: title, author, issued, DOI, container-title), `counts{}`, and `sources[]`. A failing source lands in `warnings[]` and never fails the search: a downed index is not evidence for or against a claim. Default sources are `openalex,crossref,arxiv`; add `semantic_scholar,pubmed,datacite` via `--sources`.

**2. Verify the identity and status of any source you cite as evidence** (axes a, b, d), never a boolean:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-ref "<doi-or-title>" --json
```

Consume per entry: `verdict` (`verified` / `mismatch` / `unresolvable` / `inconclusive`), `refusal_grade` (read it, do not re-derive the rule), the `status` block (`current` / `corrected` / `retracted` / `expression-of-concern`), and `accessibility` (`full-text` / `abstract-only` / `unavailable`). A `status.checked: false` is an absence of evidence, not a clean bill of health.

**3. Anchor the claim against the source's passages** (axis c):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages index <doi-or-url> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages search "<claim>" --doc <id> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core faithfulness "<claim>" --doc <id> --json
```

Consume from `faithfulness`: each `claims[]` entry's verdict (`supported` / `partial` / `contradicted` / `insufficient-passage`), its passage anchors (IDs, offsets, page coordinates), and `summary{coverage, abstention_rate}`. These four verdicts are the per-source claim-anchor vocabulary this skill records; they feed, but are not the same as, the synthesis-level classification below.

**Degradation path (the plugin never hard-fails without core, D3).** If `uv` or `core/` is unavailable, say so in the output and fall back in order: (1) MCP servers where connected (Scite for citation context, Zotero for the user's library), then (2) web search. Name the tier that produced each result. A fact-check produced without core is labeled as such, and its claim anchors are not passage-backed.

### Verdicts you consume, and which are refusal-grade

Consume the four-state identity verdict, never a boolean (D9). A finding is **refusal-grade**, meaning this skill flags it as an integrity problem and will not endorse the claim as supported, ONLY when one of these holds:

- identity is `unresolvable` or `mismatch` (axis a): the cited source cannot be resolved, or resolves to a different paper;
- publication status is `retracted` (axis b): the evidence has been withdrawn;
- claim faithfulness against the cited source is `contradicted` (axis c): the source says the opposite of the claim.

NEVER refusal-grade, surfaced instead as **open items** (never accusations, never dropped as fabricated):

- identity `inconclusive`: a source was rate-limited, or only one index holds the paper. A real citation is routinely `inconclusive`; treating it as fabrication accuses an honest author, which is the worst failure this system can make.
- faithfulness `insufficient-passage`: no OA full text, so there was nothing to anchor on. The claim is NOT clean and NOT faithful; it is unverified at the passage layer. Surface it every time, never drop it.

An `expression-of-concern` or `corrected` status is not refusal-grade, but it is a human checkpoint: surface it beside the verdict rather than absorbing it silently.

### The verified layer, stated on every verdict

Every claim verdict names the layer it was checked at:

- **full-text**: anchored against extracted OA passages (`passages` + `faithfulness`).
- **abstract**: only the abstract was retrievable; anchoring is over the abstract and is weaker.
- when full text is unavailable, the faithfulness verdict is `insufficient-passage`, never `supported` or "faithful". The layer is reported next to the verdict, always.

Axis (c) is a LEXICAL baseline: BM25 retrieval plus token-overlap and polarity heuristics, measured coverage 0.750 (`evals/BENCHMARKS.md`). It cannot read. An overstatement that reuses the passage's own tokens scores as `supported` (measured: 12 of 26 `partial` claims were called `supported`). So a `supported` anchor is a FLOOR, not a proof: report it as "consistent with the cited passage at the lexical level", never as "the source proves the claim". This weakness is in-spec; the deferred semantic layer is what tightens it.

## Evidence Sources

Primary path: the core fan-out (`search`, `get`) queries OpenAlex, Crossref, and arXiv by default (add Semantic Scholar, PubMed, and DataCite via `--sources`), deduplicates, and ranks, so the skill does not hand-roll per-API calls. Verification (`verify-ref`) adds Crossref, OpenAlex, and DataCite for axes (a), (b), (d), and `citations` / `references` add OpenCitations for citation-context checks.

Enrichment when connected (MCP tier): **Scite** for smart citation context (supporting / contrasting / mentioning), **Zotero** for the user's library. Final fallback when core is unavailable: **web search**, labeled as such.

Triangulate: prefer at least two independent confirming sources per claim (the two-confirmation bar core uses for a `verified` identity). If Scite is connected, include its citation context.

## Evidence Classification

These five classes are the SYNTHESIS-level verdict for a claim across all of its sources. Each rests on the per-source axis (c) anchors (`supported` / `partial` / `contradicted` / `insufficient-passage`) together with source identity (a) and status (b). Two rules bind the synthesis: a `contradicted` anchor against a source cited to support the claim is refusal-grade, and a claim whose only anchors are `insufficient-passage`, or whose sources are all `inconclusive`, is not "Supported": it is unverified at the passage layer and is listed as an open item.

### Supported
Multiple independent sources confirm the claim. High confidence.
- At least 2 independent papers provide consistent evidence
- Evidence is from peer-reviewed sources
- No contradicting evidence found

### Partially Supported
Some evidence agrees, but with important qualifications.
- Evidence supports the claim only under specific conditions
- Some sources agree, others are ambiguous
- The claim overgeneralizes from narrower findings

### Contested
Active disagreement in the literature.
- Some papers support, others contradict
- Ongoing scientific debate exists
- Effect has failed to replicate in some studies

### Unsupported
No evidence found for or against the claim.
- Search returned no relevant results
- The claim appears to be novel or unverified
- May indicate the claim is speculative (flag for the user)

### Contradicted
Evidence directly opposes the claim.
- Multiple sources provide counter-evidence
- The claim has been debunked or retracted
- A cited source actually says the opposite of what is claimed

## Evidence Quality Assessment

For each piece of evidence, assess:

| Factor | Weight | Notes |
|--------|--------|-------|
| Study design | High | RCTs and meta-analyses rank highest |
| Sample size | Medium | Larger samples provide stronger evidence |
| Recency | Medium | Recent studies may supersede older findings |
| Citation count | Low | Popular ≠ correct, but indicates engagement |
| Journal quality | Low | Proxy for peer review rigor |
| Replication status | High | Replicated findings are strongest |

## Scite Integration

When the Scite MCP connector is available, use its smart citation classifications:

- **Supporting citations:** papers that cite the source in a supporting context
- **Contrasting citations:** papers that cite the source in a contrasting or disagreeing context
- **Mentioning citations:** papers that cite without taking a clear stance

A claim backed by a paper with many supporting citations and few contrasting ones is stronger than one with mixed citation context.

Always check `editorialNotices` for retractions or corrections before using any paper as evidence.

## Output Format

### Single Claim Report

```markdown
## Fact-Check: "[original claim]"

**Classification:** [Supported | Partially Supported | Contested | Unsupported | Contradicted]
**Confidence:** [High | Medium | Low]
**Source identity (a):** [verified | mismatch | unresolvable | inconclusive]   **Status (b):** [current | corrected | retracted | expression-of-concern]

### Evidence

**For (supporting):**
1. [Author et al. (Year)]: "[relevant excerpt or finding]"
   Source: [journal], DOI: [doi]
   Claim anchor (c): [supported | partial | insufficient-passage] at layer [full-text | abstract]; passage [passage-id]
   Citation context: [supporting/mentioning]   Identity (a): [verified | inconclusive]

2. ...

**Against (contradicting):**
1. [Author et al. (Year)]: "[relevant excerpt or finding]"
   Source: [journal], DOI: [doi]
   Claim anchor (c): [contradicted] at layer [full-text]; passage [passage-id]
   Citation context: [contrasting]

### Evidence provenance
core [search | get | faithfulness]; sources: [openalex, crossref, ...]; queries: ["<query>", ...]; snapshots: [<response_hash>, ...]; retrieved_at: [<timestamp>]; mode: [live | replay | record]

### Assessment
[2-3 sentences explaining the classification and any important nuances. Name the layer each verdict was checked at, and note that a `supported` anchor is a lexical floor, not proof.]

### Recommendation
[Action for the author: keep as-is, add qualifier, revise, add citation, remove claim, or resolve an open item (inconclusive source, insufficient-passage)]
```

### Manuscript Section Report

```markdown
# Fact-Check Report: [Section Name]

**Claims checked:** [N]
**Supported:** [n] | **Partially supported:** [n] | **Contested:** [n] | **Unsupported:** [n] | **Contradicted:** [n]
**Refusal-grade (unresolvable / mismatch / retracted / contradicted):** [n] | **Open items (inconclusive / insufficient-passage):** [n]

Each claim entry below carries its axis verdicts (a, b, c), the layer verified, and an Evidence provenance line, exactly as in the single-claim report.

## Claims Requiring Attention

### Claim 1 (Line ~[N]): "[claim text]"
Classification: [status]
[Brief evidence summary and recommendation]

### Claim 2 ...

## Open Items
[Claims whose sources are `inconclusive`, or whose anchors are `insufficient-passage`: unverified, NOT accusations. List each with what would resolve it, e.g. a re-run when the index is reachable, or OA full text.]

## Claims Verified
[List of claims that passed verification, with sources and the layer each was checked at]
```

## Common Checks

### Misattributed Statistics
Verify that cited statistics actually appear in the cited source. Common issue: "60% of X according to [Source]" where Source says something different.

### Outdated Claims
Flag claims based on evidence that has been superseded by newer studies, particularly in fast-moving fields.

### Retracted Sources
Check every cited paper against retraction databases (core `status` / `verify-ref`, axis b). A manuscript citing retracted work needs immediate attention; `retracted` is refusal-grade, `expression-of-concern` and `corrected` are human checkpoints.

### Citation Context Mismatch
Detect when a paper is cited to support a claim but the paper actually says something different or more nuanced. Anchor the claim against the source's passages (core `faithfulness`, axis c): a `contradicted` anchor is refusal-grade, `partial` is a qualifier problem, and `insufficient-passage` means no full text was available to check. Scite's citation statements enrich this when connected.

## Integration

- Uses **literature-search** skill for finding evidence
- Uses Scite MCP connector for smart citation context
- Feeds into **post-draft-integrity** hook (automated claim checking)
- Results inform **revision-management** skill (fixing unsupported claims)
- Works with **citation-management** to verify bibliography entries

## Integrity constraints

1. Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it, never invent a DOI, author list, venue, or year.
2. Never invent data: only user-provided or actually computed numbers appear as results. Anything illustrative is labeled "(synthetic, for demonstration)".
3. Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).
4. Refusal-grade findings are exactly `unresolvable` / `mismatch` (identity, axis a), `retracted` (status, axis b), and `contradicted` (faithfulness, axis c). `inconclusive` (identity) and `insufficient-passage` (faithfulness) are NEVER refusal-grade: surface them as open items, never as accusations, and never as clean. Read `refusal_grade` from the core JSON rather than re-deriving this rule.

Canonical copy: `references/integrity-constraints.md`.
