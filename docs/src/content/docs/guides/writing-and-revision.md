---
title: "Guide: Writing & Revision"
description: The six skills that turn a verified library into a drafted, reviewed, and revised manuscript.
sidebar:
  label: Writing & Revision
  order: 3
---

Once the literature is in and the experiments are done, the work becomes prose: drafting, then surviving review, then answering it. Six skills cover that arc, and every one of them keeps the same promise as the research skills before it: no fabricated citations, no invented data, and no em dashes.

## paper-drafting

Builds an outline, then drafts sections one at a time. Introductions follow a funnel (broad progress, then the specific gap, then explicit contributions), and every factual claim carries a `\cite` key that resolves to your verified `library.bib`. It maintains a claim-to-citation mapping so the post-draft integrity hook and the citation-context audit can check that each sentence is actually supported by its source, and it keeps terms consistent against `terminology.yaml`. Numbers that appear in prose (PTB-XL's 21,837 records from 18,885 patients, per Wagner et al., 2020) are the source-verified figures, not approximations.

**Trigger it:** "`/researcher:draft-section introduction`", "Draft the methods for my SSL-for-ECG paper".

## writing-style-analysis

Calibrates the drafting voice to yours. Point it at an `author-papers/` folder (or a Google Scholar profile) and it measures your sentence-length distribution, active-versus-passive ratio, hedging and boosting habits, and citation density, then writes a reusable `style-profile.yaml` that paper-drafting loads on every subsequent draft. The result reads like you wrote it after a good night's sleep, not like a language model wrote it after none.

**Trigger it:** "Analyze my writing style", "Match my voice from my past papers".

## peer-review

Runs a five-persona panel over your manuscript: Editor-in-Chief, Methodology, Domain Expert, Writing, and a Devil's Advocate, each producing dimension-specific critiques rather than one generic pass. Rubric scores (novelty, technical soundness, clarity, reproducibility, significance) aggregate to a weighted overall that maps deterministically to a decision. Reviewer opinions are labeled synthetic, but any paper a reviewer says you "should compare to" is a real, resolvable reference, so the critique is checkable.

**Trigger it:** "`/researcher:review-paper`", "Review my manuscript with a full panel and give me scores".

## revision-management

Parses reviewer comments from any format (pasted text, a PDF report, Word inline comments, or peer-review output), numbers every discrete point (`R1.C1`, `R2.C3`), and sorts each into must-address, should-address, optional, or out-of-scope. For LaTeX manuscripts it produces a `latexdiff` comparison against the prior revision so the editor can see exactly what moved and where; DOCX tracked changes are specified but not yet implemented (`templates/word/build-docx.js` generates headings, paragraphs, and lists from `sections/*.md` today, not revision marks).

**Trigger it:** "`/researcher:revise`", "Address these reviewer comments and produce tracked changes".

## response-to-reviewers

Turns the parsed comments into a point-by-point rebuttal: each comment quoted, answered, and tied to the specific manuscript location that changed. It writes candid outcomes (an effect reclassified as inconclusive after proper multi-seed statistics) rather than defending the indefensible, and where you disagree it backs the disagreement with evidence (declining to reproduce a method whose pretraining protocol is documented as non-comparable by Liu et al., 2023) instead of hand-waving.

**Trigger it:** "Draft a point-by-point response to these reviewer comments".

## cover-letter

Writes a journal-appropriate submission letter from the standard template: submission statement, contribution summary, a fit paragraph, originality and exclusivity, conflict-of-interest, and data availability. The fit paragraph gives a concrete, verifiable reason (IEEE JBHI defined the PTB-XL benchmarking protocol the paper is measured against) rather than flattery, and it deliberately withholds specific numeric results, keeping them where they belong in the paper.

**Trigger it:** "Write a cover letter for my JBHI submission".

## See it in action

The [write-a-paper recipe](/researcher/cookbook/write-a-paper/) runs the full arc (draft, review, revise, respond) end to end, and the [`examples/writing-review/`](https://github.com/sokolmarek/researcher/tree/main/examples/writing-review) folder has the complete worked output, including the drafted introduction, the five-persona review report, and the response to reviewers.
