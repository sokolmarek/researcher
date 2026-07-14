---
description: Find state-of-the-art results, methods, and metrics for a given task or benchmark
argument-hint: "<benchmark or topic>"
---

# /researcher:sota

Find state-of-the-art results for a task or benchmark.

## Inputs (gathered conversationally)
- Topic: task, benchmark, or dataset name (e.g., "ImageNet classification", "SQuAD 2.0", "CIFAR-10"). Required, state it in your message or Claude asks.

## Behavior
1. Routes to sota-finder skill
2. Searches Papers with Code, Semantic Scholar, arXiv for current best results
3. Returns SOTA table: method, paper, year, metrics, code availability
4. Shows performance timeline and dominant trends
5. Can generate LaTeX comparison table for Related Work section
