---
name: peer-review
description: "Multi-perspective academic peer review of a manuscript, with scoring rubrics. Triggers when user says: 'review this paper', 'peer review', 'critique manuscript', 'assess quality', 'evaluate paper', 'quick assessment', 'check methodology', 'is this paper ready', 'what reviewer comments would this manuscript receive', 'score this manuscript against a rubric'. Runs 5 expert reviewer personas within Claude; integration of ChatGPT/Gemini/Ollama as additional reviewers is planned but not yet implemented. Use this skill whenever the user wants a reviewer verdict on a manuscript, as opposed to a verdict on source code, which is code-analysis."
---

# Peer Review

Simulated multi-perspective peer review system with quantitative scoring.

## Review Personas (Claude-internal)

### Editor-in-Chief (EIC)
- Journal fit assessment: scope alignment, audience match, editorial priorities
- Novelty assessment: incremental vs significant vs transformative contribution
- Editorial decision recommendation with justification
- Suggested reviewers (which personas to emphasize based on paper type)
- Identifies whether the paper belongs in this journal or should be redirected

### R1: Methodology Reviewer
- Research design appropriateness and justification
- Statistical methods: validity, power analysis, effect sizes, multiple comparison corrections
- Reproducibility assessment: are methods described in sufficient detail to replicate?
- Data quality and handling: missing data treatment, outlier handling, preprocessing
- Threats to validity: internal, external, construct, and statistical conclusion validity
- Identifies methodological assumptions that are unstated or unjustified

### R2: Domain Expert
- Literature coverage completeness: are seminal and recent key works cited?
- Theoretical framework strength and coherence
- Positioning within field: how does this advance the state of the art?
- Missed references: specific papers the authors should cite and engage with
- Identifies claims that contradict established findings without acknowledgment

### R3: Cross-disciplinary Reviewer
- Broader implications: what does this mean beyond the immediate subfield?
- Practical impact: can practitioners or other researchers use these findings?
- Accessibility to non-specialists: is the paper readable outside its niche?
- Real-world applicability: do the assumptions hold in practice, not just in theory?
- Identifies opportunities for interdisciplinary connections the authors may have missed

### Writing Reviewer
- Clarity and readability
- Logical structure and flow
- Argumentation quality
- Grammar and style
- Figure/table quality and necessity

### Devil's Advocate
- Challenges core thesis
- Identifies logical fallacies
- Strongest counter-arguments
- Alternative explanations for results
- Unfalsifiability concerns

## Scoring Rubric (0-100)

| Dimension | Weight |
|-----------|--------|
| Novelty & Significance | 20% |
| Methodology | 25% |
| Results & Analysis | 20% |
| Writing Quality | 15% |
| Literature & Context | 10% |
| Reproducibility | 10% |

### Decision Mapping
- **≥80:** Accept (or Accept with minor edits)
- **65-79:** Minor Revision
- **50-64:** Major Revision
- **<50:** Reject

### Score Behavioral Indicators
- **90-100:** Exceptional. Publication-ready with minimal changes. Top 5% of submissions.
- **80-89:** Strong. Clear contribution, solid methodology, well-written.
- **65-79:** Adequate. Contribution present but needs refinement. Addressable issues.
- **50-64:** Significant concerns. Fundamental issues with methodology, framing, or analysis.
- **<50:** Critical flaws. Unsupported claims, invalid methodology, or insufficient contribution.

## External model review (planned, not implemented)

No dispatch implementation ships today: this section specifies the intended integration, and reviews today are Claude's multi-persona panel only.

When implemented, the skill would dispatch review prompts to external models for independent perspectives:

### ChatGPT Integration
- Requires: `OPENAI_API_KEY` environment variable
- Send paper text + structured review prompt → parse response into review format
- Model: `gpt-4o` (or user-configured)

### Gemini Integration
- Requires: `GOOGLE_AI_API_KEY` environment variable
- Send paper text + review prompt → parse response
- Model: `gemini-2.5-pro` (or user-configured)

### Ollama Integration
- Requires: `OLLAMA_ENDPOINT` environment variable (default: `http://localhost:11434`)
- Send paper text + review prompt to local model
- Model: user-configured (e.g., `llama3`, `mixtral`)

### Review Synthesis
When external reviews are available:
1. Present each model's review separately with source label
2. Identify consensus points (all reviewers agree)
3. Identify divergent points (reviewers disagree)
4. Weight Claude's review highest (most context-aware)
5. Generate unified recommendation with confidence level

## Review Modes

### Full Review
Default. All 5 personas (external models are planned, not yet available). Comprehensive report.

### Quick Assessment
Triggered by: "quick review", "quick assessment"
EIC + Writing Reviewer only. 1-page summary with top 5 strengths and weaknesses.

### Methodology Focus
Triggered by: "check methodology", "methods review"
Methodology Reviewer + Devil's Advocate. Deep dive on research design.

### Re-Review
Triggered by: "re-review", "verify revisions"
Compares revised manuscript against original review comments. Checks each issue was addressed.

## Output Format

```markdown
# Peer Review Report

## Summary
[EIC's 2-3 sentence overall assessment]

## Scores
| Dimension | Score | Assessment |
|-----------|-------|------------|
| Novelty | XX/100 | ... |
| ... | ... | ... |
| **Overall** | **XX/100** | **Decision** |

## Detailed Reviews

### Reviewer 1: Methodology
**Strengths:**
1. ...
**Weaknesses:**
1. ...
**Specific Recommendations:**
1. ...

[... repeat for each reviewer ...]

## Revision Roadmap
Priority-ordered list of changes needed.
```

## Simulated Rebuttal Mode

Triggered by: "simulate rebuttal", "defend the paper", "how would authors respond"

After a full review is complete, this mode simulates the paper's authors defending their work against each criticism:

1. **For each reviewer comment**, generate a plausible author response:
   - Accept and address: the criticism is valid, here is how we would fix it
   - Partially accept: the reviewer has a point, but the concern is overstated (explain why)
   - Respectfully disagree: the criticism is based on a misunderstanding or different assumptions (present the evidence)
2. **Rank criticisms by defensibility**: identify which reviewer comments are hardest to rebut (these are the strongest criticisms)
3. **Identify fatal weaknesses**: criticisms where no reasonable defense exists. These MUST be addressed before submission
4. **Output format**: table with columns: Reviewer, Comment Summary, Simulated Response, Defensibility Score (1-5), Priority

This mode helps authors:
- Anticipate reviewer objections before submission
- Identify which weaknesses to fix proactively vs which can be defended in rebuttal
- Practice formulating diplomatic but firm responses

## Pre-submission Stress Test

Triggered by: "stress test", "pre-submission check", "predict reviewer attacks", "what will reviewers criticize"

A focused mode specifically designed to predict what real reviewers will attack. Unlike a full review, this mode thinks adversarially:

1. **Identify the 5 most likely attack vectors**: the specific claims, methods, or framings that will draw fire
2. **For each attack vector**:
   - State the likely reviewer objection in their voice
   - Rate severity: cosmetic / substantive / potentially fatal
   - Suggest a preemptive fix the authors can implement NOW (before submission)
   - Estimate how common this objection is (based on typical review patterns in the field)
3. **Journal-specific predictions**: if a target journal is set in `manuscript/config.yaml`, tailor predictions to that journal's known reviewer pool tendencies and editorial standards
4. **Output a "Vulnerability Map"**: prioritized list of weak points with recommended preemptive actions

The stress test is designed to be run BEFORE the full review: fix the obvious vulnerabilities first, then run a proper multi-persona review on the strengthened manuscript.

## Review History

Track reviews across rounds in `manuscript/reviews/`:
- `review-R1.md`: first round review
- `review-R2.md`: re-review after revision
- Compare scores across rounds to show improvement

## Integrity constraints

1. Never fabricate citations: every reference must come from an actual retrieval (API, MCP, or user-provided source). If a citation cannot be verified, flag it; never invent a DOI, author list, venue, or year.
2. Never invent data: only user-provided or actually computed numbers may appear as results. Anything illustrative must be labeled "(synthetic, for demonstration)".
3. Refuse to present as valid output: a likely-fabricated or unresolvable citation, a data claim with no traceable source, or a retracted source (unless the user explicitly cites it as retracted).

Canonical copy: `references/integrity-constraints.md`.
