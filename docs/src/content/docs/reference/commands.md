---
title: Slash Commands
description: The 11 slash commands and what they route to.
sidebar:
  label: Commands
  order: 1
---

Slash commands are shortcuts into the most common workflows. Type them in Claude Code or Cowork.

Installed plugin commands are namespaced by the plugin name, so every command below is invoked as `/researcher:<command>`. This guarantees they never collide with commands from other plugins. Arguments are free text (an argument-hint appears in autocomplete), and Claude asks for anything missing conversationally.

| Command | What it does |
|---|---|
| `/researcher:new-manuscript` | Create a new manuscript project with the full folder structure. |
| `/researcher:draft-section <section>` | Draft a section (abstract, introduction, methods, results, discussion, conclusion). |
| `/researcher:review-paper` | Run the simulated multi-persona peer review. |
| `/researcher:submit-ready` | Pre-submission checklist: citations, formatting, word count, required sections. |
| `/researcher:revise <round>` | Handle a revision round (R1, R2, R3) with reviewer-comment parsing. |
| `/researcher:brainstorm` | Socratic research-design refinement. |
| `/researcher:find-journal` | Find best-fit journals for your paper. |
| `/researcher:find-conference` | Find relevant conferences with deadlines. |
| `/researcher:fact-check <claim>` | Verify a claim against the scientific literature. |
| `/researcher:sota <benchmark>` | Find state-of-the-art results for a benchmark. |
| `/researcher:design-experiment <question>` | Design an experiment for a research question. |

You never *have* to use a command. Plain language works too: "review my paper" fires the same skill as `/researcher:review-paper`. Commands just save keystrokes at 3 AM.
