# GRADE Certainty Worksheet

Loaded on demand during the certainty-rating step of the systematic-review workflow (M4.9). The
systematic-review skill links here rather than inlining the instrument, so its SKILL.md stays under the
500-line cap (D6). The machine-fillable skeleton is `templates/grade-worksheet.yaml`.

GRADE rates the **certainty of evidence per outcome** (not per study): how much confidence a reader can
place in the pooled estimate for one outcome across the included body of evidence. One worksheet covers
one outcome within one comparison. The completed worksheets populate the GRADE Summary of Findings table.

## No automated scoring, stated plainly

**The plugin never computes a certainty rating.** It does not add up downgrades, does not apply upgrade
rules, and does not decide High / Moderate / Low / Very low. A human applies GRADE judgement to each domain
and records the result. The kernel's jobs are mechanical only: prefill the outcome name, the study and
participant counts from the extraction table (M4.7), the links to the per-study RoB 2 worksheet hashes
(`references/rob2-worksheet.md`), and the link to the meta-analysis result (M4.10); then hash the completed
worksheet into the ledger. Every judgement below is the appraiser's.

## Starting point

Certainty starts from study design and is then moved down (or, rarely, up):

| Body of evidence | Starting certainty |
|---|---|
| Randomized trials | `High` |
| Observational studies | `Low` |

## The five downgrading domains

Each domain is rated `not serious` (no downgrade), `serious` (down one level), or `very serious` (down two
levels), with a written reason. Record the levels moved as `0`, `-1`, or `-2`. Publication bias is rated
`not detected`, `suspected` (`-1`), or `strongly suspected` (`-2`).

| Domain | The question the appraiser answers |
|---|---|
| Risk of bias | Do the RoB 2 judgements across the studies contributing to this outcome undermine confidence? Draw on the per-study worksheet judgements, weighted toward the studies carrying the most information. |
| Inconsistency | Is there unexplained heterogeneity across studies (widely differing point estimates, non-overlapping confidence intervals, high I-squared, large tau-squared)? Contradiction-detection (M4.8) feeds this domain concrete cited disagreements rather than a vibe. |
| Indirectness | Do the population, intervention, comparator, or outcome of the evidence differ from the review question (the shared qualifier axes from the eligibility profile), or is the comparison indirect? |
| Imprecision | Is the pooled confidence interval wide, does it cross a decision threshold, or is the optimal information size not met? Read this from the meta-analysis output (M4.10), never by eye. |
| Publication bias | Is there reason to suspect missing studies (asymmetric funnel plot with enough studies to read one, known unpublished trials, small-study effects, industry-only evidence)? |

## The three upgrading factors

Upgrading applies mainly to observational evidence that has **no serious downgrades**. Each recorded factor
carries a written reason and the levels moved up.

| Factor | Levels up |
|---|---|
| Large magnitude of effect | `+1` large, `+2` very large |
| Dose-response gradient | `+1` |
| Plausible residual confounding would reduce a demonstrated effect, or would produce a spurious effect where none is observed | `+1` |

## Final certainty

After the human applies the domain judgements, the outcome lands in one of:

| Certainty | Reading |
|---|---|
| `High` | Very confident the true effect lies close to the estimate |
| `Moderate` | Moderately confident; the true effect is probably close, but may be substantially different |
| `Low` | Limited confidence; the true effect may be substantially different |
| `Very low` | Very little confidence; the true effect is likely to be substantially different |

Certainty does not fall below `Very low` and does not rise above `High`. Record the final rating plus a
one-line reason that names the domains that drove it.

## Summary of Findings row

Each completed worksheet contributes one row to the GRADE Summary of Findings (SoF) table:

- outcome name and the comparison it belongs to;
- number of participants and studies contributing;
- the anticipated absolute effect (assumed risk in the comparator, corresponding risk with the
  intervention) and the relative effect (for example a risk ratio or mean difference), both **carried
  from the meta-analysis result (M4.10), never hand-typed** so `researcher compile` can bind them;
- the certainty rating and the footnoted reasons for every downgrade or upgrade.

The SoF table is rendered by the latex-tables skill and cites each row's worksheet hash from the ledger, so
a reader can trace a certainty rating back to the recorded judgement.

## How the appraiser completes a worksheet

1. Open the prefilled `templates/grade-worksheet.yaml` skeleton for this outcome. The `outcome`,
   `comparison`, `n_studies`, `n_participants`, `rob2_worksheet_hashes`, and `meta_analysis_ref` fields are
   already populated; leave them alone.
2. Set the starting certainty from the study design.
3. Rate each of the five downgrading domains with a reason, reading imprecision and inconsistency from the
   meta-analysis output rather than by eye. Complete the RoB 2 worksheets (`references/rob2-worksheet.md`)
   before this step, since the risk-of-bias domain depends on them.
4. Record any upgrading factors, which normally apply only to observational evidence with no serious
   downgrades.
5. Record the final certainty and the one-line reason.
6. Save, then hash the worksheet into the ledger (next section).

## Recording into the ledger (deterministic backend)

A completed worksheet becomes an append-only `artifact_hash` event (D19), so the SoF table can cite the
exact certainty-rating bytes that fed a conclusion. The skill computes a SHA-256 over the canonicalized
worksheet and appends the event; the timestamp is caller-supplied, so a replay is byte-identical:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core provenance append \
  '{"run_id": "<review-run-id>", "type": "artifact_hash", "ts": "<ISO-8601>",
    "payload": {"artifact_type": "grade-worksheet",
                "artifact_id": "grade:<comparison-slug>:<outcome-slug>",
                "artifact_hash": "sha256:<64-hex>",
                "outcome": "<outcome name>", "comparison": "<comparison>",
                "certainty": "<High|Moderate|Low|Very low>",
                "worksheet_path": "manuscript/appraisal/<file>.yaml",
                "completed_by": "<appraiser-id>"}}' \
  --json
```

Read back the emitted `event_id` and stored `payload.artifact_hash`; the SoF table cites those. Record the
`certainty` in the payload as a convenience label only: it is a copy of the human's judgement, never a value
the kernel derived.

**Degradation path (D3).** GRADE rating is a human judgement instrument, not a retrieval step, so there is
no MCP or web-search fallback for the rating itself. The only kernel dependency is the ledger event. If `uv`
and `core` are absent, complete the worksheet the same way, keep it under version control, and pin its
version by the git commit hash; state in the report that the certainty-rating version is tracked by commit
rather than by the ledger.

## Integrity

The refusal-grade constraints in `references/integrity-constraints.md` apply. Load-bearing here: never
present a certainty rating as the plugin's when a human did not make it, and never carry a pooled absolute or
relative effect into the SoF row by hand. Every pooled number flows from the committed meta-analysis script
(M4.10) so the compile gate can bind it; a hand-edited SoF number is exactly the C002 defect `researcher
compile` exists to catch.
