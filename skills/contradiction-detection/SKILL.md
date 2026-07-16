---
name: contradiction-detection
description: "Mine contrasting evidence for a claim (or a manuscript's claim list) and build a contradiction matrix. Triggers when user says: 'find contradicting evidence', 'is this contested', 'who disagrees with this', 'contrasting studies', 'conflicting findings', 'does the literature disagree', 'find opposing studies', 'evidence against this claim', 'contradiction matrix', 'contested claim', 'inconsistency in the evidence'. For each claim it fans out over Scite contrast tallies and targeted core searches, anchors each contradicting quote against M2 passages (full-text) or the abstract otherwise, always stating the layer, and outputs a matrix of claim x contradicting source, quote, layer, and strength. Within a systematic review this feeds GRADE's inconsistency domain. Use this skill to SURVEY disagreement across many sources; to verify ONE claim up or down against the literature use fact-checking, and to classify how an existing citation is framed use citation-context."
---

# Contradiction Detection

Mine the literature for evidence that CONTRADICTS a claim, then organize it into a contradiction
matrix. The unit of output is disagreement made concrete: for each claim, the specific sources that
push back, the quote that does the pushing, the layer that quote was checked at, and how strong the
disagreement is. This skill surfaces candidates for a human to confirm; it does not adjudicate who
is right.

## What this skill is, and is not

- It **mines contrasting evidence** across many sources and assembles a matrix. It is a survey of
  disagreement, not a verdict on the claim.
- **fact-checking** verifies ONE claim up or down (supported / partially supported / contested /
  unsupported / contradicted). Reach for it when the question is "is this true?".
- **citation-context** classifies how an EXISTING citation is framed (supporting / contrasting /
  mentioning). Reach for it when the question is "am I citing this paper accurately?".
- This skill answers "who disagrees with this, and how concretely?".

**An empty matrix is not evidence of consistency.** Axis (c) is a lexical baseline whose
`contradicted` recall is 0.538 (below), so it misses roughly half of genuine contradictions, and a
downed source is dirty evidence, not a clean "no contradiction". Report a null result as "no
contradicting evidence surfaced by these searches", never as "the claim is uncontested".

## Refusal-grade rules, inlined (integrity)

Integrity constraints: see `references/integrity-constraints.md`; the rules below are binding and
also govern this skill. Consume the four-state verdicts, never a boolean (D9). Read `refusal_grade`
from the core JSON; do not re-derive the rule.

- A contradicting source is only listed as a real contradiction when its **identity** resolves
  (`verified`, or `inconclusive` flagged "one index only"). A source that is `unresolvable` or
  `mismatch` on axis (a) is FLAGGED as unresolved and NEVER entered in the matrix as an established
  paper: it may be fabricated or mis-resolved, and entering it would manufacture a contradiction
  from nothing.
- A `retracted` contradicting source (axis b) still carries the retraction notice inline; it does
  not silently strengthen the disagreement, and `expression-of-concern` / `corrected` are human
  checkpoints surfaced beside the cell.
- `inconclusive` (identity) and `insufficient-passage` (faithfulness) are **open items, never
  refusal-grade and never dropped as fabricated**. Treating `inconclusive` as fabrication accuses
  an honest author of inventing a real citation, the worst failure this system can make.
- A `source_error` is dirty evidence, not a clean negative. Absence of a contradiction because a
  source timed out is `inconclusive`, never "no contradiction found".

Note that `contradicted` (axis c) is refusal-grade in fact-checking because there it flags the
author's own cited support. Here, a `contradicted` verdict against the claim is the FINDING this
skill is looking for, so it populates the matrix rather than halting work; the refusal-grade
handling above applies to the contradicting SOURCES' own identity and status.

## Inputs

- A single claim string, or a claim list (extracted from a manuscript's `.tex`/`.md`, or supplied
  by the user). For a manuscript, parse assertions the same way fact-checking does: empirical,
  statistical, and causal claims first.
- Optional: the claim's primary supporting source(s) (DOI/arXiv/OpenAlex id), which seed the
  citation-graph and Scite streams below.
- Optional PICO/PECO framing (population, intervention/exposure, outcome, direction). Inside a
  systematic review these are the locked eligibility axes, so contradiction scope stays consistent
  with screening.

## Workflow

### Mode A: contradiction scan for one claim

1. **Decompose the claim** into assertion plus qualifier axes (population, intervention/exposure,
   outcome, and the claimed DIRECTION of effect). The direction is what a contradiction inverts.
2. **Mine contrasting candidates** from three independent streams (use all that are available; name
   which ran):
   - **Scite contrast tallies** (MCP, when connected): for the claim's primary source(s), pull the
     papers that cite in a CONTRASTING context, plus their excerpts. This is the highest-signal
     stream when present.
   - **Targeted core searches**: search the opposing framing, not the claim's own words. Query the
     outcome and population with negation and reversal terms ("no association", "no significant
     difference", "failed to replicate", "null result", the opposite direction), so retrieval is
     not biased toward confirmations. See Deterministic backend.
   - **Citation graph**: `citations <primary-source-doi>` enumerates works that cite the claim's
     source; screen them for a contrasting stance (Scite tally, or the faithfulness anchor in
     step 4).
3. **Resolve each candidate** (axes a, b) with `verify-ref` and `status`. Drop nothing as
   fabricated: list `verified` and `inconclusive` (flagged "one index only"); FLAG
   `unresolvable`/`mismatch` as unresolved and keep them OUT of the matrix; annotate any
   `retracted` / `expression-of-concern` inline.
4. **Anchor the contradiction** against each surviving source (axis c). This is what turns "cites
   in a contrasting context" into a concrete, layered disagreement:
   - Run `passages index <doi-or-url>` then `faithfulness "<claim>" --doc <id>`. A `contradicted`
     verdict means the source's own passages disagree with the claim at the **full-text** layer;
     capture the anchoring passage as the quote.
   - If no OA full text is retrievable, there is nothing to anchor at full text: mark the pair
     **insufficient-passage at the full-text layer** (no full-text contradiction is implied), and
     fall back to an **abstract**-layer judgment over the abstract from `get`/`search`, which is
     weaker and not passage-backed.
   - A `partial` verdict is a qualified disagreement (the source contradicts the claim only under
     conditions); record it as such, not as a full contradiction.
5. **Assign layer and strength** (below) per surviving source and place the cell in the matrix.
6. **Separate the open items**: `inconclusive` sources, `insufficient-passage` anchors, and any
   `source_error` go in their own list with what would resolve them (a re-run when the index is
   reachable, OA full text). They are unverified, never accusations, and never counted as "no
   contradiction".

### Mode B: contradiction matrix for a claim list or manuscript

1. Extract the claim list (parse the manuscript, or take the user's list). Prioritize empirical,
   statistical, and causal claims.
2. Run Mode A per claim, reusing retrievals across claims where the same source recurs.
3. Assemble the full matrix (claims down, contradicting sources across; one row per claim with its
   contradicting sources, quotes, layers, and strengths).
4. Inside the systematic-review workflow, hand the matrix to GRADE's inconsistency domain (see
   "Feeding GRADE" below).

## The contradiction matrix

One row per (claim, contradicting source) pair. Columns:

| Column | Contents |
|---|---|
| Claim | the claim id and text (or manuscript span) |
| Contradicting source | author (year), DOI; identity verdict (a) and status (b) inline |
| Quote | the exact passage that disagrees, with its anchor (passage id + offsets at full-text; abstract span otherwise) |
| Layer | `full-text` / `abstract` / `insufficient-passage` (see taxonomy) |
| Verdict (c) | `contradicted` or `partial` from `faithfulness` (the axis-c anchor) |
| Strength | `strong` / `moderate` / `weak` (see scale), a human-confirmable judgment |

### Layer taxonomy (state it on every cell)

- **full-text**: the contradicting quote is anchored to an indexed OA passage (`passages index` +
  `faithfulness`). A `contradicted` here is a full-text-anchored disagreement.
- **abstract**: only the abstract was retrievable; the quote and judgment come from the abstract.
  This is weaker and not passage-backed, and the cell is ALSO flagged `insufficient-passage` at the
  full-text layer, so the matrix never implies a full-text-verified contradiction from an abstract.
- **insufficient-passage**: no OA text was retrievable to anchor on at all. The pair is surfaced,
  never dropped, and no contradiction (full-text or abstract) is asserted from it.

### Strength scale (human-confirmable, never an automated score)

Strength is a judgment the human confirms, aided by the signals below. It is NOT a number the tool
computes, because the lexical axis-c baseline is too weak to be trusted as a scorer (below).

- **strong**: two or more independent sources with full-text-anchored `contradicted` verdicts on
  the same outcome and matching qualifiers, all `verified` on identity and `current` on status.
- **moderate**: a single full-text-anchored `contradicted`, or multiple abstract-layer
  disagreements, or a Scite contrast tally that is large relative to supporting citations.
- **weak**: an abstract-only disagreement, a `partial` (qualified) verdict, a single
  `inconclusive`-identity source, or a contradiction that hinges on a qualifier mismatch
  (different population/outcome) rather than a genuine reversal.

A `retracted` contradicting source does not raise strength; its notice is shown and the human
decides whether to keep it in the assessment.

## Deterministic backend

Candidate mining, source identity and status, and quote anchoring route through the
`researcher-core` evidence kernel, so the matrix rests on actual retrievals and is reproducible.
Skills never import the kernel; they shell out and read `--json`. Full command and field reference:
`references/core-cli.md`.

Standard invocation (two fallbacks documented in the reference, for a Codex install or a checkout
without `uv`):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core <cmd> ... --json
```

**1. Mine contrasting candidates** (`search`, `citations`):

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<opposing-framing terms>" --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core citations <primary-source-doi> --limit 50 --json
```

Read from `search`: `records[]` (CSL-JSON), `counts{}`, `sources[]`, and `warnings[]` (a source in
`warnings[]` is a coverage gap, never proof no contradiction exists). Read from `citations`:
`nodes[]` (the citing works) and `warnings[]`. Default `search` sources are `openalex,crossref,arxiv`;
add `semantic_scholar,pubmed` via `--sources` for clinical or ML coverage.

**2. Resolve identity and status of every candidate** (axes a, b), never a boolean:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core verify-ref "<doi-or-title>" --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core status <doi-or-id> --json
```

Read per entry: `verdict` (`verified`/`mismatch`/`unresolvable`/`inconclusive`), `refusal_grade`,
`reason`, `source_outcomes[]` (each `confirmed`/`negative`/`source_error`), `best_match`, and the
`status` block (`current`/`corrected`/`retracted`/`expression-of-concern`). A `status.checked:
false` is an absence of evidence, not a clean bill of health.

**3. Anchor the contradiction** (axis c), naming the layer:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core passages index <doi-or-url> --json
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core faithfulness "<the claim>" --doc <doc-id> --json
```

Run `faithfulness` with THE CLAIM as the argument and the candidate source as `--doc`: a
`contradicted` verdict means that source disagrees with the claim. Read each `claims[]` entry's
`verdict` (`supported`/`partial`/`contradicted`/`insufficient-passage`), its passage anchors (id,
offsets, page coords), and `summary{coverage, abstention_rate}`. When `passages index` finds no OA
full text (exit 1, `found:false`, or accessibility `unavailable`/`abstract-only`), the pair is
`insufficient-passage` at the full-text layer; fall back to an abstract-layer judgment over the
abstract in the `get`/`search` record and mark it so.

**Degradation path (the plugin never hard-fails without core, D3).** If `uv` or `core/` is absent,
say so in the output and fall back in order: (1) **MCP servers** where connected, above all the
**Scite MCP** for contrast tallies and excerpts (its native strength) and **Zotero** for the user's
library, then (2) **web search**. Name the tier that produced each cell. A matrix built without core
is labeled as such, its quotes are not passage-backed, and its layers cannot be `full-text`.

## Axis (c) is a lexical baseline: honest limits and the gate

This skill ships because its gating benchmark, axis (c) faithfulness, is GREEN at D17 size (104
claim-passage pairs, >= 20 per class, risk-coverage curve reported). The measured numbers, from
`evals/BENCHMARKS.md`, are what make the caveats above concrete, not rhetorical:

- **`contradicted` recall 0.538**, 95% Wilson [0.355, 0.712] (14 of 26 true contradictions found).
  The lexical baseline (BM25 plus token-overlap and polarity heuristics) MISSES roughly half of
  genuine contradictions, and it flipped 6 of 26 true contradictions to `supported` outright. This
  is why an empty matrix is not consistency and why every surfaced contradiction needs human
  confirmation.
- **`contradicted` precision 0.538**, 95% Wilson [0.355, 0.712]: of what it labels `contradicted`,
  under half are truly contradictions, so the matrix over-flags too. Confirm each cell before it
  informs a conclusion.
- **Coverage 0.750**: on documents with no OA full text it abstains perfectly (26/26
  `insufficient-passage`), which is the D11 invariant this skill relies on to never manufacture a
  full-text contradiction from thin air.

Report `contradicted` recall (0.538) beside any contradiction summary. The weakness is in-spec: M2
ships the lexical floor, and this measured rate is exactly the start trigger for the deferred
semantic layer that will tighten it. Treat this skill as a recall aid that concentrates human
attention on likely disagreements, not as an automated arbiter of contradiction.

## Scite integration

When the Scite MCP connector is connected it is the primary contrast-mining stream: its Smart
Citation tallies give literature-wide supporting / contrasting / mentioning COUNTS for a source, and
its citation statements give the actual contrasting excerpts. A claim whose primary source carries
many contrasting citations and few supporting ones is a strong contradiction candidate before any
anchoring runs. Always check Scite `editorialNotices` for retractions or corrections on a
contradicting paper, and corroborate with core `status`. Scite tallies COMPLEMENT the core anchor;
they do not replace it, and a Scite-only cell is layered `abstract` (or `insufficient-passage`) and
labeled as tally-derived, never `full-text`.

## Feeding GRADE (systematic-review workflow)

Inside `skills/systematic-review/`, the matrix is the concrete input to GRADE's **inconsistency**
domain (`references/grade-worksheet.md`): instead of rating down for inconsistency on a vibe, the
human cites the specific contradicting studies, quotes, and layers this skill surfaced. The skill
organizes and records; the human makes the GRADE judgment. The completed GRADE worksheet (not this
skill) is what gets hashed into an `artifact_hash` event so the review report can prove which
appraisal fed the certainty rating (M4.9). The matrix also flags where a contradiction is only
`abstract`-layer or `insufficient-passage`, so the human does not rate down inconsistency on
evidence that was never checked at full text.

## Output format

### Single-claim contradiction report

```markdown
## Contradictions for: "[claim text]"

**Streams run:** [Scite contrast tally | core search | citation graph]  (name the ones that ran)
**Contradicting sources surfaced:** [n]  **Confirmed identity (a):** [n]  **Open (inconclusive):** [n]  **Flagged unresolved (out of matrix):** [n]
**Strongest layer reached:** [full-text | abstract | insufficient-passage]

### Contradiction matrix

| Source (a / b) | Quote (anchor) | Layer | Verdict (c) | Strength |
|---|---|---|---|---|
| [Author (Year)], DOI [x] (verified / current) | "[passage]" (passage-id, offsets) | full-text | contradicted | moderate |
| [Author (Year)], DOI [y] (verified / retracted) | "[abstract span]" | abstract | partial | weak |

### Open items (unverified, NOT contradictions)
- [Author (Year)], DOI [z]: identity `inconclusive` (one index only) OR anchor `insufficient-passage` (no OA full text). What would resolve it: [re-run when index reachable | OA full text].
- [source_error on <source> during search]: dirty evidence, not "no contradiction". Re-run.

### Flagged unresolved (kept OUT of the matrix)
- "[candidate]": identity `unresolvable` / `mismatch`. Not entered as an established contradicting paper.

### Evidence provenance
core [search | citations | faithfulness]; sources: [openalex, crossref, ...]; queries: ["<opposing query>", ...]; snapshots: [<response_hash>, ...]; retrieved_at: [<timestamp>]; mode: [live | replay | record]. Scite tally (where connected): supporting [n] / contrasting [n] / mentioning [n].

### Assessment
[2-3 sentences. State the strength honestly, name the layer each contradiction was checked at, and note that axis (c) contradicted recall is 0.538: an absence of surfaced contradictions is not proof of consistency. Recommend human confirmation of every cell.]
```

### Manuscript / claim-list matrix

```markdown
# Contradiction Matrix: [manuscript or topic]

**Claims scanned:** [N]  **Claims with surfaced contradictions:** [n]  **Claims with only open items:** [n]  **Claims with none surfaced:** [n]

Per-claim rows follow the single-claim matrix above; each cell carries its layer and an Evidence provenance line.

## Claims with contradictions requiring attention
### Claim 1 (Line ~[N]): "[claim text]"
[matrix rows + strongest layer + recommendation]

## Claims with only open items
[inconclusive sources / insufficient-passage anchors: unverified, not consistency]

## Note on completeness
The lexical axis-c baseline (contradicted recall 0.538) under-detects contradictions. "None surfaced" means these searches found none, not that the claim is uncontested.
```

## Integration points

- **fact-checking**: verifies a single claim up or down; this skill surveys who disagrees. A
  contradiction surfaced here can hand a claim to fact-checking for a full verdict.
- **citation-context**: classifies how a citation is framed; a `contrasting` framing there is a
  candidate contradiction to anchor here.
- **research-convergence**: reconciles many sources into one thesis; the matrix is the disagreement
  half of that reconciliation.
- **systematic-review** and **peer-review**: the matrix feeds GRADE inconsistency and gives
  reviewers concrete counter-evidence to weigh.
- **literature-search**: supplies the retrieval substrate for candidate mining.

## Integrity constraints

1. Never fabricate citations: every contradicting source must come from an actual retrieval (core,
   Scite MCP, Zotero, or web search). Never invent a DOI, author list, venue, or year for a source
   you claim disagrees with the claim.
2. Never invent data or quotes: every matrix quote is an actual passage or abstract span from a
   retrieved source, with its anchor. Anything illustrative is labeled "(synthetic, for
   demonstration)".
3. Refuse to enter as an established contradiction: a candidate whose identity is `unresolvable` or
   `mismatch` (axis a), or a source known `retracted` used without its notice.
4. Consume the four-state verdicts, never a boolean. Refusal-grade handling (flag as unresolved,
   keep out of the matrix, attach the retraction notice) fires on `unresolvable`/`mismatch`
   (identity) and `retracted` (status) for the contradicting SOURCE. `inconclusive` and
   `insufficient-passage` are NEVER refusal-grade: surface them as open items. Read `refusal_grade`
   from the core JSON rather than re-deriving the rule. An empty matrix is never reported as proof
   the claim is uncontested.

Canonical copy: `references/integrity-constraints.md`.
