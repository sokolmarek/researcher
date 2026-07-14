# Threshold calibration (M2.6)

This file is a **gate, not documentation**. The M2 plan states that calibration MUST complete
before any refusal-grade consumer ships, so the M3 citation audit, the compile gate, and the
commit hook may not act on a verdict until the thresholds below are the ones `verify.py`
actually uses, and the measured refusal-grade false-positive rate on the gold subset is the one
recorded here.

The committed thresholds ARE the ones in `researcher_core/verify.py::Thresholds`, and the report
emits them (`thresholds` block of `verification-report.schema.json`), so a verdict can never be
read without the rule that produced it.

## Reproducing every number in this file

```
# axis (a): offline, replays core/tests/snapshots/verify-gold/
uv run --project core python core/tests/snapshots/verify-gold/calibrate.py

# axis (b): the same, plus all 120 DOIs of evals/gold/status.yaml against the live APIs
uv run --project core python core/tests/snapshots/verify-gold/calibrate.py --status-live
```

The offline arm is deterministic (D15): identical snapshots, configuration, and parser version
give byte-identical output. The live arm is not, and is not claimed to be.

## What "refusal-grade" means, and why this is the number that matters

Only `unresolvable` and `mismatch` are refusal-grade. Those are the two verdicts that let a
consumer tell a researcher that a citation appears fabricated or wrong. `inconclusive` is NEVER
refusal-grade, and neither is `verified`.

**Refusal-grade false positive:** a reference that is real and correctly cited (gold verdict
`verified` or `inconclusive`) which the kernel calls `unresolvable` or `mismatch`. This is the
failure that accuses an honest researcher, and it is the rate this calibration exists to drive
to zero.

**Refusal-grade false negative:** a fabricated or wrong reference (gold `unresolvable` or
`mismatch`) that the kernel does not flag. This is a missed catch. It is a worse outcome for the
literature and a better outcome for the individual user than a false positive, and the
precedence in `decide()` deliberately trades in that direction: when the evidence is thin or
dirty, the verdict falls to `inconclusive` rather than to a refusal.

## Committed thresholds

| Knob | Value | Why |
|---|---|---|
| `title_similarity` | **0.70** | D9's stated bar. Applied to rapidfuzz `token_sort_ratio` over title fingerprints (lowercased, depunctuated, whitespace-collapsed). |
| `year_tolerance` | **1** | D9. Publication year within plus or minus one. |
| `require_first_author_surname` | **true** | D9, and measured below to be the check that carries identity when title similarity alone fails. |
| `min_confirmations` | **2** | D9. Two independent indexes must agree before a reference is `verified`. |
| `strong_title_similarity` | **0.90** | Calibrated. The bar a title must clear before ANY relaxation applies. |
| `preprint_year_tolerance` | **3** | Calibrated. The year window when, and only when, the resolved record is a preprint and title plus first author already match strongly. |
| `truncation_min_chars` | **20** | Calibrated. Minimum length of a truncated title before the prefix rule may fire. |

The last three only ever RELAX a check, and only when identity is already established by title
and author. None of them can turn a non-matching record into a confirmation. Both directions were
measured; see the sweep.

## Axis (a): the gold subset

`core/tests/snapshots/verify-gold/` holds 11 stratified cases, every one of them backed by
snapshots recorded from the live OpenAlex, Crossref, DataCite, and Semantic Scholar APIs
(`record.py`). All four verdicts are covered, and every edge case the M2 plan names is present.

| Case | Gold verdict | What it is |
|---|---|---|
| `clean_two_index` | verified | A well-indexed paper. Two confirmations, one clean negative from an index that does not mint its DOI. |
| `title_truncated` | verified | Title cut mid-sentence by a citation manager. |
| `author_initials_only` | verified | Bib carries initials, indexes carry full given names. |
| `preprint_later_published` | verified | Mask R-CNN: the arXiv preprint DOI (2017) cited with the journal version's year (2020). Same work, two DOIs, three years apart. |
| `lone_disagreeing_index` | verified | Mask R-CNN in TPAMI: Crossref and Semantic Scholar date it 2020, OpenAlex dates it 2018. One index disagrees, two confirm. |
| `title_only_reference` | verified | A reference with no identifier at all, resolved by title search. |
| `valid_doi_wrong_metadata` | mismatch | A real DOI carrying another paper's title, year, and author. |
| `wrong_doi_real_paper` | mismatch | A real paper with a DOI that resolves nowhere. |
| `single_index_only` | inconclusive | A ScienceDB dataset only DataCite holds. One confirmation. |
| `invented_reference` | unresolvable | The seeded fake from the citation-audit example (D8). Every source returns a clean negative. |
| `invented_reference_with_source_error` | inconclusive | The same fake, with OpenAlex timing out. |

### Measured outcomes at the committed thresholds

```
accuracy               11/11
refusal-grade FP       0/8   (95% Wilson 0.000-0.324)
refusal-grade FN       0/3
```

Zero refusal-grade false positives on eight honest references, and zero missed catches on three
bad ones. The Wilson interval is wide because n is 8: this subset is a CALIBRATION set, not a
certification set. D17's certification arithmetic (0 errors in n >= 29 to certify FPR < 0.10 at
95% confidence) runs against the 150-tuple `evals/gold/identity.yaml` set in M2.12, not here. What
this file certifies is that the thresholds are the ones in the code and that they get every
stratum right.

### Threshold sweep: what each knob is worth

Each row turns exactly one knob off and re-runs the same 11 cases from the same snapshots.

| Setting | Accuracy | Refusal-grade FP | What breaks |
|---|---|---|---|
| **committed** | **11/11** | **0/8** | nothing |
| no preprint year relaxation | 10/11 | **1/8** (Wilson 0.022-0.471) | `preprint_later_published` becomes **`mismatch`**: refusal-grade, on an honest citation |
| no truncation rule | 11/11 | 0/8 | no verdict changes on this subset (see note) |
| title bar raised to 0.90 | 11/11 | 0/8 | no verdict changes on this subset (see note) |
| first-author surname check off | 10/11 | 0/8 | `invented_reference` degrades from `unresolvable` to `mismatch`: still flagged, but for the wrong reason |
| `min_confirmations` = 1 | 10/11 | 0/8 | `single_index_only` becomes **`verified`** on the word of one index |

**The preprint relaxation earns its keep, and it is the reason it exists.** Without it, Mask R-CNN
cited by its arXiv DOI with its journal year is a three-year discrepancy, OpenAlex and DataCite
BOTH resolve the DOI and BOTH disagree, and D9 rule 2 fires: `mismatch`, refusal-grade. A real,
honest, correctly-attributed reference would be reported to the author as wrong. That is the single
worst failure this system can produce, and citing a preprint by its DOI with its published year is
ordinary scholarship, not an error. The relaxation is narrow (it widens the YEAR window only, only
when the resolved record is a preprint, and only when title similarity is at least 0.90 with the
first-author surname overlapping) and it cannot rescue a wrong title or a wrong author.

**The surname check is what makes the title-search fallback safe.** Measured on this subset:

```
title_similarity("Contrastive masked autoencoders for single-lead ECG anomaly detection",
                 "Masked Contrastive Learning for Anomaly Detection")   =  0.746
```

The FABRICATED title scores **0.746** against a real and completely unrelated paper: above the 0.70
bar. Title similarity alone would confirm a fabricated reference against the wrong work. The claimed
year (2021) is also within tolerance of that paper's. It is the first-author surname check, and only
that, which rejects the pair. With the surname check off, `invented_reference` stops being
`unresolvable` (all sources cleanly negative) and becomes `mismatch` (a source "resolved" it by
title). Still refusal-grade, so the FP rate does not move, but the verdict is wrong, and on a real
reference with a coincidentally similar title the same mechanism would manufacture a false
`mismatch`. `require_first_author_surname` stays true.

**The title bar stays at 0.70, and the direction of the risk is why.** A 0.90 bar also scores 11/11
here, because the truncation rule lifts the truncated title from 0.752 to 1.0. But a stricter title
bar does not make refusals safer, it makes them MORE likely: a title that fails the bar on a
resolving source produces a `mismatch`, which is refusal-grade. The conservative direction for a
refusal-grade check is the LOWER bar, backed by the year and surname checks, which is exactly what
D9 specifies. It stays at 0.70.

**The truncation rule changes no verdict on this subset**, and is committed anyway. It is honest to
say so: at a 0.70 bar the truncated title already passes on `token_sort_ratio` alone (0.752). What
the rule buys is headroom (a harsher truncation, or a title bar someone later raises) and an
explicitly prefix-anchored notion of truncation, rather than a generic `partial_ratio` that would
also lift unrelated titles sharing a phrase. It is guarded (20 characters minimum, and the shorter
title must be at least 40% of the longer) so it cannot fire on a fragment.

**Two confirmations, not one.** With `min_confirmations` at 1, the ScienceDB dataset that only
DataCite holds is reported `verified` on the word of a single index. It is a real dataset, so this
is not a refusal-grade failure, but `verified` is an overclaim: the D9 gate exists so that
"verified" means two independent indexes agree. It stays at 2, and the legitimate single-index work
lands in `inconclusive`, which is never refusal-grade and never blocks anyone.

### The failure this calibration is really about

`invented_reference_with_source_error` is the same fabricated entry as `invented_reference`, with
OpenAlex timing out. The verdict MUST move from `unresolvable` (refusal-grade) to `inconclusive`
(never refusal-grade), because a clean negative can no longer be asserted. It does, at every
threshold setting in the sweep: the precedence in `decide()` makes `unresolvable` unreachable
whenever any source errored, so no threshold choice can reintroduce the failure. A rate-limited
index must never accuse a researcher of fabricating a real citation.

## Axis (b): publication status, all 120 gold DOIs

Run live against Crossref and OpenAlex over the full `evals/gold/status.yaml` (25 retracted /
25 corrected / 25 expression-of-concern / 45 current).

```
gold \ predicted            current   corrected   retracted   expression-of-concern
current                          45           0           0                       0
corrected                         0          25           0                       0
retracted                         0           0          25                       0
expression-of-concern             0           0           6                      19

accuracy   114/120 (95% Wilson 0.895-0.977)
unchecked  0
conflicts  0
```

**All six misses are the same case, and the gold labels are the stale side of it.** Each of the six
is a paper that received an expression of concern and was then RETRACTED, later:

| DOI | EoC | Retraction | OpenAlex `is_retracted` |
|---|---|---|---|
| 10.1042/bsr20160523 | 2020-07-02 | 2021-05-14 | true |
| 10.1042/bsr20181289 | 2021-04-19 | 2023-03-02 | true |
| 10.1161/circresaha.111.250423 | 2020-09-25 | 2021-09-03 | true |
| 10.2119/molmed.2014.00183 | 2020-02-03 | 2020-12-30 | true |
| 10.1371/journal.pgen.1004792 | 2021-03-19 | 2021-11-04 | true |
| 10.1155/2022/3802603 | 2022-12-01 | 2022-12-19 | true |

In every one, the retraction post-dates the expression of concern, and OpenAlex independently
reports `is_retracted: true`. The current status of these six works is `retracted`, and
"strongest notice wins" returns it. The gold set was harvested by filtering Crossref on
`update-type:expression_of_concern`, which matches any work that HAS an expression of concern,
including one later retracted. **Against the corrected labels the classifier is 120/120 (95%
Wilson 0.969-1.000).** The six labels in `evals/gold/status.yaml` should be moved to the
`retracted` class by that file's owner; this calibration does not edit the gold set it is
measured against.

Zero entries were unchecked and zero conflicts arose across all 120, so no verdict in that run
rests on an absence of evidence.

### The trap axis (b) is built around

A retraction NOTICE is a current document. Crossref deposits the notice/article pairing in BOTH
directions with the SAME type, so the Lancet Surgisphere retraction notice
(`10.1016/s0140-6736(20)31324-6`) carries `update-to: retraction` AND `updated-by: retraction`,
both pointing at the paper it retracts, and OpenAlex sets `is_retracted: true` on the notice as
well. Every one of those signals, read naively, says "retracted". `status.py` classifies it
`current`, reports OpenAlex's flag as a `conflict` rather than resolving it away, and only drops
the update entries that mirror the notice's own pairing. That last precision matters: the Lancet
Neurology expression-of-concern notice `10.1016/s1474-4422(22)00030-8` was itself later flagged by
a separate expression of concern from a third DOI, and a rule that discarded a notice document's
whole update graph would lose a real editorial notice. Both cases are in the snapshot-backed test
set (`status-cases.json`).

## Protocol version

These rules are `IDENTITY_PROTOCOL_VERSION = "1.0"` (axis a) and `STATUS_PROTOCOL_VERSION = "1.0"`
(axis b), emitted on every report. Any change to a threshold or to the precedence bumps them,
because a stored verdict is only interpretable against the rulebook that produced it, and this
file must be re-measured before the bump ships.
