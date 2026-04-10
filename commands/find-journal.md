# /find-journal

Find the best journal for your paper.

## Form Fields
- **topic** (text, required): Paper topic, title, or paste your abstract
- **filters** (text, optional): Constraints like "Q1 only", "open access", "impact > 3", "indexed in Scopus"

## Behavior
1. Routes to journal-finder skill
2. Analyzes the topic/abstract to determine field and scope
3. Searches for matching journals with ranking and reasoning
4. Applies user filters if provided
5. Returns ranked list of 5-10 journals with details (IF, quartile, APC, turnaround, scope match)
