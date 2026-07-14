---
name: brainstorming
description: "Socratic research design refinement through guided questioning. Triggers when user says: 'brainstorm', 'research idea', 'refine my question', 'help me think through', 'explore this topic', 'what should I study', 'narrow my focus', 'devil's advocate', 'challenge my idea'. Guides users from vague research ideas to refined questions, hypotheses, and methodology through structured Socratic dialogue. Use this skill whenever the user needs help developing or sharpening a research concept."
---

# Brainstorming

Socratic research design refinement: from vague idea to actionable research question.

## Core Philosophy

Never hand the user a finished research question. Instead, **guide them to discover it** through structured questioning. The best research questions emerge from dialogue, not dictation.

## Socratic Questioning Phases

Work through these phases sequentially, adapting depth to the chosen mode.

### Phase 1: Clarification
Establish what the user actually means. Remove ambiguity.
- "What exactly do you mean by [term]?"
- "Can you give a concrete example of what you're describing?"
- "When you say [X], are you referring to [A] or [B]?"
- "What is the scope: a specific population, domain, time period?"

### Phase 2: Assumptions
Surface hidden assumptions that constrain or bias the inquiry.
- "What are you assuming about [variable/relationship]?"
- "Is that always true, or only under certain conditions?"
- "What would it mean if that assumption were wrong?"
- "Are you assuming causation where there might only be correlation?"

### Phase 3: Evidence
Ground the idea in existing knowledge and testability.
- "What evidence supports this intuition?"
- "How could we test this empirically?"
- "What data would convince you this is wrong?"
- "Has anyone studied something similar before?"

### Phase 4: Perspectives
Broaden the view by introducing other disciplinary lenses.
- "What would a [psychologist/economist/statistician] say about this?"
- "How does field X approach this same problem?"
- "What would a critic of this approach argue?"
- "Who benefits and who is harmed by this framing?"

### Phase 5: Implications
Explore downstream consequences of the research direction.
- "If this hypothesis is confirmed, what follows?"
- "What are the practical consequences of knowing the answer?"
- "How would this change current practice or theory?"
- "What new questions does this open up?"

### Phase 6: Meta-Questions
Reflect on the inquiry itself to ensure it is worth pursuing.
- "Why is this question important right now?"
- "What would change if we knew the answer?"
- "Is this the most impactful question you could ask in this space?"
- "Can this realistically be answered with available methods and data?"

## Modes

### Quick Brainstorm (5 minutes)
- Run Phases 1 and 3 only
- Produce a refined research question and 2-3 candidate hypotheses
- Best for: users who have a semi-formed idea and need sharpening

### Deep Dialogue (full Socratic)
- Run all 6 phases sequentially with follow-up questions
- Produce: refined question, hypotheses, proposed methodology sketch, identified gaps
- Best for: early-stage exploration of a new research direction

### Devil's Advocate
- Skip Phase 1, assume the idea is clear
- Focus on Phases 2, 4, and 5 in adversarial mode
- Challenge every claim, assumption, and framing choice
- Best for: stress-testing a research design before committing resources

## Output Format

After the dialogue, produce a structured summary:

```markdown
# Research Brainstorm Summary

## Refined Research Question
[Single, clear, testable research question]

## Hypotheses
- H1: [Primary hypothesis]
- H2: [Alternative hypothesis]
- H0: [Null hypothesis]

## Key Concepts & Definitions
- [Term 1]: [Operational definition agreed during dialogue]
- [Term 2]: [Operational definition]

## Assumptions (acknowledged)
1. [Assumption surfaced during Phase 2]
2. ...

## Proposed Methodology (sketch)
- Study type: [suggested approach]
- Key variables: [IV, DV, controls]
- Data source: [where/how]

## Open Questions
- [Unresolved issues from the dialogue]

## Mind Map
[If requested, generate via tikz-diagrams skill]
```

## Mind Map Generation

When requested, invoke the `tikz-diagrams` skill to produce a TikZ mind map:
- Central node: core research topic
- Level 1 branches: major themes from the Socratic phases
- Level 2 branches: sub-questions, variables, related concepts
- Color-code by phase (clarification = blue, assumptions = orange, evidence = green, perspectives = purple, implications = red, meta = gray)

## Session Logging

Save every brainstorming session to `manuscript/brainstorm-log.md` (append mode):
- Timestamp and mode used
- Full question-answer dialogue (condensed)
- Final structured output
- This log becomes a paper trail for research design decisions

## Integration

- Feeds into **experiment-design** skill (refined question + hypotheses as input)
- Feeds into **literature-search** skill (key concepts as search terms)
- Can invoke **tikz-diagrams** skill for mind map visualization
- Session log is referenced by **paper-drafting** when writing the introduction
