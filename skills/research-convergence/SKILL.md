---
name: research-convergence
description: "Deep research that converges on arguments and thesis construction. Triggers: converge on argument, build thesis, research argument, socratic mode, deep research, flash search, argument map, refine thesis, research direction, challenge my argument."
---

# Research Convergence

Not just finding papers — converging on arguments. Deep research that builds toward a thesis through structured argumentation.

## CRITICAL INTEGRITY RULE
**NEVER fabricate claims or evidence chains.** Every claim in the argument map must trace back to a real citation from an actual search. If evidence is thin, say so. Gaps are findings too.

## Modes

### Socratic Mode
Triggered by: "socratic mode", "help me refine my argument", "challenge my thesis", "play devil's advocate on my research"

Interactive back-and-forth dialogue to sharpen the user's research direction.

**Workflow:**
1. Ask the user to state their current research question or thesis
2. Probe assumptions: "What evidence supports this claim?", "What would falsify this?"
3. Identify hidden premises and unstated dependencies
4. Challenge weak links: "How do you account for [counter-evidence]?"
5. Suggest alternative framings or stronger formulations
6. Iterate until the argument structure is tight

**Output:**
- Refined thesis statement
- Argument structure (premise chain leading to conclusion)
- Identified assumptions that need empirical support
- Suggested next steps (searches, experiments, readings)

### Full Research Mode
Triggered by: "full research", "deep dive", "comprehensive argument", "build the case for", "research convergence"

Comprehensive multi-round investigation that builds an argument map from the literature.

**Workflow:**
1. **Round 1 — Broad scan:** Search across all available connectors for the core research question. Identify major themes, key authors, seminal papers (15-30 papers).
2. **Round 2 — Targeted deepening:** For each major theme, conduct focused follow-up searches. Chase citations forward and backward on the most relevant papers (20-40 additional papers).
3. **Round 3 — Counter-evidence hunt:** Explicitly search for papers that contradict or complicate the emerging thesis. Search for failed replications, negative results, critical commentaries (10-20 papers).
4. **Round 4 — Synthesis:** Organize all findings into an argument map. Identify the strongest line of argumentation. Note where evidence is strong vs weak.

**Output:** `argument-map.md` (see Output Format below)

### Flash Mode
Triggered by: "flash search", "quick scan", "flash mode", "5 minute scan", "quick overview"

Rapid preliminary scan for when the user needs a fast orientation.

**Workflow:**
1. Construct a single well-formed query from the research question
2. Search top 2-3 available connectors
3. Return 5-10 most relevant papers with one-sentence relevance annotations
4. Sketch a preliminary argument in 3-5 bullet points
5. Identify obvious gaps and suggest where to dig deeper

**Output:**
- Ranked paper list with relevance notes
- Preliminary argument sketch (3-5 claims with tentative evidence)
- Suggested next queries for deeper investigation

## Argument Map Structure

The core output of Full Research Mode is `argument-map.md`:

```markdown
# Argument Map: [Research Question]

## Thesis
[One-sentence refined thesis statement]

## Core Claims

### Claim 1: [Statement]
**Evidence for:**
- [Citation key]: [One-sentence summary of supporting evidence]
- [Citation key]: [One-sentence summary of supporting evidence]

**Evidence against:**
- [Citation key]: [One-sentence summary of counter-evidence]

**Strength:** Strong / Moderate / Weak
**Notes:** [Any caveats, conditions, or qualifications]

### Claim 2: [Statement]
...

## Synthesis
[2-3 paragraph narrative connecting the claims into a coherent argument]

## Gaps and Limitations
- [Gap 1]: No empirical evidence found for [specific sub-claim]
- [Gap 2]: Conflicting results between [citation] and [citation]

## Annotated Bibliography
[Citations organized by argument thread, not alphabetically]

### Supporting [Claim 1]
- **smith2024**: Smith et al. (2024). "Title." Journal. — [2-sentence annotation]

### Challenging [Claim 1]
- **jones2023**: Jones et al. (2023). "Title." Journal. — [2-sentence annotation]
```

## Progressive Narrowing Strategy

Each search round builds on prior results:
- **Round 1 queries:** Broad terms from the research question
- **Round 2 queries:** Specific terms extracted from Round 1 abstracts, key author names, cited references
- **Round 3 queries:** Negation queries ("failure of X", "limitations of X", "critique of X"), replication studies, meta-analyses
- **Round 4:** No new searches — synthesis of accumulated evidence

Track all queries and result counts for reproducibility.

## Search Session State

Maintain session state across rounds:
- Queries executed and result counts per source
- Papers found, deduplicated, and retained
- Emerging themes and their paper clusters
- Current argument structure (evolves across rounds)

## Integration Points

- **literature-search:** All search operations delegate to literature-search skill for actual query execution
- **citation-management:** Papers selected for the argument map are added to `library.bib`
- **paper-drafting:** The argument map directly informs introduction and discussion section structure
- **peer-review:** The argument map helps reviewers check whether claims are adequately supported

## When to Recommend Each Mode

| Situation | Mode |
|-----------|------|
| User unsure of direction, exploring ideas | Socratic |
| User has a clear question, needs full evidence base | Full Research |
| User needs quick orientation on a new topic | Flash |
| User wants to stress-test an existing argument | Socratic |
| User preparing literature review section | Full Research |
| User deciding whether a topic is worth pursuing | Flash |
