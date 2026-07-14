---
description: Run peer review on the current manuscript and save the report to manuscript/reviews/

---

# /researcher:review-paper

Run peer review on current manuscript.

## Inputs (gathered conversationally)
- Mode: full, quick, methodology, or re-review (default: full). State it in your message or Claude asks.
- External reviews: whether to include external model reviews, which require API keys (default: false). State it in your message or Claude asks.

## Behavior
Routes to the peer-review skill. Reads all manuscript sections, runs review, saves report to manuscript/reviews/.
