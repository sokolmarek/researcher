# /revise

Start revision workflow from reviewer comments.

## Parameters
- **round** (optional, default: R1): Revision round (R1, R2, R3)

## Form Fields
- **comments_source** (select: paste/file/word-doc): How to provide reviewer comments

## Behavior
1. Parses reviewer comments into structured format
2. Creates revision roadmap (categorized, prioritized)
3. Routes to  for tracked changes
4. Routes to  for response document
5. Saves all artifacts to manuscript/revisions/R{n}/
