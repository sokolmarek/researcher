# M2 benchmarks: the measured evidence kernel

This file records what the kernel actually does on the gold sets. It is the M2 exit gate (D16,
D17): no M3 skill work begins until the lines in [Gate status](#gate-status) are green, and two
of them are not.

Everything here was MEASURED, on the date below, by the command below, offline from snapshots.
Nothing here is a target, an estimate, or a number carried over from a smaller set. Where a
number is worse than we would like, it is printed anyway, and where an n cannot certify a claim,
this file says so instead of implying that it can.

## Reproducing every number in this file

```
# the whole suite, offline, from evals/snapshots/ (no network, nothing to configure)
uv run --project core python evals/run_axes.py

# one axis
uv run --project core python evals/run_axes.py --axis identity

# machine-readable
uv run --project core python evals/run_axes.py --json

# the secondary retrieval configuration reported below
uv run --project core python evals/run_axes.py --axis retrieval --retrieval-sources crossref,arxiv

# LIVE. Hits the real APIs and rewrites evals/snapshots/. Not deterministic, by definition.
uv run --project core python evals/run_axes.py --record
```

The runner exits 1 while any gold item is skipped, so a CI job cannot go green over a benchmark
that quietly measured half its gold set. It exits 1 today: see [Gate status](#gate-status).

## Provenance and determinism

| | |
|---|---|
| core version | 0.1.0 |
| Snapshots | `evals/snapshots/`, 1126 recorded responses (arxiv 55, crossref 341, datacite 224, fulltext 6, openalex 317, pubmed 78, unpaywall 105) |
| Recorded | 2026-07-14, live, from the keyless public APIs, polite pool `mareksokol98@gmail.com` |
| Replay | every number below was produced with zero network calls. Replay mode never awaits a fetcher. |
| Determinism (D15) | two consecutive runs produced byte-identical reports: both `--json` and the human report hash to the same digest (`be6d058f6b3f300bbff6aeae276027f8` for the human report). |

Determinism is claimed only for replay from a fixed snapshot set, configuration, and parser
version, which is exactly what D15 defines it to be. It is not claimed for `--record`.

## The headline: axis (a), reference identity

The number that matters is not accuracy. It is the **refusal-grade false positive rate**: how
often the kernel tells a researcher that a REAL reference of theirs looks fabricated or wrong.
Only `unresolvable` and `mismatch` are refusal-grade; `inconclusive` never is.

```
refusal-grade FALSE POSITIVE    3/99    0.030   95% Wilson [0.010, 0.085]
refusal-grade FALSE NEGATIVE    0/50    0.000   95% Wilson [0.000, 0.071]
```

**The false positive is the worse error, and it is not close.** A false positive tells an honest
author that a citation they read, used, and cited correctly does not exist. It attacks the
person the tool is supposed to serve, it is the failure that destroys trust in the whole system
on first contact, and the author has no way to defend against it except to distrust the tool. A
false negative merely fails to catch a bad citation, which leaves the author exactly where they
were without the tool: it is a missed catch, not an accusation. D9's precedence is built to trade
in that direction (thin or dirty evidence falls to `inconclusive`, never to a refusal), and the
measured 0/50 false negatives with 3/99 false positives shows the trade is real but not free.

### The three false positives, named

Silence about which items failed would be the same as not measuring them.

| Reference | Gold | Called | Why |
|---|---|---|---|
| `10.1109/taffc.2020.3014842` (Sarkar and Etemad, self-supervised ECG) | verified | **mismatch** | OpenAlex confirms it. Crossref resolves it with a year 2 off (IEEE early access versus issue year). DataCite, which does not mint this DOI, "resolves" it through the title-search fallback and reports `doi_mismatch`. Two resolving disagreements outvote one confirmation, and D9 rule 2 fires. |
| `10.5281/zenodo.21358727` (a real Zenodo dataset) | inconclusive | **mismatch** | DataCite confirms it. OpenAlex and Crossref do not hold the DOI, find a similar record by title search, and each report `doi_mismatch`. Two indexes that do not hold the record manufacture the disagreement. |
| `10.17026/ar/sraj8f` (a real DANS archaeology dataset) | inconclusive | **mismatch** | DataCite resolves the DOI, but the gold title is truncated at 88 characters and the real title is far longer, so similarity is 0.539, below the 0.70 bar. The truncation relaxation does not fire because the short title is under 40% of the long one. |

Two of the three share one root cause: **the title-search fallback lets a source that does not
hold a DOI produce a resolving disagreement.** An index that does not mint a DOI should return a
clean negative for it, not a `doi_mismatch` against a paper it found by title. That is a defect
in the identity layer, it is refusal-grade, and it is the single highest-value fix the M3
citation audit depends on. It is filed below.

`core/CALIBRATION.md` measured 0/8 refusal-grade false positives on the 8 honest references of
the calibration subset. At n = 99 the rate is not zero. Both numbers are correct; the small one
simply could not see this.

### Full confusion matrix

```
gold \ predicted  verified  mismatch  unresolvable  inconclusive
verified                65         1             0             8
mismatch                 0        25             0             0
unresolvable             0         0            25             0
inconclusive             5         2             0            18

accuracy   133/149   0.893  95% Wilson [0.833, 0.933]
```

| class | n | recall (95% Wilson) | precision (95% Wilson) |
|---|---|---|---|
| verified | 74 | 0.878 [0.785, 0.935] | 0.929 [0.843, 0.969] |
| mismatch | 25 | 1.000 [0.867, 1.000] | 0.893 [0.728, 0.963] |
| unresolvable | 25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| inconclusive | 25 | 0.720 [0.524, 0.857] | 0.692 [0.500, 0.835] |

Every one of the 25 invented references was caught, and no real reference was ever called
`unresolvable`. The `unresolvable` column is clean top to bottom, which is the property the
commit hook and the M3 compile gate stand on.

**The 8 verified references that fell to `inconclusive` all fail the same way**, and it is worth
naming because it looks like a bug and is not: title similarity is 1.000 at both OpenAlex and
Crossref, but one of the two disagrees on the first-author surname (compound surnames such as
"Al Rahhal" are split differently by different indexes) or on the year (early-access versus
issue), so only one source confirms, the 2-confirmation bar is not met, and the verdict falls to
`inconclusive`. `inconclusive` is never refusal-grade and never blocks anyone. The cost is
recall on `verified`, not safety.

## Axis (b): publication status

```
gold \ predicted       current  corrected  retracted  expression-of-concern
current                     45          0          0                      0
corrected                    0         25          0                      0
retracted                    0          0         25                      0
expression-of-concern        0          0          6                     19

accuracy   114/120   0.950  95% Wilson [0.895, 0.977]
unchecked      0     (no entry rests on an absence of evidence)
conflicts      0
```

| class | n | recall (95% Wilson) | precision (95% Wilson) |
|---|---|---|---|
| current | 45 | 1.000 [0.921, 1.000] | 1.000 [0.921, 1.000] |
| corrected | 25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| retracted | 25 | 1.000 [0.867, 1.000] | 0.806 [0.637, 0.908] |
| expression-of-concern | 25 | 0.760 [0.566, 0.885] | 1.000 [0.832, 1.000] |

All 6 errors are the same case, and `core/CALIBRATION.md` documents it in detail: a paper that
received an expression of concern and was LATER RETRACTED. The kernel reports `retracted`
(strongest notice wins) and OpenAlex independently confirms `is_retracted: true` on all six. The
gold labels are the stale side of that disagreement, because the set was harvested by filtering
Crossref on `update-type:expression_of_concern`, which matches any work that has ever had one.
Against corrected labels the classifier is 120/120. **This file does not edit the gold set it is
measured against**, so the 0.950 above stands as measured, and the six DOIs are listed in
`core/CALIBRATION.md` for the gold set's owner to reclassify.

Zero entries were unchecked. Not one verdict rests on a source that failed to answer.

## Axis (d): accessibility

```
gold \ predicted  full-text  abstract-only  unavailable
full-text                42              0            0
abstract-only             1             32            0
unavailable               0              0           30

accuracy   104/105   0.990  95% Wilson [0.948, 0.998]
```

| class | n | recall (95% Wilson) | precision (95% Wilson) |
|---|---|---|---|
| full-text | 42 | 1.000 [0.916, 1.000] | 0.977 [0.879, 0.996] |
| abstract-only | 33 | 0.970 [0.847, 0.995] | 1.000 [0.893, 1.000] |
| unavailable | 30 | 1.000 [0.886, 1.000] | 1.000 [0.886, 1.000] |

The single off-diagonal cell is `10.1038/s41591-018-0268-3`, and it is arguably not an error at
all: Unpaywall (which is where the gold labels come from) reports no OA copy, while the kernel's
cascade continues to PubMed, finds PMC6784839, and returns `full-text`. The kernel is right and
the label is narrow. It is left as an error rather than argued away, because the alternative is a
benchmark that explains away its own misses.

## Axis (c): claim faithfulness, and the price of abstention

`insufficient-passage` is ABSTENTION, not a wrong answer.

```
gold \ predicted      supported  partial  contradicted  insufficient-passage
supported                    20        1             5                     0
partial                      12        7             7                     0
contradicted                  6        6            14                     0
insufficient-passage          0        0             0                    26

accuracy over ALL items         67/104   0.644  95% Wilson [0.549, 0.730]
accuracy over ANSWERED items    41/78    0.526  95% Wilson [0.416, 0.633]
coverage (fraction answered)    78/104   0.750  95% Wilson [0.659, 0.823]
correct abstentions             26/26    1.000  95% Wilson [0.871, 1.000]
passage anchoring               74/78    0.949  95% Wilson [0.875, 0.980]
```

| class | n | recall (95% Wilson) | precision (95% Wilson) |
|---|---|---|---|
| supported | 26 | 0.769 [0.579, 0.890] | 0.526 [0.373, 0.675] |
| partial | 26 | 0.269 [0.137, 0.461] | 0.500 [0.268, 0.732] |
| contradicted | 26 | 0.538 [0.355, 0.712] | 0.538 [0.355, 0.712] |
| insufficient-passage | 26 | 1.000 [0.871, 1.000] | 1.000 [0.871, 1.000] |

**This is a weak classifier and the numbers say so.** M2 ships a LEXICAL baseline (BM25 retrieval
plus token overlap and polarity heuristics), and a lexical baseline cannot read. It recovers
`supported` reasonably (0.769) and it abstains perfectly when there is no full text (26/26), but
`partial` recall is 0.269: an overstatement reuses almost every token of the passage it
overstates, so token overlap scores it as support. Twelve of the 26 `partial` claims were called
`supported`. That is the failure mode of the method, it is exactly what D16 expects a baseline to
do, and it is the measurement M3's claim anchoring has to beat.

The abstention side is clean in the one direction that matters: **no claim over a document
without full text was ever emitted as an answer** (the `insufficient-passage` row and column are
both perfectly diagonal), which is the D11 invariant.

Passage anchoring is 74/78: when the kernel answered, it cited the exact passage the gold item
was written against 95% of the time. The 4 misses are not verdict errors; the kernel justified
its verdict from a different real passage of the same document.

### Risk-coverage curve (selective prediction)

Accuracy over answered items (0.526) is the number a vendor would quote. It is meaningless
without its coverage (0.750), because an oracle that abstains on everything has perfect accuracy
on what it answers and is worthless. The curve is what prices abstention.

Every answerable item (a document with indexed passages) is forced to an answer, using the same
decision procedure with the `insufficient-passage` floor removed, and scored by its best
passage-overlap confidence. A policy answers everything at or above the threshold.

| confidence >= | coverage | answered | errors | risk |
|---|---|---|---|---|
| 1.000 | 0.231 | 18 | 2 | **0.111** |
| 0.941 | 0.256 | 20 | 4 | 0.200 |
| 0.909 | 0.321 | 25 | 5 | 0.200 |
| 0.882 | 0.372 | 29 | 8 | 0.276 |
| 0.857 | 0.449 | 35 | 12 | 0.343 |
| 0.818 | 0.526 | 41 | 16 | 0.390 |
| 0.769 | 0.577 | 45 | 19 | 0.422 |
| 0.750 | 0.641 | 50 | 23 | 0.460 |
| 0.700 | 0.744 | 58 | 26 | 0.448 |
| 0.667 | 0.821 | 64 | 28 | 0.438 |
| 0.600 | 0.949 | 74 | 34 | 0.459 |
| 0.545 | **1.000** | 78 | 37 | **0.474** |

```
answerable items             78    (documents with indexed passages)
structurally unanswerable    26    (no full text: nothing to anchor on, excluded from the curve)
AURC (mean risk over the curve)  0.380
```

Read it as follows. At full coverage the forced classifier is wrong 47.4% of the time. Abstaining
on the low-confidence tail buys real safety: at 23% coverage the risk falls to 11.1%, roughly a
quarter of the full-coverage risk. The confidence signal is therefore informative (risk decreases
monotonically as coverage shrinks, which is not guaranteed and is the thing the curve tests), but
the price is steep: to get to an 11% error rate this baseline must decline to answer three
quarters of the claims it could answer. **That is the honest summary of axis (c) in M2, and it is
the argument for the M3 anchoring work, stated as a number rather than an intuition.**

Coverage 0.0 is the degenerate oracle: it abstains on everything, it has no risk, and it is
useless. That point is on this curve too, which is precisely why the curve is printed and a
single accuracy figure is not.

## Retrieval: recall@k

**The default configuration is INCOMPLETE and this axis does not meet its D17 size.**

OpenAlex now meters full-text search on a daily budget ("Insufficient budget ... Resets at
midnight UTC"). The budget ran out partway through the snapshot recording, so 22 of the 55
known-item queries have no OpenAlex search snapshot. They are reported as SKIPPED, they are not
silently dropped, and they are not quietly turned into a live call.

Primary configuration, `openalex,crossref,arxiv`, **33 of 55 queries scored, 22 SKIPPED**:

| k | hits | recall (95% Wilson) |
|---|---|---|
| 1 | 25/33 | 0.758 [0.590, 0.872] |
| 3 | 30/33 | 0.909 [0.764, 0.969] |
| 5 | 30/33 | 0.909 [0.764, 0.969] |
| 10 | 33/33 | 1.000 [0.896, 1.000] |

MRR 0.846. **These numbers are over a 33-query subset and cannot be read as the retrieval
result.** The missing 22 are not random: they are the self-supervised-learning block of the gold
set, so the scored subset is topically skewed toward the ECG block.

Secondary configuration, `crossref,arxiv`, whose snapshots ARE complete, **55 of 55 scored**:

| k | hits | recall (95% Wilson) |
|---|---|---|
| 1 | 51/55 | 0.927 [0.827, 0.971] |
| 3 | 53/55 | 0.964 [0.877, 0.990] |
| 5 | 53/55 | 0.964 [0.877, 0.990] |
| 10 | 54/55 | 0.982 [0.904, 0.997] |

MRR 0.947. This is a DIFFERENT system (two sources, not three), so it is not comparable with the
primary numbers and does not substitute for them. It is reported because it is the one retrieval
measurement in this file that covers all 55 gold queries, and because it establishes that the
missing OpenAlex snapshots are the only thing standing between this axis and its gate.

To complete the axis, after the OpenAlex budget resets at midnight UTC:

```
uv run --project core python evals/run_axes.py --record --axis retrieval
```

## Dedup: pair accuracy, and the two error directions

```
gold \ predicted   same  different
same                110          0
different             0        100

pair accuracy   210/210   1.000  95% Wilson [0.982, 1.000]
```

```
FALSE MERGE (gold different -> same)    0/100   0.000   95% Wilson [0.000, 0.037]
FALSE SPLIT (gold same -> different)    0/110   0.000   95% Wilson [0.000, 0.034]
```

**These two errors are not equally bad, and the threshold is tuned accordingly.** A false merge
DESTROYS DATA: two distinct papers collapse into one, one of the two records is gone, its DOI no
longer appears in the result set, and no downstream step can recover it. A systematic review that
false-merges has silently dropped a study from its evidence base and will never know. A false
split merely leaves a duplicate standing: it is visible, a human sees it, nothing is lost, and it
costs a reader's attention rather than a study. `dedupe.py` requires DOI equality or a 0.90
normalized-title similarity and refuses to merge records whose DOIs conflict outright, which is
the conservative direction. On 210 labeled pairs, including hard negatives (real papers on the
same topic with similar titles that are NOT the same work), it made neither error.

## What these n certify, and what they do not

D17's arithmetic, applied to the numbers above rather than gestured at.

Zero-error certification: 0.9^29 = 0.047 < 0.05, so certifying an error rate below 0.10 at 95%
confidence needs 0 errors in n >= 29 (exact one-sided; the two-sided Wilson bound needs n >= 35).
0.85^19 = 0.046 < 0.05, so certifying below 0.15 needs 0 misses in n >= 19 (Wilson: n >= 22).

**Certified by the numbers above:**

- **Refusal-grade FPR below 0.10.** 3 errors in 99 negatives, 95% Wilson [0.010, 0.085]. The
  upper bound is below 0.10, so the claim holds at 95% confidence. It does NOT certify FPR below
  0.05: the upper bound is 0.085, above 0.05. To claim 0.05 the negative set must grow or the two
  title-search defects must be fixed.
- **Refusal-grade FNR below 0.15, and below 0.10.** 0 misses in 50 refusal-grade positives, 95%
  Wilson [0.000, 0.071]. Zero errors in n = 50 clears both of D17's thresholds (n >= 29 and
  n >= 22).
- **Dedup false-merge rate below 0.05.** 0 in 100, 95% Wilson [0.000, 0.037].
- **Dedup false-split rate below 0.05.** 0 in 110, 95% Wilson [0.000, 0.034].
- **Faithfulness abstention correctness.** 26/26 correct abstentions on documents with no full
  text, 95% Wilson [0.871, 1.000], which certifies only that the rate is above 0.871. It does not
  certify "always", and no n we can afford would.

**NOT certified, and stated here so nobody quotes them as if they were:**

- **Any per-class rate at n = 25 or n = 26.** A perfect 25/25 has a 95% Wilson interval of
  [0.867, 1.000]. The implied error-rate upper bound is 0.133, which is ABOVE 0.10, so a
  per-class n of 25 cannot certify an error rate below 0.10 even with zero errors. This binds
  every per-class row of axes (a), (b) and (c) above: `mismatch` recall 1.000, `unresolvable`
  recall 1.000, `corrected` recall 1.000 and `retracted` recall 1.000 are all real measurements
  and none of them certifies a 0.10 bound. D17 says exactly this, and the per-class floors exist
  to make each class MEASURABLE, not to certify it.
- **The retrieval numbers.** The primary configuration scored 33 of 55 queries. No claim of any
  kind is made from it.
- **Axis (c) accuracy.** 0.644 overall, 0.526 over answered items, on a lexical baseline. These
  are measurements of a baseline, not a bar anything should be held to.
- **Anything at all from the live canary.** Determinism is never claimed for live calls (D15).

## Gate status

The M2 exit gate is these benchmarks green at D17 sizes. Two lines are not.

| Gate | Size required (D17) | Gold | Scored | Status |
|---|---|---|---|---|
| Axis (a) identity | >= 150 tuples, >= 25/class, >= 100 negatives | 150 (75/25/25/25), 100 negatives | 149, 99 negatives | **RED**: 1 item unscorable (see below) |
| Axis (b) status | >= 120, >= 20/class | 120 (45/25/25/25) | 120 | GREEN |
| Axis (c) faithfulness | >= 100 pairs, >= 20/class, risk-coverage reported | 104 (26/26/26/26) | 104 | GREEN |
| Axis (d) accessibility | >= 100 DOIs | 105 | 105 | GREEN |
| Retrieval | >= 50 known-item queries | 55 | 33 | **RED**: 22 OpenAlex search snapshots missing |
| Dedup | >= 200 labeled pairs | 210 | 210 | GREEN |
| Determinism (D15) | byte-identical across two runs | | | GREEN |

The two red lines, and what closes them:

1. **Retrieval, 22 missing snapshots.** OpenAlex's daily search budget was exhausted during
   recording. Re-run `python evals/run_axes.py --record --axis retrieval` after the budget resets
   at midnight UTC. Nothing about the kernel needs to change.
2. **Identity, 1 unscorable item.** `10.1016/s0140-6736(21)01698-6` cannot be snapshotted,
   because DataCite's search API returns **HTTP 400** for its gold title. This is a real kernel
   defect, and the benchmark found it. See below.

## Defects this benchmark found

These belong to the connector and verify layers, not to this file. They are recorded here because
a benchmark that finds bugs and does not report them is decoration.

1. **DataCite queries are not sanitized (HTTP 400).** The gold title
   `"Implantable loop recorder detection of atrial fibrillation to prevent stroke (The LOOP Stu"`
   is truncated mid-word, leaving an unbalanced parenthesis. `datacite.py` passes it to
   `api.datacite.org/dois?query=...` verbatim, DataCite's query parser rejects it, and the source
   returns HTTP 400. The kernel handles the failure SAFELY (`source_error`, therefore
   `inconclusive`, therefore never a refusal), so no user is ever accused because of it, but the
   source silently contributes nothing and the request cannot be snapshotted. Truncated titles
   with unbalanced brackets are ordinary in real `.bib` files.
2. **The title-search fallback lets a non-holding index manufacture a `doi_mismatch`.** When a
   source does not hold a DOI, finds a similar work by title, and reports `doi_mismatch`, two
   such sources can outvote a genuine confirmation and produce a refusal-grade `mismatch` on a
   real reference. This caused 2 of the 3 refusal-grade false positives above
   (`10.1109/taffc.2020.3014842`, `10.5281/zenodo.21358727`). A Zenodo DOI is not Crossref's to
   disagree about, and an index that does not mint a DOI should return a clean negative for it.
3. **PMC blocks automated fetches with an interstitial.** `https://www.ncbi.nlm.nih.gov/pmc/...`
   returns a "Checking your browser" page to httpx, which the extractor reads as a 1-segment
   full-text document. It does not affect any number above (the faithfulness gold deliberately
   sources full text from arXiv HTML and PLOS, and no gold item resolves through PMC), but any
   future document that resolves through the PMC cascade step will extract a junk passage rather
   than an article. The OA cascade should treat the interstitial as a miss.
