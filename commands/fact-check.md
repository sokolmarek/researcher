---
description: Verify a claim, section, or manuscript against scientific literature and report confidence levels
argument-hint: "<claim>"
---

# /researcher:fact-check

Verify claims against scientific literature.

## Inputs (gathered conversationally)
- Claim: a specific claim to verify. If omitted, Claude scans the current manuscript section or full manuscript.
- Scope: claim, section, or manuscript (default: claim). State it in your message or Claude asks.

## Behavior
1. Routes to fact-checking skill
2. If claim provided: searches for supporting/contradicting evidence
3. If section/manuscript scope: scans text for factual claims, checks each
4. Uses Scite MCP for smart citation context when available
5. Returns fact-check report with confidence levels per claim
6. Flags unsupported, contested, or contradicted statements
