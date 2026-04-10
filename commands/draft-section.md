# /draft-section

Draft a specific manuscript section.

## Parameters
- **section** (required): One of: abstract, introduction, methods, results, discussion, conclusion

## Behavior
1. Loads manuscript/config.yaml for context
2. Reads existing sections for coherence
3. Loads style-profile.yaml if available
4. Routes to  skill in section mode
5. Writes output to appropriate .tex or .md file
