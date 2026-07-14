---
description: Create a new manuscript project, routing the gathered inputs to the manuscript-setup skill
---

# /researcher:new-manuscript

Create a new manuscript project.

## Inputs (gathered conversationally)
- Title: paper title. Required, state it in your message.
- Authors: comma-separated author names. Required, state them in your message.
- Journal: target journal name. Optional.
- Format: latex, word, or both (default: latex). State it or Claude asks.
- Citation style: apa7, ieee, chicago, vancouver, or mla (default: apa7). State it or Claude asks.
- Paper type: imrad, review, case-study, conference, or theoretical (default: imrad). State it or Claude asks.

## Behavior
Routes to the manuscript-setup skill with the gathered inputs as parameters.
