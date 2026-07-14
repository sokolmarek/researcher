---
description: Draft a manuscript section using config, existing sections, and style profile for context
argument-hint: "<section>"
---

# /researcher:draft-section

Draft a specific manuscript section.

## Inputs (gathered conversationally)
- Section: one of abstract, introduction, methods, results, discussion, or conclusion. State it in your message or Claude asks.

## Behavior
1. Loads manuscript/config.yaml for context
2. Reads existing sections for coherence
3. Loads style-profile.yaml if available
4. Routes to the paper-drafting skill in section mode
5. Writes output to appropriate .tex or .md file
