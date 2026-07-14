---
description: Run peer review on the current manuscript and save the report to manuscript/reviews/
---

# /researcher:review-paper

Run peer review on current manuscript.

## Inputs (gathered conversationally)
- Mode: full, quick, methodology, or re-review (default: full). State it in your message or Claude asks.

Review runs Claude's multi-persona reviewer panel only. External model reviewers (OpenAI, Google, Ollama) are planned, not implemented, so there is nothing to turn on and no API keys are needed.

## Behavior
Routes to the peer-review skill. Reads all manuscript sections, runs review, saves report to manuscript/reviews/.
