# M2 benchmarks: the measured evidence kernel

This file records what the kernel actually does on the gold sets. It is the M2 exit gate (D16,
D17): no M3 skill work begins until the lines in [Gate status](#gate-status) are green, and they
now all are.

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

# the M4.7 extraction gate (a separate runner; same snapshot store, same offline rules)
uv run --project core python evals/run_extraction.py
uv run --project core python evals/run_extraction.py --json
```

The runner exits 1 while any gold item is skipped, so a CI job cannot go green over a benchmark
that quietly measured half its gold set. It exits 0 today, with every gold set fully scored: see
[Gate status](#gate-status).

## Provenance and determinism

| | |
|---|---|
| core version | 0.1.0 |
| Snapshots | `evals/snapshots/`, 1198 recorded responses (arxiv 55, crossref 342, datacite 272, fulltext 6, openalex 340, pubmed 78, unpaywall 105) |
| Recorded | 2026-07-14, live, from the keyless public APIs, polite pool `mareksokol98@gmail.com` |
| Replay | every number below was produced with zero network calls. Replay mode never awaits a fetcher. |
| Determinism (D15) | two consecutive `--json` runs produced byte-identical output (md5 `bbc01679ccabfcbd0a11fe6b088963f8`). A deletion test confirms replay is read-only: removing a stored snapshot and running with no flag reports that item skipped and re-fetches nothing. |

Determinism is claimed only for replay from a fixed snapshot set, configuration, and parser
version, which is exactly what D15 defines it to be. It is not claimed for `--record`.

## The headline: axis (a), reference identity

The number that matters is not accuracy. It is the **refusal-grade false positive rate**: how
often the kernel tells a researcher that a REAL reference of theirs looks fabricated or wrong.
Only `unresolvable` and `mismatch` are refusal-grade; `inconclusive` never is.

```
refusal-grade FALSE POSITIVE    0/100   0.000   95% Wilson [0.000, 0.037]
refusal-grade FALSE NEGATIVE    0/50    0.000   95% Wilson [0.000, 0.071]
```

**The false positive is the worse error, and it is not close.** A false positive tells an honest
author that a citation they read, used, and cited correctly does not exist. It attacks the
person the tool is supposed to serve, it is the failure that destroys trust in the whole system
on first contact, and the author has no way to defend against it except to distrust the tool. A
false negative merely fails to catch a bad citation, which leaves the author exactly where they
were without the tool: it is a missed catch, not an accusation. D9's precedence is built to trade
in that direction (thin or dirty evidence falls to `inconclusive`, never to a refusal), and the
measured 0/50 false negatives alongside 0/100 false positives show the trade holds in both
directions. It is not free: the cost is paid in `verified` recall, where nine real references fall
to `inconclusive` (below), never in a refusal.

### Zero false positives, and where the three that used to be here went

Silence about which items failed would be the same as not measuring them, so this section names
what happened rather than declaring victory. An earlier run of this same gold set measured
**3/99** refusal-grade false positives on real references, and named all three. They are gone.
Two shared a single root cause (a source that did not hold a DOI was allowed to manufacture a
`doi_mismatch` against a paper it found by title); the third was a harsh title truncation the
matcher could not read as truncation. A fourth reference that could not be scored at all, because
a colon in its title made DataCite return zero hits, is now scored, which is why the negative set
is 100 rather than 99. All of that is recorded in **Fixes this benchmark drove** below, and the
colon fix in particular must not be reintroduced. The refusal-grade false positive rate is now
0/100, and neither refusal-grade recall moved: every invented reference and every wrong-DOI entry
is still caught.

`core/CALIBRATION.md` measured 0/8 refusal-grade false positives on the 8 honest references of
the calibration subset. At n = 100 the rate is still zero, and the interval is now tight enough
to license a bound, which the calibration set at n = 8 could not (see the certification section
below).

### Full confusion matrix

```
gold \ predicted  verified  mismatch  unresolvable  inconclusive
verified                66         0             0             9
mismatch                 0        25             0             0
unresolvable             0         0            25             0
inconclusive             5         0             0            20

accuracy   136/150   0.907  95% Wilson [0.849, 0.944]
```

| class | n | recall (95% Wilson) | precision (95% Wilson) |
|---|---|---|---|
| verified | 75 | 0.880 [0.787, 0.936] | 0.930 [0.846, 0.970] |
| mismatch | 25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| unresolvable | 25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| inconclusive | 25 | 0.800 [0.609, 0.911] | 0.690 [0.508, 0.827] |

Every one of the 25 invented references was caught, and no real reference was ever called
`mismatch` or `unresolvable`. Both refusal-grade columns are clean top to bottom, which is the
property the commit hook and the M3 compile gate stand on.

**The 9 verified references that fell to `inconclusive` all fail the same way**, and it is worth
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
retracted                    0          0         31                      0
expression-of-concern        0          0          0                     20

accuracy   121/121   1.000  95% Wilson [0.969, 1.000]
unchecked      0     (no entry rests on an absence of evidence)
conflicts      0
```

| class | n | recall (95% Wilson) | precision (95% Wilson) |
|---|---|---|---|
| current | 45 | 1.000 [0.921, 1.000] | 1.000 [0.921, 1.000] |
| corrected | 25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| retracted | 31 | 1.000 [0.890, 1.000] | 1.000 [0.890, 1.000] |
| expression-of-concern | 20 | 1.000 [0.839, 1.000] | 1.000 [0.839, 1.000] |

The classifier is perfect on all four classes. Six gold items are the reason retracted reads 31
rather than 25: each received an expression of concern and was LATER RETRACTED, so the original
harvest (a Crossref filter on `update-type:expression_of_concern`, which matches any work that has
ever had one) had captured the first notice rather than the current status. Their labels were
corrected against the papers' own Crossref retraction notices, and `status.py` now lets Crossref's
specific update-type outrank OpenAlex's coarse `is_retracted` boolean. Both changes are recorded in
**Fixes this benchmark drove** below. Against the earlier stale labels the same classifier read
114/120; the six were the entire gap. Relabeling six items out of expression-of-concern would have
left that class at 19, one under the 20-per-class floor, so one further genuine expression-of-concern
paper (verified live: real paper title, an expression_of_concern in Crossref update-to, no retraction
notice, OpenAlex is_retracted false) was added to restore it to 20. Every class now meets its floor,
and all four score recall and precision 1.000.

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

The primary configuration, `openalex,crossref,arxiv`, now covers the whole gold set: **55 of 55
known-item queries scored, 0 skipped.** Every query is the exact title of a real paper and the
target is that paper's DOI, so a search that cannot find a paper when handed its exact title will
not find it from a vaguer one: this is the floor, not the bar.

| k | hits | recall (95% Wilson) |
|---|---|---|
| 1 | 45/55 | 0.818 [0.697, 0.898] |
| 3 | 51/55 | 0.927 [0.827, 0.971] |
| 5 | 51/55 | 0.927 [0.827, 0.971] |
| 10 | 55/55 | 1.000 [0.935, 1.000] |

MRR 0.883. Sources are openalex, crossref, and arxiv, deduplicated and ranked. An earlier run of
this axis scored only 33 of 55: OpenAlex's daily full-text-search budget was exhausted during
recording, so 22 queries (the self-supervised-learning block of the set) had no OpenAlex snapshot.
Those snapshots are now recorded, the axis is complete, and the scored set is no longer topically
skewed toward the ECG block.

Secondary configuration, `crossref,arxiv`, also 55 of 55 scored:

| k | hits | recall (95% Wilson) |
|---|---|---|
| 1 | 51/55 | 0.927 [0.827, 0.971] |
| 3 | 53/55 | 0.964 [0.877, 0.990] |
| 5 | 53/55 | 0.964 [0.877, 0.990] |
| 10 | 54/55 | 0.982 [0.904, 0.997] |

MRR 0.947. This is a DIFFERENT system (two sources, not three), so it is not a substitute for the
primary numbers, and the comparison is worth stating plainly: dropping OpenAlex RAISES recall@1
(0.927 versus 0.818) and MRR (0.947 versus 0.883), because OpenAlex results reorder the ranking
and push some targets below rank 1, but it LOWERS recall@10 (0.982 versus 1.000), because OpenAlex
is the only source that holds the one paper `crossref,arxiv` never finds. Three sources find
everything by k = 10; two sources rank the ones they do find slightly higher.

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

## Extraction (axis M4.7): a lexical anchoring baseline

This section is the M4.7 gate for the `extraction-tables` skill (D18): the skill may claim only
the accuracy measured here, and only for the layer it measures. It is NOT part of the M2 exit
gate above; it is measured by a separate runner (`evals/run_extraction.py`) that shares this
file's snapshot store, offline replay rule, and Wilson-interval convention. It added no
snapshots: all 147 cells replay from the same committed store the axes above use (the six
open-access full texts under `evals/snapshots/fulltext/`, and the two abstract-only papers'
OpenAlex records that the identity axis already recorded).

**Read this exactly as you read axis (c).** It is a LEXICAL baseline and it is weak in the same
way, on purpose. A cell is a `(paper, column, expected value)` triple; every value was read off
the paper's own text, and where a value is genuinely absent the cell is labeled `not reported`
(a fabricated cell is worse than a missing one). Given a paper's indexed passages and an
ANSWER-FREE probe, the runner asks only whether the labeled value is LOCATABLE and whether a
genuinely-absent value is correctly ABSTAINED on. Reading the value out of the located passage,
resolving which of two datasets a cell means, disambiguating a metric name from a description:
that is Claude's judgment layer on top, not core's, and it is not measured here.

The gold set is 147 cells, 119 with a value and 28 `not reported`, at least 20 per column type
(population 23, method 23, dataset 23, metric_name 28, metric_value 26, sample_size 24). 125
cells anchor at the FULL-TEXT layer (the six OA papers, indexed into passages) and 22 at the
ABSTRACT layer (two paywalled papers with no OA full text, indexed from their OpenAlex abstract).
An abstract-layer cell is never reported as full-text-verified (D11/D18); the runner asserts it.

### Location accuracy: can the labeled value be found

```
overall (present cells)        109/119   0.916  95% Wilson [0.852, 0.954]
  of which grounded on concept 114/119   0.958
  value present in a passage   109/119   0.916
```

| column type | n (present) | location accuracy (95% Wilson) |
|---|---|---|
| population | 18 | 0.778 [0.548, 0.910] |
| method | 21 | 0.952 [0.773, 0.992] |
| dataset | 21 | 1.000 [0.845, 1.000] |
| metric_name | 18 | 0.722 [0.491, 0.875] |
| metric_value | 20 | 1.000 [0.839, 1.000] |
| sample_size | 21 | 1.000 [0.845, 1.000] |

**The spread across columns is the honest story, and it is the story of a lexical method.** The
runner nails a column when the value is a distinctive string the probe's neighbourhood contains:
a dataset name (`2018 UCR Time Series Archive`), a numeric result (`0.934`, `63.026%`), or an
explicit count (`128 time series classification datasets`) all score 1.000, because once the
concept passage is retrieved the value string is right there. It is weakest on `metric_name`
(0.722): a metric name IS the concept, so an answer-free probe (`what threshold-free ranking
metric is reported`) rarely shares a token with the sentence that names it (`AUROC`), and the
lexical retriever cannot bridge that purpose-to-name gap. `population` (0.778) fails the same
way when the population is a generic phrase (`time series classification`) that the probe
describes without quoting. These are not bugs to be tuned away; they are exactly the semantic
gap that D16 expects a lexical baseline to fall into, and the number M3's claim-anchoring and
Claude's extraction layer have to beat.

Per anchor layer, reported separately so the two are never blended:

```
full-text   90/100   0.900  95% Wilson [0.826, 0.945]
abstract    19/19    1.000  95% Wilson [0.832, 1.000]
```

The abstract layer reads 1.000, but that number is EASIER and is not comparable to the full-text
one: at the abstract layer the whole abstract is a single retrieved unit, so "locatable" collapses
to "the value is stated somewhere in the abstract", with no passage retrieval to miss. It is
reported to show the layer path works and stays labeled, not as evidence the extractor is better
on abstracts.

### Abstention: the "not reported" side

```
'not reported' precision   25/30   0.833  95% Wilson [0.664, 0.927]
'not reported' detection   25/28   0.893  95% Wilson [0.728, 0.963]
FABRICATION RISK            3/28    0.107  95% Wilson [0.037, 0.272]
```

Precision here is "of the cells the extractor called ABSENT, the fraction truly `not reported`".
It is 0.833 rather than higher because a present cell the extractor failed to locate (a location
miss) looks exactly like a wrong abstention and lands in the denominator: five of the location
misses above are the drag. **Fabrication risk is the number that matters most**, and it is the
extraction analog of axis (a)'s refusal-grade false positive: of the 28 genuinely-absent cells,
3 (0.107) were wrongly claimed as located. All three are the same failure: the paper NAMES a
concept it never gives a value for (a cited `ImageNet` in a financial paper's reference list, the
word `accuracy` in a regression paper that reports only MAPE, `sensitivity analyses` in PRISMA),
and the lexical extractor grounds on that token and reports a nearby unrelated number. That is
the precise error the extraction-tables skill's anchoring-plus-layer design exists to catch, and
0.107 on a weak baseline is the measurement that justifies the design rather than an assertion
that it is safe.

### What this n certifies, and what it does not

- **Nothing below 0.10 at any per-column n.** Every per-column row is n <= 21, and a perfect
  21/21 has a 95% Wilson interval reaching down only to 0.845 (implied error-rate upper bound
  0.155, above 0.10), so not one column certifies an error rate below 0.10 even at 1.000. The
  D17 gate size (>= 100 cells, >= 20 per column type) exists to make each column MEASURABLE, not
  to license a bound. This is the same caveat that binds the small per-class rows in axis (a).
- **The headline 0.916 is a baseline measurement, not a bar.** Like axis (c)'s 0.644, it is the
  number a richer layer must beat, quoted with its interval so nobody reads it as a guarantee.
- **The abstract-layer 1.000 certifies nothing about full text.** It is an easier task on a
  different surface (n = 19), reported to prove the layer is labeled, not to be quoted alone.
- **Determinism (D15).** Two consecutive `--json` runs are byte-identical (md5
  `80b6b3c83c27b92cfc1446657a025564`); deleting one snapshot and re-running reports the affected
  cells SKIPPED and exits non-zero, re-fetching nothing.

## What these n certify, and what they do not

D17's arithmetic, applied to the numbers above rather than gestured at.

Zero-error certification: 0.9^29 = 0.047 < 0.05, so certifying an error rate below 0.10 at 95%
confidence needs 0 errors in n >= 29 (exact one-sided; the two-sided Wilson bound needs n >= 35).
0.85^19 = 0.046 < 0.05, so certifying below 0.15 needs 0 misses in n >= 19 (Wilson: n >= 22).

**Certified by the numbers above:**

- **Refusal-grade FPR below 0.10, and now below 0.05.** 0 errors in 100 negatives, 95% Wilson
  [0.000, 0.037]. Zero errors in n = 100 clears D17's n >= 35 two-sided bar, so the claim below
  0.10 holds at 95% confidence, and because the upper bound is 0.037 it now clears 0.05 as well,
  which the earlier 3/99 result (upper bound 0.085) could not. This is a whole-axis rate, not a
  per-class one: see the per-class caveat below.
- **Refusal-grade FNR below 0.15, and below 0.10.** 0 misses in 50 refusal-grade positives, 95%
  Wilson [0.000, 0.071]. Zero errors in n = 50 clears both of D17's thresholds (n >= 29 and
  n >= 22).
- **Retrieval recall@10 above 0.935.** 55/55 known-item queries returned the target within the
  top 10, 95% Wilson [0.935, 1.000]. The axis is now complete at all 55 queries; the earlier
  33-query subset certified nothing.
- **Dedup false-merge rate below 0.05.** 0 in 100, 95% Wilson [0.000, 0.037].
- **Dedup false-split rate below 0.05.** 0 in 110, 95% Wilson [0.000, 0.034].
- **Faithfulness abstention correctness.** 26/26 correct abstentions on documents with no full
  text, 95% Wilson [0.871, 1.000], which certifies only that the rate is above 0.871. It does not
  certify "always", and no n we can afford would.

**NOT certified, and stated here so nobody quotes them as if they were:**

- **A per-class rate at a small per-class n.** A perfect 25/25 has a 95% Wilson interval of
  [0.867, 1.000]; the implied error-rate upper bound is 0.133, which is ABOVE 0.10, so a
  per-class n of 25 cannot certify an error rate below 0.10 even with zero errors. This binds the
  small per-class rows above: `mismatch` recall 1.000 and `unresolvable` recall 1.000 (each
  n = 25), `corrected` recall 1.000 (n = 25), `retracted` recall 1.000 (n = 31, error upper bound
  still 0.110) and `expression-of-concern` recall 1.000 (n = 20) are all real measurements and
  none of them certifies a 0.10 bound. D17 says exactly this, and the per-class floors exist to
  make each class MEASURABLE, not to certify it.
- **Retrieval recall@1 and MRR.** recall@1 is 0.818 (10 of 55 targets not returned first) and MRR
  is 0.883, both over the full 55-query set. These are point measurements, not zero-error
  certifications, and no bound is claimed from them.
- **Axis (c) accuracy.** 0.644 overall, 0.526 over answered items, on a lexical baseline. These
  are measurements of a baseline, not a bar anything should be held to.
- **Anything at all from the live canary.** Determinism is never claimed for live calls (D15).

## Gate status

The M2 exit gate is these benchmarks green at D17 sizes. Every line is now green, the runner exits
0, and every gold set is fully scored.

| Gate | Size required (D17) | Gold | Scored | Status |
|---|---|---|---|---|
| Axis (a) identity | >= 150 tuples, >= 25/class, >= 100 negatives | 150 (75/25/25/25), 100 negatives | 150, 100 negatives | GREEN |
| Axis (b) status | >= 120, >= 20/class | 121 (45/25/31/20) | 121 | GREEN |
| Axis (c) faithfulness | >= 100 pairs, >= 20/class, risk-coverage reported | 104 (26/26/26/26) | 104 | GREEN |
| Axis (d) accessibility | >= 100 DOIs | 105 | 105 | GREEN |
| Retrieval | >= 50 known-item queries | 55 | 55 | GREEN |
| Dedup | >= 200 labeled pairs | 210 | 210 | GREEN |
| Determinism (D15) | byte-identical across two runs | | | GREEN |

Every class meets its D17 floor. The axis (b) counts (45/25/31/20) reflect a ground-truth
correction: six items that had received an expression of concern and were later retracted were
relabeled to `retracted`, and one further genuine expression-of-concern paper was added so that
class stayed at its 20-per-class floor rather than dropping to 19. All four status classes score
recall and precision 1.000.

Both lines that were red in an earlier run are closed, and neither closure changed any of the
kernel's guarantees:

1. **Retrieval, formerly 22 missing snapshots.** OpenAlex's daily search budget had been exhausted
   during recording, leaving 22 of the 55 known-item queries without an OpenAlex snapshot. Those
   snapshots are now recorded and the axis scores all 55 offline.
2. **Identity, formerly 1 unscorable item.** `10.1016/s0140-6736(21)01698-6` could not be
   snapshotted because DataCite's search API returned **HTTP 400** for its gold title. Query
   sanitization (see the fixes below) closed that, so all 100 negatives are now scored.

## Fixes this benchmark drove

A benchmark that finds bugs and does not report them is decoration. Three defects surfaced here,
all three are fixed, and they are recorded so no future change reintroduces them. The first is the
most important.

1. **Query sanitization: an ordinary colon in a title made DataCite return zero hits.** DataCite's
   search is Lucene-backed, and Lucene reads a leading token followed by a colon (for example
   `Attention:`) as a FIELD NAME rather than as text, so a title beginning that way matched
   nothing. A zero-hit result is a clean negative, and a clean negative is the only outcome that
   builds toward the refusal-grade `unresolvable`, so a pure query artifact could push a real
   reference toward a refusal. Measured directly: one gold title returned 0 results with its colon
   and 84 with the colon removed. Every search now sanitizes its query before it is sent. This
   also closed the HTTP 400 that a truncated title with an unbalanced bracket used to throw, which
   is why `10.1016/s0140-6736(21)01698-6` is now scorable and the negative set is 100 rather than
   99. This was the highest-value thing the suite produced.
2. **A source may disagree about a DOI only if it actually resolved it.** A source that did not
   hold a DOI could fall back to a title search, find a lookalike, and report `doi_mismatch` as
   though it had resolved the identifier and found a conflict. Two such non-holding indexes could
   then outvote one genuine confirmation and produce a refusal-grade `mismatch` on a real
   reference. Now only a source that actually resolved the identifier may disagree about it; a
   title-search hit may still support a confirmation, and may convict an identifier only when no
   source resolved it anywhere and no source errored. This took the refusal-grade false positive
   rate from 3/100 to 0/100 with `mismatch` and `unresolvable` recall both unchanged at 1.000.
3. **Six stale axis-b labels, and a status precedence fix.** Six gold items labeled
   expression-of-concern had received an EoC and were LATER retracted, so the harvest had captured
   the first notice rather than the current status. Their labels were corrected against the papers'
   own Crossref retraction notices, and `status.py` now lets Crossref's specific update-type
   outrank OpenAlex's coarse `is_retracted` boolean. Axis (b) reads 121/121 after both changes.

One defect this benchmark found is still open, and it affects no number above:

- **PMC blocks automated fetches with an interstitial.** `https://www.ncbi.nlm.nih.gov/pmc/...`
  returns a "Checking your browser" page to httpx, which the extractor reads as a 1-segment
  full-text document. No number above depends on it (the faithfulness gold deliberately sources
  full text from arXiv HTML and PLOS, and no gold item resolves through PMC), but any future
  document that resolves through the PMC cascade step will extract a junk passage rather than an
  article. The OA cascade should treat the interstitial as a miss.
