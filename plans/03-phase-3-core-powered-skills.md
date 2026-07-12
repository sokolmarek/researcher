# Phase 3: Core-Powered and New Skills

Version target: 0.4.0
Effort: 4-5 focused sessions

## Prerequisites

Phase 3 starts ONLY after the Phase 2 evidence capabilities have passed their acceptance checks:

- Minimal OA full-text extraction (`core/researcher_core/fulltext.py`: OA cascade resolve, PDF via pymupdf / HTML via selectolax or stdlib parser, heuristic section split, returns `{section, text, char_offsets}`).
- Four-state verification (per-source outcome in {confirmed, negative, source_error}; reference-level verdict in {verified, mismatch, unresolvable, inconclusive}).
- Threshold calibration on the gold subset (completed before any refusal-grade decision is made).

If any of the three is not green, Phase 3 does not begin: the claim-faithfulness, contradiction, extraction, and verification skills below have no sound backend without them. Phase 2 also supplies the append-only event-model ledger (`provenance.jsonl` validated against `core/schemas/provenance-event.schema.json`) emitting `retrieval`, `record_lineage`, and `dedup_decision` events, plus the `core/` CLI.

## Goal

Point the research-side skills at the deterministic core, and add five new skills that the core makes possible. After this phase the plugin has 33 skills (28 + 5 new) and 14 commands (11 + 3 new), and every retrieval or verification claim a skill makes is backed by reproducible API calls and, where a claim is anchored to a source, by the Phase-2 four-state verdicts and OA full text rather than model recall.

## Conventions for every touched skill

- Add a **"Deterministic backend"** section: the exact core CLI invocation(s), what fields of the JSON output to use, and the degradation path (if `uv` or `core/` is unavailable: fall back to MCP servers from `.mcp.json`, then to web search, and say so in the output).
- **Consume the four-state verdict, not a boolean.** Skills read `verified / mismatch / unresolvable / inconclusive` from core verification. Refusal-grade behavior (flagging "likely fabricated", refusing to declare a bibliography or manuscript clean) fires ONLY on `unresolvable` or `mismatch` (plus `retracted` and `contradicted/unfaithful` where applicable), NEVER on `inconclusive`. `inconclusive` (a legitimate single-index paper, or any `source_error` on a lookup) is surfaced as an open item, not treated as fabrication.
- **Anchor faithfulness against the Phase-2 OA full text.** For claim-citation, contradiction, and extraction work, anchors resolve against `fulltext.py` output (section, text, char offsets) when OA full text is available. When it is unavailable for a source, anchors degrade to abstract level and the per-claim verdict is `unverified_no_fulltext`. A skill MUST NOT emit a clean/faithful verdict for a claim whose source full text was unavailable, and MUST state which layer it verified (abstract vs full-text).
- Keep SKILL.md under 500 lines (decision D6): replace hand-written API walkthroughs with core CLI calls and a link to `references/core-cli.md`.
- Preserve existing trigger phrases exactly; additions only.

## Tasks

### P3.1 Upgrade `skills/literature-search/SKILL.md`

Target: `skills/literature-search/SKILL.md`

Core fan-out replaces the hand-rolled per-API instructions. Systematic mode appends events to the append-only event-model ledger (`provenance append` writing `provenance.jsonl`) and reports PRISMA counts from `provenance prisma`, which derives counts by aggregating events (identified = retrieval hits; deduplicated = `dedup_decision` removals) rather than reading a single stored total. The Phase-2 `retrieval` / `record_lineage` / `dedup_decision` events are the ones this skill emits via core. Scite MCP (when connected) enriches the top results with supporting/contrasting tallies.
Acceptance: old trigger phrases still fire; systematic mode writes a valid `provenance.jsonl` whose records validate against `core/schemas/provenance-event.schema.json`, and `provenance prisma` derives non-zero identified/deduplicated counts.

### P3.2 Upgrade `skills/fact-checking/SKILL.md`

Target: `skills/fact-checking/SKILL.md`

Evidence retrieval via `search` and `get`, Scite Smart Citations for support/contrast classification when available. The skill consumes the four-state verification verdict from core, not a boolean. Verdict block gains an "evidence provenance" line (which sources, which queries, retrieved when) and states the verdict class. Refusal-grade handling: only `unresolvable` or `mismatch` justify a "likely fabricated" flag; `inconclusive` (single-index paper, or any `source_error`) is reported as inconclusive, never as fabricated.
Acceptance: a checked claim's report lists resolvable DOIs only; unverifiable claims get verdict Unsupported, never an invented source; an `inconclusive` verification is labeled inconclusive rather than fabricated.

### P3.3 Upgrade `skills/sota-finder/SKILL.md`

Target: `skills/sota-finder/SKILL.md`

Every number entering a SOTA table must come from a paper retrieved this session, and each paper is run through core verification before inclusion. Rows carry the four-state verdict (verified / mismatch / unresolvable / inconclusive) and peer-reviewed/preprint flags. A paper whose verification is `inconclusive` (for example a legitimate single-index paper) is included with an inconclusive flag, not dropped as fabricated; only `unresolvable`/`mismatch` rows are withheld or marked refusal-grade.
Acceptance: dry run on the examples topic (PTB-XL superclass benchmark) reproduces the shape of `examples/research-verification/sota-benchmark-table.md`, with a per-row four-state flag on each entry.

### P3.4 Upgrade `skills/citation-context/SKILL.md`

Target: `skills/citation-context/SKILL.md`

Add `citations`/`references` graph calls (who cites this paper and how) and Scite tallies. Classification stays with Claude; enumeration comes from the graph. Any paper the skill asserts as existing is subject to the same four-state verdict, so a citing entry that resolves as `unresolvable` is flagged rather than listed as fact.
Acceptance: for a fixture DOI, the skill lists real citing papers with correct counts.

### P3.5 Upgrade `skills/citation-management/SKILL.md`

Target: `skills/citation-management/SKILL.md`

Add a retraction sweep (`retractions library.bib`) to the validation workflow and run core verification (`verify-bib`) before any bibliography is declared clean. `verify-bib` returns the four-state verdict per entry; the bibliography is declared clean only when no entry is refusal-grade (`unresolvable`, `mismatch`, or retracted). `inconclusive` entries are surfaced for human review but do not by themselves block a clean declaration.
Acceptance: a bib containing a known-retracted DOI produces a prominent warning; a bib with an `unresolvable` entry is not declared clean; a bib whose only open items are `inconclusive` is flagged for review, not refused.

### P3.6 Upgrade `skills/research-gaps/SKILL.md`

Target: `skills/research-gaps/SKILL.md`

Gap claims get graph evidence: traverse citations around the seed set and check whether candidate gaps are actually unaddressed (Owl-style "has anyone done X"). A gap asserted on the basis of a paper that fails verification is downgraded until the underlying reference resolves.
Acceptance: each reported gap lists the searches and traversals that failed to find prior work, not just an assertion.

### P3.7 New skill: `skills/systematic-review/` + `commands/systematic-review.md`

Target: `skills/systematic-review/SKILL.md`, `commands/systematic-review.md`

End-to-end PRISMA workflow over the event-model ledger: protocol definition (question, inclusion/exclusion criteria), multi-source search via core, and a screening log in which each include/exclude decision is emitted as a `screening_decision` event (carrying a reason) appended to `provenance.jsonl`. This skill is the one that introduces `screening_decision` into the ledger; Phase 2 supplied `retrieval`/`record_lineage`/`dedup_decision`. PRISMA flow counts (identified, deduplicated, screened, excluded, included) are derived by `provenance prisma` aggregating the events, and the inclusion table is built from `included` decisions. Human screens; the skill organizes and records.
Acceptance: dry run on the examples topic produces a protocol, a screening log of `screening_decision` events (each with a reason) that validate against `core/schemas/provenance-event.schema.json`, and PRISMA counts derived from the ledger that reconcile identified/deduplicated/screened/excluded/included.

### P3.8 New skill: `skills/citation-audit/` + `commands/verify-citations.md`

Target: `skills/citation-audit/SKILL.md`, `commands/verify-citations.md`

The integrity workhorse. Two levels:
1. Existence gate: `verify-bib` four-state verdicts (verified / mismatch / unresolvable / inconclusive) for every entry plus a retraction sweep. Refusal-grade classes here are `unresolvable`, `mismatch`, and retracted only; `inconclusive` is reported but never triggers refusal.
2. Claim-faithfulness audit: for each claim-citation pair in a manuscript, anchor against the Phase-2 OA full text (`fulltext.py`: section, text, char offsets) with three-layer anchors (supporting quote, page or section locator, retrieved metadata match); flag claims whose cited source does not contain the anchor. When OA full text is unavailable for the cited source, the anchor degrades to abstract level and the per-claim verdict is `unverified_no_fulltext`. The skill MUST NOT emit a clean/faithful verdict for such a claim, and every claim verdict states which layer it verified (abstract vs full-text). High-warn refusal-grade classes (unresolvable citation, mismatch, retracted source, contradicted/unfaithful claim) cause the skill to refuse to mark the manuscript clean. `inconclusive` and `unverified_no_fulltext` are surfaced as open items: not clean, and not refusal-grade.
Acceptance: reproduces `examples/research-verification/citation-audit.md` behavior on the seeded-fake bib; a manuscript claim misattributed to a real paper is flagged; a claim whose source lacks OA full text is reported as `unverified_no_fulltext` and never as clean/faithful; an `inconclusive` existence result does not by itself trigger refusal.

### P3.9 New skill: `skills/contradiction-detection/`

Target: `skills/contradiction-detection/SKILL.md`

For a claim or a manuscript's claim list: mine contrasting evidence via Scite contrast tallies and targeted core searches; anchor each contradicting quote against the Phase-2 OA full text when available, and against the abstract otherwise, stating the layer explicitly. Produce a contradiction matrix (claim x contradicting source, with quotes, the verification layer used, and strength). When a contradicting source has no OA full text, the quote is abstract-level and the pair is marked `unverified_no_fulltext` for the full-text layer, so no full-text-faithful claim is implied.
Acceptance: for a claim with known contested literature, at least one genuine contrasting paper is surfaced with a real quote, and each matrix cell states whether the quote came from full text or abstract.

### P3.10 New skill: `skills/extraction-tables/`

Target: `skills/extraction-tables/SKILL.md`

Elicit-style structured extraction: user defines columns (population, method, dataset, metric, effect size, and so on); the skill extracts per-paper values, anchoring against the Phase-2 OA full text when available and falling back to the abstract otherwise, into a markdown/CSV table. Each populated cell carries a source anchor (which paper, which section/sentence, char offsets from the `fulltext.py` extraction) and its verification layer. Cells sourced only from an abstract or from a paper with no OA full text are labeled at that layer with verdict `unverified_no_fulltext`, never presented as full-text-verified; genuinely absent data is marked "not reported" and never fabricated.
Acceptance: 5-paper table on the examples topic with no empty-cell fabrication (unavailable data is marked "not reported"), each populated cell carrying a source anchor and its verification layer.

### P3.11 New skill: `skills/literature-monitoring/` + `commands/watch-topic.md`

Target: `skills/literature-monitoring/SKILL.md`, `commands/watch-topic.md`

Saved-search state in `manuscript/monitoring.yaml` (queries, sources, last-run timestamp, seen-ID list). On re-run: execute the saved searches via core, diff against seen IDs, report only new papers. No scheduler inside the plugin; the doc notes external cron or Claude Code recurring tasks as options.
Acceptance: second run after seeding reports only papers not in the seen list.

### P3.12 Registration and bookkeeping

- New skill directories and command files are auto-discovered under `skills/` and `commands/` (Phase 1 removed the explicit manifest arrays); the Phase 3 change to `.claude-plugin/plugin.json` is the version bump to 0.4.0. The plugin now has 33 skills and 14 commands.
- Extend `agents/research-agent.md` and `agents/discovery-agent.md` skill lists (systematic-review, citation-audit, contradiction-detection, extraction-tables, literature-monitoring as appropriate).
- Update CLAUDE.md: skill count 28 to 33, command count 11 to 14, new category entries (this value is bumped again to 34 in Phase 4).
- For each new skill, record 3 should-trigger and 3 shouldn't-trigger prompts (appendix table here) as Phase 4 eval seeds.

## Files created

- `skills/systematic-review/SKILL.md`, `skills/citation-audit/SKILL.md`, `skills/contradiction-detection/SKILL.md`, `skills/extraction-tables/SKILL.md`, `skills/literature-monitoring/SKILL.md`
- `commands/systematic-review.md`, `commands/verify-citations.md`, `commands/watch-topic.md`

## Files modified

- `skills/literature-search/SKILL.md`, `skills/fact-checking/SKILL.md`, `skills/sota-finder/SKILL.md`, `skills/citation-context/SKILL.md`, `skills/citation-management/SKILL.md`, `skills/research-gaps/SKILL.md`
- `.claude-plugin/plugin.json` (version 0.4.0)
- `agents/research-agent.md`, `agents/discovery-agent.md`
- `CLAUDE.md`

## Phase acceptance checklist

- [ ] Phase 2 evidence capabilities (full-text extraction + four-state verification + calibration) passed acceptance before this phase started
- [ ] All 6 upgraded skills still trigger on their pre-upgrade phrases (re-run the Phase 1 smoke prompts for them)
- [ ] Each upgraded skill has a Deterministic backend section with a working degradation path
- [ ] Every consuming skill reads the four-state verdict and treats `inconclusive` as non-refusal-grade (refusal fires only on `unresolvable`/`mismatch`/retracted/contradicted)
- [ ] Faithfulness skills (citation-audit, contradiction-detection, extraction-tables) anchor against OA full text and emit `unverified_no_fulltext` (never clean/faithful) when full text is unavailable, stating the layer verified
- [ ] Systematic-review dry run appends `screening_decision` events to `provenance.jsonl` and yields PRISMA counts derived by `provenance prisma`
- [ ] Citation-audit flags the seeded fake and refuses to mark the manuscript clean on refusal-grade classes
- [ ] 5 new skills trigger on their recorded should-trigger prompts and stay silent on shouldn't-trigger prompts
- [ ] Every SKILL.md under 500 lines
- [ ] plugin.json, agents, CLAUDE.md updated; version 0.4.0; 33 skills and 14 commands

## Risks and fallbacks

- Trigger-phrase collisions between new and existing skills (systematic-review vs literature-search; citation-audit vs citation-management vs fact-checking): write descriptions with disjoint trigger vocabularies, and lean on the shouldn't-trigger prompt sets to catch overlap early.
- Claim-faithfulness anchoring needs source text: without OA full text, anchors degrade to abstract-level and the per-claim verdict is `unverified_no_fulltext`; the skill states which layer it verified and never emits a clean/faithful verdict for that claim.
- Over-refusing on thin evidence: `inconclusive` (single-index paper or a `source_error`) must not be treated as fabrication; only `unresolvable`/`mismatch` are refusal-grade for existence.
- Skill bloat: if an upgraded SKILL.md approaches 500 lines, move detail to `references/` (D6).

## Appendix: new-skill trigger seeds (fill during execution)

| Skill | Should trigger (3) | Shouldn't trigger (3) |
|---|---|---|
| systematic-review | | |
| citation-audit | | |
| contradiction-detection | | |
| extraction-tables | | |
| literature-monitoring | | |
