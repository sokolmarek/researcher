# /fact-check

Verify claims against scientific literature.

## Parameters
- **scope** (select: claim/section/manuscript, default: claim): What to check

## Form Fields
- **claim** (text, optional): A specific claim to verify. If omitted, scans the current manuscript section or full manuscript.
- **scope** (select: claim/section/manuscript, default: claim): Scope of fact-checking

## Behavior
1. Routes to fact-checking skill
2. If claim provided: searches for supporting/contradicting evidence
3. If section/manuscript scope: scans text for factual claims, checks each
4. Uses Scite MCP for smart citation context when available
5. Returns fact-check report with confidence levels per claim
6. Flags unsupported, contested, or contradicted statements
