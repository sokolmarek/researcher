---
title: "Guide: Publishing & Formatting"
description: The five skills that pick a venue, format for it, and keep your bibliography honest.
sidebar:
  label: Publishing & Formatting
  order: 5
---

You have a manuscript. Now comes the part nobody warned you about in grad school: choosing where to send it, wrestling it into that publisher's document class, and making sure every DOI still resolves. These five skills handle the endgame, and they never invent a journal, a deadline, or a citation to fill a gap.

## journal-finder

Recommends best-fit journals with a ranked shortlist and, crucially, a fit rationale for each one. Fit is argued from evidence rather than prestige: the recommendation names which venue published your manuscript's actual predecessors or benchmark. For the running self-supervised-ECG example, IEEE JBHI ranks first because the PTB-XL benchmark itself was published there (Strodthoff et al., 2021, https://doi.org/10.1109/jbhi.2020.3022989), with Computers in Biology and Medicine close behind as the home of the closest methodological predecessor (Mehari & Strodthoff, 2022, https://doi.org/10.1016/j.compbiomed.2021.105114). Volatile numbers like impact factor and APC are never fabricated; each is tagged for you to confirm at a named source with an access date.

**Trigger it:** "`/find-journal`", "Recommend target journals for my paper".

## conference-finder

Finds peer-reviewed venues and reports each one's format and typical timing. Because submission deadlines shift every cycle, exact dates are never invented: each venue gets its stable characteristics plus a flag to confirm the current CFP at the homepage. Fit is again grounded in real prior work, so Computing in Cardiology, CHIL, and ML4H surface for the ECG example because that community actually publishes ECG self-supervised learning there.

**Trigger it:** "`/find-conference`", "Find conferences for this work with deadlines".

## journal-formatting

Auto-applies a publisher's submission requirements to your manuscript: the right document class, citation style, required sections, and structure. It knows Elsevier (`elsarticle`), Springer (`svjour3`), IEEE (`IEEEtran`), ACM (`acmart`), Nature, Science, PLOS, MDPI, and 50-plus more. That means the correct scaffold, plus the fiddly bits publishers reject over: Elsevier Highlights and a Data Availability Statement, IEEE Index Terms, Nature's Methods-after-references ordering, CRediT contributions.

**Trigger it:** "Format this for Elsevier", "Apply IEEE submission requirements".

## word-output

Produces a full Microsoft Word DOCX via `docx-js`, for the co-authors and journals that live in Word. It converts from LaTeX (pandoc for the baseline, then `docx-js` to repair tables, figures, headings, and citations) or builds natively from Word-mode section files. It supports tracked changes and comments, so a revision round can be delivered the way reviewers and editors expect to receive it.

**Trigger it:** "Export to Word", "I need a DOCX with tracked changes".

## citation-management

Maintains your `library.bib` across its whole lifecycle: import, validate, convert, audit. It validates DOIs against the source, detects retractions and corrections before you cite something embarrassing, converts between citation formats, and syncs with Zotero and Mendeley. The one rule it will not bend: every entry originates from a real source, and an unresolvable DOI gets flagged rather than guessed into existence.

**Trigger it:** "`/cite`", "Validate my bibliography", "Sync my Zotero library".

## See it in action

The [find-a-home recipe](/researcher/cookbook/find-a-home/) runs journal-finder and conference-finder end to end on the ECG example, and the [`examples/publishing/`](https://github.com/sokolmarek/researcher/tree/main/examples/publishing) folder has the full worked reports.
