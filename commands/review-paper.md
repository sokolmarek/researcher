# /review-paper

Run peer review on current manuscript.

## Form Fields
- **mode** (select: full/quick/methodology/re-review, default: full): Review depth
- **external** (toggle, default: false): Include external model reviews (requires API keys)

## Behavior
Routes to  skill. Reads all manuscript sections, runs review, saves report to manuscript/reviews/.
