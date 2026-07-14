---
title: Agents
description: Reference for the nine orchestration agents that route work across Researcher's skills.
sidebar:
  label: Agents
  order: 2
---

Agents are the orchestration layer. Where a skill does one job well, an agent strings several skills together and picks the right model for the work. You rarely call an agent by name: commands and workflows summon them for you. This page is the map of who does what.

## The nine agents

| Agent | Role | Key skills | Model |
| --- | --- | --- | --- |
| Research Agent | Literature search and synthesis | literature-search, citation-management | inherit |
| Writing Agent | Section drafting and coherence | paper-drafting, writing-style-analysis, figure-suggestions | inherit |
| Review Agent | Multi-perspective peer review | peer-review | inherit |
| Formatting Agent | LaTeX and Word formatting and compliance | journal-formatting, latex-tables, tikz-diagrams, word-output | sonnet |
| Code Agent | Code analysis and implementation | implementation, code-analysis | sonnet |
| Style Agent | Voice calibration | writing-style-analysis | inherit |
| Visualization Agent | Plots, diagrams, and NN architectures | visualization, tikz-diagrams, plotneuralnet, figure-suggestions, image-prompt-crafting | sonnet |
| Statistics Agent | Method selection and experiment design | statistical-analysis, experiment-design, visualization | inherit |
| Discovery Agent | Journal and conference finding, gaps, and SOTA | journal-finder, conference-finder, research-gaps, sota-finder | inherit |

## Model routing

The Code, Visualization, and Formatting agents run on Sonnet. Their work is mechanical and high-volume (generating figures, compiling LaTeX, producing tables), so Sonnet handles it faster and cheaper without a loss in quality. That keeps the larger model's budget for the Research and Writing agents, where synthesis, argument, and voice actually benefit from the extra reasoning. An `inherit` model simply means the agent uses whatever model the parent session is running, so your top-level choice flows down to the reasoning-heavy work.

Agent definitions carry two independent frontmatter mechanisms. A `model: sonnet` key pins the agent to Sonnet, as described above. A separate `skills:` key preloads the listed skills into that agent's context so they are available without a discovery step. These do not make skills route into an agent on their own: a skill only forks into an agent when the skill's own frontmatter declares `context: fork` together with `agent: <name>`. Today that happens for two skills: implementation and code-analysis, both of which fork into the Code Agent.

## Where to go next

- The skills each agent orchestrates are catalogued in [Skills](/researcher/reference/skills/).
- Commands that summon these agents live in [Commands](/researcher/reference/commands/).
- To see the Research and Writing agents work end to end, follow the [guides](/researcher/guides/research-and-discovery/).
