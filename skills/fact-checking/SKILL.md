---
name: fact-checking
description: "Verify scientific claims against published literature. Triggers when user says: 'fact check', 'verify claim', 'is this true', 'check this statement', 'verify citations', 'evidence for', 'is this supported', 'check my claims', 'validate findings', 'source check'. Searches literature to find evidence supporting or contradicting claims, classifies evidence strength, and produces structured fact-check reports. Use this skill whenever the user needs to verify the accuracy of a scientific statement or check claims in a manuscript."
---

# Fact-Checking

Verify scientific claims and statements against published literature with evidence classification.

## CRITICAL INTEGRITY RULE

**NEVER mark a claim as "Supported" without actual retrieved evidence.** If no evidence is found, classify as "Unsupported" — not "Supported" with fabricated sources. Absence of evidence is reported honestly.

## Workflow

### Single Claim Verification

1. **Parse the claim** — extract the core factual assertion, entities, and relationships
2. **Identify searchable components** — key terms, concepts, named entities
3. **Search for evidence** — query multiple sources with varied search strategies
4. **Evaluate retrieved evidence** — assess relevance, quality, and stance toward the claim
5. **Classify the claim** — assign evidence category and confidence level
6. **Report findings** — structured output with sources and reasoning

### Manuscript Section Scan

1. **Extract claims** — identify all factual assertions in the provided text
2. **Categorize claims** — empirical facts, statistical claims, causal claims, definitional claims
3. **Prioritize** — check empirical and causal claims first (highest risk of error)
4. **Verify each** — run single claim workflow for each extracted claim
5. **Produce report** — consolidated fact-check report for the section

## Evidence Sources

Search in priority order:

1. **Scite MCP** (if available) — smart citation context with supporting/contrasting/mentioning classifications. Preferred source because it provides citation statement context.
2. **Semantic Scholar** — broad coverage, citation counts, abstracts
3. **PubMed** — biomedical claims
4. **CrossRef** — DOI resolution and metadata verification
5. **arXiv** — preprints for recent claims
6. **Google Scholar** (via web search) — broadest fallback

Use at least 2 sources per claim for triangulation. If Scite is available, always include it.

## Evidence Classification

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

### Evidence

**For (supporting):**
1. [Author et al. (Year)] — "[relevant excerpt or finding]"
   Source: [journal], DOI: [doi]
   Citation context: [supporting/mentioning]

2. ...

**Against (contradicting):**
1. [Author et al. (Year)] — "[relevant excerpt or finding]"
   Source: [journal], DOI: [doi]
   Citation context: [contrasting]

### Assessment
[2-3 sentences explaining the classification and any important nuances]

### Recommendation
[Action for the author: keep as-is, add qualifier, revise, add citation, remove claim]
```

### Manuscript Section Report

```markdown
# Fact-Check Report: [Section Name]

**Claims checked:** [N]
**Supported:** [n] | **Partially supported:** [n] | **Contested:** [n] | **Unsupported:** [n] | **Contradicted:** [n]

## Claims Requiring Attention

### Claim 1 (Line ~[N]): "[claim text]"
Classification: [status]
[Brief evidence summary and recommendation]

### Claim 2 ...

## Claims Verified
[List of claims that passed verification, with sources]
```

## Common Checks

### Misattributed Statistics
Verify that cited statistics actually appear in the cited source. Common issue: "60% of X according to [Source]" where Source says something different.

### Outdated Claims
Flag claims based on evidence that has been superseded by newer studies, particularly in fast-moving fields.

### Retracted Sources
Check every cited paper against retraction databases. A manuscript citing retracted work needs immediate attention.

### Citation Context Mismatch
Detect when a paper is cited to support a claim but the paper actually says something different or more nuanced. Scite's citation statements are especially useful here.

## Integration

- Uses **literature-search** skill for finding evidence
- Uses Scite MCP connector for smart citation context
- Feeds into **post-draft-integrity** hook (automated claim checking)
- Results inform **revision-management** skill (fixing unsupported claims)
- Works with **citation-management** to verify bibliography entries
