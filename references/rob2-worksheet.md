# Cochrane RoB 2 Worksheet

Loaded on demand during the critical-appraisal step of the systematic-review workflow (M4.9).
The systematic-review skill links here instead of inlining the instrument, so its SKILL.md stays
under the 500-line cap (D6). The machine-fillable skeleton is `templates/rob2-worksheet.yaml`.

RoB 2 is the Cochrane risk-of-bias tool (current version, 22 August 2019) for **randomized trials**.
This file reproduces the five domains and their signalling questions as a human-completed worksheet
and defines exactly what the plugin does and does not do with them.

## No automated scoring, stated plainly

**The plugin never computes a risk-of-bias judgement.** It does not run the RoB 2 algorithm, does
not map signalling-question responses to a domain rating, and does not roll domains up into an overall
rating. A human appraiser answers every signalling question, applies the RoB 2 judgement logic (the
Cochrane guidance document and the RoB 2 Excel tool are the reference for that logic), and records the
resulting Low / Some concerns / High judgements. The kernel's only jobs are mechanical: prefill the
study id, the outcome name, and the links to the extraction anchors, and, once the human has completed
the worksheet, hash it into the provenance ledger so the final report can prove which appraisal version
fed the conclusions. Nothing here decides for the appraiser.

## Scope and unit of assessment

- RoB 2 assesses **one result at a time**, not a whole study. A trial that reports three outcomes gets
  three worksheets, because bias in measurement or in selection of the reported result can differ
  outcome by outcome. The mechanical link back to the extraction table is per outcome for this reason.
- The base worksheet covers **individually randomized parallel-group trials**. RoB 2 has separate
  variants for cluster-randomized and crossover trials; those variants are an extension pattern for a
  later milestone, out of scope for 0.5.0, and a study of either design should be flagged for the
  appraiser rather than forced through the parallel-group questions.
- Non-randomized studies are **out of scope for RoB 2**. ROBINS-I is the Cochrane tool for those and is
  parked on the deferred backlog; do not appraise an observational study on this worksheet.

## Response vocabulary

Every signalling question is answered with one of:

| Code | Meaning |
|---|---|
| `Y` | Yes |
| `PY` | Probably yes |
| `PN` | Probably no |
| `N` | No |
| `NI` | No information |
| `NA` | Not applicable (a conditional question the routing skipped) |

Signalling questions are phrased so that the answer that raises a bias concern is not always the same
word: read each one on its own terms. The bracketed conditions below are the RoB 2 routing: answer a
conditional question only when its condition holds, and mark it `NA` otherwise.

Each domain then carries a **domain-level judgement**, and the worksheet a single **overall judgement**,
each one of:

| Judgement | Meaning |
|---|---|
| `Low` | Low risk of bias |
| `Some concerns` | Some concerns |
| `High` | High risk of bias |

The appraiser also records a free-text **rationale** per domain (the reasoning behind the judgement, with
the extraction anchors or quotations that support it) and may record a **predicted direction** of bias.

## Domain 1: bias arising from the randomization process

- **1.1** Was the allocation sequence random?
- **1.2** Was the allocation sequence concealed until participants were enrolled and assigned to
  interventions?
- **1.3** Did baseline differences between intervention groups suggest a problem with the randomization
  process?

## Domain 2: bias due to deviations from intended interventions

RoB 2 splits this domain by the effect of interest. Record which one the review targets in the
worksheet's `deviations_variant` field, then answer the matching set. The intention-to-treat effect
(assignment) is the usual default for a review of effectiveness; the per-protocol effect (adherence)
answers a different question and uses a different question set.

### Variant A: effect of assignment to intervention (intention-to-treat)

- **2.1** Were participants aware of their assigned intervention during the trial?
- **2.2** Were carers and people delivering the interventions aware of participants' assigned
  intervention during the trial?
- **2.3** [if `Y`/`PY`/`NI` to 2.1 or 2.2] Were there deviations from the intended intervention that arose
  because of the trial context?
- **2.4** [if `Y`/`PY` to 2.3] Were these deviations likely to have affected the outcome?
- **2.5** [if `Y`/`PY`/`NI` to 2.4] Were these deviations from intended intervention balanced between
  groups?
- **2.6** Was an appropriate analysis used to estimate the effect of assignment to intervention?
- **2.7** [if `N`/`PN`/`NI` to 2.6] Was there potential for a substantial impact (on the result) of the
  failure to analyse participants in the group to which they were randomized?

### Variant B: effect of adhering to intervention (per-protocol)

- **2.1** Were participants aware of their assigned intervention during the trial?
- **2.2** Were carers and people delivering the interventions aware of participants' assigned
  intervention during the trial?
- **2.3** [if `Y`/`PY`/`NI` to 2.1 or 2.2] Were important non-protocol interventions balanced across
  intervention groups?
- **2.4** Were there failures in implementing the intervention that could have affected the outcome?
- **2.5** Was there non-adherence to the assigned intervention regimen that could have affected
  participants' outcomes?
- **2.6** [if `N`/`PN` to 2.3, or `Y`/`PY`/`NI` to 2.4 or 2.5] Was an appropriate analysis used to
  estimate the effect of adhering to the intervention?

## Domain 3: bias due to missing outcome data

- **3.1** Were data for this outcome available for all, or nearly all, participants randomized?
- **3.2** [if `N`/`PN`/`NI` to 3.1] Is there evidence that the result was not biased by missing outcome
  data?
- **3.3** [if `N`/`PN` to 3.2] Could missingness in the outcome depend on its true value?
- **3.4** [if `Y`/`PY`/`NI` to 3.3] Is it likely that missingness in the outcome depended on its true
  value?

## Domain 4: bias in measurement of the outcome

- **4.1** Was the method of measuring the outcome inappropriate?
- **4.2** Could measurement or ascertainment of the outcome have differed between intervention groups?
- **4.3** [if `N`/`PN`/`NI` to 4.1 and 4.2] Were outcome assessors aware of the intervention received by
  study participants?
- **4.4** [if `Y`/`PY`/`NI` to 4.3] Could assessment of the outcome have been influenced by knowledge of
  intervention received?
- **4.5** [if `Y`/`PY`/`NI` to 4.4] Is it likely that assessment of the outcome was influenced by knowledge
  of intervention received?

## Domain 5: bias in selection of the reported result

- **5.1** Were the data that produced this result analysed in accordance with a pre-specified analysis
  plan that was finalized before unblinded outcome data were available for analysis?
- **5.2** Is the numerical result being assessed likely to have been selected, on the basis of the results,
  from multiple eligible outcome measurements (e.g. scales, definitions, time points) within the outcome
  domain?
- **5.3** Is the numerical result being assessed likely to have been selected, on the basis of the results,
  from multiple eligible analyses of the data?

## How the appraiser completes a worksheet

1. Open the prefilled `templates/rob2-worksheet.yaml` skeleton the skill produced for this study and
   outcome. The `study_id`, `outcome`, `result`, and `extraction_anchor` fields are already populated
   from the extraction table (M4.7); leave them alone.
2. Read the trial report against the source anchors and answer every signalling question with one code
   from the response vocabulary. Answer conditional questions only when their routing condition holds;
   otherwise leave them `NA`.
3. Write the per-domain `rationale`, quoting or anchoring the evidence for each answer.
4. Apply the RoB 2 judgement logic yourself and record the `Low` / `Some concerns` / `High` judgement per
   domain and the single overall judgement. The plugin does not derive these.
5. Save the completed worksheet, then hash it into the ledger (next section). The GRADE risk-of-bias
   domain (`references/grade-worksheet.md`) draws on these per-study judgements, so complete appraisal
   before certainty rating.

The completed worksheet renders into the manuscript's appraisal table (a per-study, per-domain traffic-light
row plus the overall column) via the latex-tables skill; the derived table cites the worksheet hash so a
reader can trace the row back to the recorded appraisal.

## Recording into the ledger (deterministic backend)

A completed worksheet is evidence, so it becomes an append-only `artifact_hash` event (D19). The content
hash binds the exact appraisal bytes to the run; the GRADE summary-of-findings table and the appraisal
table cite that hash, so a later reader can prove which appraisal version fed the conclusions.

The skill computes a SHA-256 over the canonicalized completed worksheet and appends the event through the
kernel. The timestamp is caller-supplied (D19), so a replay is byte-identical:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core provenance append \
  '{"run_id": "<review-run-id>", "type": "artifact_hash", "ts": "<ISO-8601>",
    "payload": {"artifact_type": "rob2-worksheet",
                "artifact_id": "rob2:<study-id>:<outcome-slug>",
                "artifact_hash": "sha256:<64-hex>",
                "study_id": "<study-id>", "outcome": "<outcome name>",
                "worksheet_path": "manuscript/appraisal/<file>.yaml",
                "deviations_variant": "assignment", "completed_by": "<appraiser-id>"}}' \
  --json
```

Read back the emitted event's `event_id` and the stored `payload.artifact_hash`; those are what the
appraisal table and the GRADE worksheet cite. `provenance prisma` counts `artifact_hash` events toward the
appraisal stage, so this is also what lets the derived report state how many included studies were appraised.

**Degradation path (D3).** RoB 2 appraisal is a human judgement instrument, not a retrieval step, so there
is no MCP or web-search fallback for the appraisal itself: the questions and judgements are the appraiser's
regardless of tooling. The only thing the kernel provides is the ledger event. If `uv` and `core` are
absent, complete the worksheet exactly the same way, keep it under version control, and pin its version by
the git commit hash instead of an `artifact_hash` event. State in the report that the appraisal version is
tracked by commit rather than by the ledger, so the provenance claim stays honest about which store holds it.

## Integrity

The refusal-grade constraints in `references/integrity-constraints.md` apply. Two are load-bearing here:
never invent a signalling-question answer the source does not support (an unanswerable question is `NI`,
never a guessed `Y` or `N`), and never present a risk-of-bias judgement as the plugin's when a human did
not make it. `NI` on many questions is a real and reportable state of the evidence, not a gap to paper over.
