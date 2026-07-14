---
description: Recommend ranked journals matching a paper's topic, applying optional filters like quartile or open access
argument-hint: "[filters]"
---

# /researcher:find-journal

Find the best journal for your paper.

## Inputs (gathered conversationally)
- Topic: paper topic, title, or paste your abstract. Required; Claude asks if it is missing.
- Filters: constraints like "Q1 only", "open access", "impact > 3", "indexed in Scopus" (optional). State it in your message or Claude asks.

## Behavior
1. Routes to journal-finder skill
2. Analyzes the topic/abstract to determine field and scope
3. Searches for matching journals with ranking and reasoning
4. Applies user filters if provided
5. Returns ranked list of 5-10 journals with details (IF, quartile, APC, turnaround, scope match)
