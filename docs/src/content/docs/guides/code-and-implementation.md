---
title: "Guide: Code & Implementation"
description: Two skills that write reproducible experiment code and reverse-engineer a methods section from an existing codebase.
sidebar:
  label: Code & Implementation
  order: 6
---

Two skills sit at the boundary between the paper and the code that produced it. One writes the experiments; the other reads them back into prose. Both carry `context: fork` and `agent: code-agent` in their frontmatter, so they execute inside the [Code Agent](/researcher/reference/agents/) subagent, which is pinned to Sonnet in its own frontmatter. That keeps the larger model's budget for the reasoning-heavy work of writing and reviewing. Code generation is a place where a faster, cheaper model does the job well, so there is no reason to spend Opus tokens on boilerplate.

## implementation

Turns an experiment plan into runnable, reproducible code: data pipelines, model and training scripts, and evaluation harnesses. Reproducibility is not an afterthought here, it is enforced. Seeds are pinned, dependency versions are recorded, config is separated from code, and the evaluation split is fixed before a single metric is computed.

In the running scenario, that means a PTB-XL loader that respects the official train/validation/test folds (folds 1 to 8, 9, and 10), a contrastive pretraining loop, a linear-evaluation probe, and a fine-tuning script, all reading from one config file so a reviewer can reproduce the label-efficiency curve rather than take your word for it. The skill will scaffold the harness but it will not manufacture numbers: the evaluation code is written to report whatever the model actually produces, and the results section only ever describes real runs.

**Trigger it:** "Write the training script for the contrastive pretraining", "Build a reproducible data pipeline for PTB-XL", "Set up the evaluation harness for the fine-tuning experiment".

## code-analysis

The inverse direction. Point it at an existing codebase and it produces a methods-section draft: a prose description of what the code does, pseudocode for the core algorithm, and a complexity analysis (time and space) of the parts that matter. It is the skill for the moment three weeks before a deadline when the experiments run but the methods section is still an empty file.

Given the ECG pretraining repository, it would read the augmentation and contrastive-loss modules, write out the InfoNCE-style objective as pseudocode, note the cost of the pairwise similarity computation over a batch, and hand you a draft you then verify line by line against your own intent. It describes the code as written, so if the code and your mental model disagree, the draft surfaces that rather than papering over it.

**Trigger it:** "Analyze this codebase and draft a methods section", "Generate pseudocode and complexity analysis for the training loop", "Turn my repo into a methods description".

## Why Sonnet, and what stays on Opus

The routing is mechanical, not prose. Each skill's SKILL.md frontmatter declares `context: fork` and `agent: code-agent`, and the Code Agent's own frontmatter sets `model: sonnet`, per the [agents reference](/researcher/reference/agents/). Frontmatter is the only thing that switches models; instructions written in a skill's body cannot. Writing a data loader or transcribing a loss function into pseudocode is well-scoped, verifiable work where Sonnet is fast and accurate. The judgment calls (deciding what the methods section should emphasize, checking that the generated code matches the experiment you actually intend to run) are yours, and the writing and review skills that lean on them stay on the larger model. The split is a budget decision, not a quality compromise.

The fork has one honest tradeoff. A forked skill receives your task and the repository, not the whole conversation, so anything the subagent needs (file paths, the config file it should read, seeds or constraints you settled on earlier in the chat) must be named explicitly in the request. It will not see the discussion that produced them.

## See it in action

The [manuscript-setup output](https://github.com/sokolmarek/researcher/tree/main/examples/writing-review/manuscript-setup.md) shows the `methods.tex` placeholder that code-analysis fills, and the [Research & Discovery guide](/researcher/guides/research-and-discovery/) covers the literature side that frames what the code is being compared against.
