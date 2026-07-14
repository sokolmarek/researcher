---
description: Find and filter relevant academic conferences for paper submission by topic, deadline, ranking, and location
argument-hint: "[topic or field]"
---

# /researcher:find-conference

Find relevant academic conferences for paper submission.

## Inputs (gathered conversationally)
- Topic: paper topic or research area. State it in your message or Claude asks.
- Filters (optional): constraints like "deadline after June 2026", "CORE A*", "in Europe", "IEEE only"

## Behavior
1. Routes to conference-finder skill
2. Searches for conferences matching the topic
3. Applies deadline, ranking, location, and publisher filters
4. Returns list of conferences with: name, dates, location, deadline, ranking, acceptance rate, publisher
5. Highlights upcoming deadlines
