"""Axis (a) reference-identity tests (D9).

Everything here runs OFFLINE. The gold cases replay the snapshots in
``core/tests/snapshots/verify-gold/``, recorded from the live OpenAlex, Crossref, DataCite,
and Semantic Scholar APIs by ``verify-gold/record.py``, so every verdict asserted below was
produced from a real API payload rather than a hand-written fake. The one thing that CANNOT
be snapshotted is an outage, so the source-error case injects a :class:`SourceError` over the
same recorded responses.

The assertion this file exists for: ``inconclusive`` is never refusal-grade, and
``unresolvable`` is unreachable when any source errored. Everything else is detail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from rapidfuzz import fuzz

from researcher_core.connectors import create_connector
from researcher_core.connectors.base import BaseConnector, SourceError, SourceErrorKind
from researcher_core.model import CSLName, CSLRecord, canonical_json, title_fingerprint
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore
from researcher_core.verify import (
    BY_IDENTIFIER,
    BY_TITLE_SEARCH,
    CONFIRMED,
    DEFAULT_THRESHOLDS,
    INCONCLUSIVE,
    MISMATCH,
    NEGATIVE,
    SOURCE_ERROR,
    UNRESOLVABLE,
    VERIFIED,
    ReferenceClaim,
    SourceOutcome,
    Thresholds,
    assess_match,
    decide,
    is_refusal_grade,
    title_similarity,
    verify_claims,
)

GOLD_ROOT = Path(__file__).resolve().parent / "snapshots" / "verify-gold"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "verification-report.schema.json"

CASES: list[dict[str, Any]] = json.loads((GOLD_ROOT / "cases.json").read_text(encoding="utf-8"))[
    "cases"
]
CASES_BY_NAME = {case["name"]: case for case in CASES}


def gold_session() -> SnapshotSession:
    """A replay session over the gold store. Never reaches the network."""
    return SnapshotSession(SnapshotStore(GOLD_ROOT), SnapshotMode.REPLAY)


def gold_connectors(case: dict[str, Any]) -> list[BaseConnector]:
    session = gold_session()
    connectors = [create_connector(name, snapshots=session) for name in case["sources"]]
    injected = case.get("inject_source_error")
    if injected:
        for connector in connectors:
            if connector.name == injected:
                _make_it_fail(connector)
    return connectors


def _make_it_fail(
    connector: BaseConnector, kind: SourceErrorKind = SourceErrorKind.TIMEOUT
) -> None:
    """Turn a connector into a downed index. The one thing a snapshot cannot record."""

    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise SourceError(
            connector.name,
            f"Request to {connector.name} timed out after 30.0s.",
            kind=kind,
            endpoint="works",
        )

    connector.resolve_doi = boom  # type: ignore[method-assign]
    connector.get_by_id = boom  # type: ignore[method-assign]
    connector.search = boom  # type: ignore[method-assign]
    connector.get_oa_pdf = boom  # type: ignore[method-assign]


def run_case(case: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Verify one gold case offline and return its report entry."""
    claim = ReferenceClaim.from_mapping(case["claim"])
    connectors = gold_connectors(case)
    report = _verify_with(connectors, [claim], **kwargs)
    return report["entries"][0]


def _verify_with(
    connectors: list[BaseConnector], claims: list[ReferenceClaim], **kwargs: Any
) -> dict[str, Any]:
    import asyncio

    from researcher_core.verify import verify_claims_async

    async def go() -> dict[str, Any]:
        try:
            return await verify_claims_async(claims, connectors, **kwargs)
        finally:
            for connector in connectors:
                await connector.aclose()

    return asyncio.run(go())


def outcome(source: str, kind: str, **kwargs: Any) -> SourceOutcome:
    return SourceOutcome(source=source, outcome=kind, **kwargs)


def record(
    title: str = "Sharing Detailed Research Data Is Associated with Increased Citation Rate",
    year: int | None = 2007,
    surname: str = "Piwowar",
    doi: str = "10.1371/journal.pone.0000308",
    **kwargs: Any,
) -> CSLRecord:
    from researcher_core.model import CSLDate

    return CSLRecord(
        title=title,
        author=[CSLName(family=surname, given="Heather A.")] if surname else [],
        issued=CSLDate.from_year(year),
        DOI=doi,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# The D9 precedence, in isolation
# ---------------------------------------------------------------------------


def test_two_confirmations_verify() -> None:
    decision = decide([outcome("openalex", CONFIRMED), outcome("crossref", CONFIRMED)])
    assert decision.verdict == VERIFIED
    assert decision.refusal_grade is False


def test_two_confirmations_outrank_a_lone_disagreeing_source() -> None:
    """D9 rule 1. A lone bad index must never produce a refusal-grade verdict."""
    decision = decide(
        [
            outcome("openalex", CONFIRMED),
            outcome("crossref", CONFIRMED),
            outcome(
                "datacite",
                NEGATIVE,
                resolved=True,
                matched_by=BY_IDENTIFIER,
                mismatch_reasons=("year",),
                matched_record=record(year=2019),
            ),
        ]
    )
    assert decision.verdict == VERIFIED
    assert decision.disagreements == ("datacite",)  # logged, not acted on
    assert "outranked" in decision.reason


def test_two_confirmations_outrank_an_erroring_source() -> None:
    decision = decide(
        [
            outcome("openalex", CONFIRMED),
            outcome("crossref", CONFIRMED),
            outcome("datacite", SOURCE_ERROR, error={"type": "timeout", "message": "timed out"}),
        ]
    )
    assert decision.verdict == VERIFIED
    assert decision.refusal_grade is False


def test_two_resolving_disagreements_are_a_mismatch() -> None:
    decision = decide(
        [
            outcome(
                "openalex",
                NEGATIVE,
                resolved=True,
                matched_by=BY_IDENTIFIER,
                mismatch_reasons=("title_similarity",),
            ),
            outcome(
                "crossref",
                NEGATIVE,
                resolved=True,
                matched_by=BY_IDENTIFIER,
                mismatch_reasons=("title_similarity",),
            ),
        ]
    )
    assert decision.verdict == MISMATCH
    assert decision.refusal_grade is True


def test_one_clean_disagreement_with_no_confirmation_is_a_mismatch() -> None:
    decision = decide(
        [
            outcome(
                "openalex",
                NEGATIVE,
                resolved=True,
                matched_by=BY_IDENTIFIER,
                mismatch_reasons=("year",),
            ),
            outcome("crossref", NEGATIVE, resolved=False),
        ]
    )
    assert decision.verdict == MISMATCH


def test_one_disagreement_alongside_an_error_is_not_a_mismatch() -> None:
    """D9 rule 2 requires the single-disagreement case to be clean. An error makes it dirty."""
    decision = decide(
        [
            outcome(
                "openalex",
                NEGATIVE,
                resolved=True,
                matched_by=BY_IDENTIFIER,
                mismatch_reasons=("year",),
            ),
            outcome("crossref", SOURCE_ERROR, error={"type": "timeout", "message": "timed out"}),
        ]
    )
    assert decision.verdict == INCONCLUSIVE
    assert decision.refusal_grade is False


def test_one_disagreement_alongside_a_confirmation_is_not_a_mismatch() -> None:
    decision = decide(
        [
            outcome("openalex", CONFIRMED),
            outcome(
                "crossref",
                NEGATIVE,
                resolved=True,
                matched_by=BY_IDENTIFIER,
                mismatch_reasons=("year",),
            ),
        ]
    )
    assert decision.verdict == INCONCLUSIVE


def test_all_clean_negatives_are_unresolvable() -> None:
    decision = decide(
        [
            outcome("openalex", NEGATIVE, resolved=False),
            outcome("crossref", NEGATIVE, resolved=False),
            outcome("datacite", NEGATIVE, resolved=False),
        ]
    )
    assert decision.verdict == UNRESOLVABLE
    assert decision.refusal_grade is True


@pytest.mark.parametrize(
    "kind",
    [
        SourceErrorKind.TIMEOUT,
        SourceErrorKind.RATE_LIMIT,
        SourceErrorKind.SERVER_ERROR,
        SourceErrorKind.NETWORK,
    ],
)
def test_a_single_source_error_makes_unresolvable_unreachable(kind: SourceErrorKind) -> None:
    """THE line. A downed index must never be counted as evidence of fabrication."""
    decision = decide(
        [
            outcome("openalex", NEGATIVE, resolved=False),
            outcome("crossref", NEGATIVE, resolved=False),
            outcome("datacite", SOURCE_ERROR, error={"type": kind.value, "message": "down"}),
        ]
    )
    assert decision.verdict == INCONCLUSIVE
    assert decision.refusal_grade is False
    assert "clean negative cannot be asserted" in decision.reason


def test_a_single_confirmation_is_inconclusive_not_verified() -> None:
    """A legitimate single-index paper. Thin evidence, never a refusal."""
    decision = decide(
        [outcome("openalex", CONFIRMED), outcome("crossref", NEGATIVE, resolved=False)]
    )
    assert decision.verdict == INCONCLUSIVE
    assert decision.refusal_grade is False


def test_no_sources_queried_is_inconclusive_not_unresolvable() -> None:
    decision = decide([])
    assert decision.verdict == INCONCLUSIVE


def test_only_two_verdicts_are_refusal_grade() -> None:
    assert is_refusal_grade(UNRESOLVABLE)
    assert is_refusal_grade(MISMATCH)
    assert not is_refusal_grade(INCONCLUSIVE)
    assert not is_refusal_grade(VERIFIED)


def test_min_confirmations_is_configurable_but_defaults_to_two() -> None:
    assert DEFAULT_THRESHOLDS.min_confirmations == 2
    single = decide([outcome("openalex", CONFIRMED)], Thresholds(min_confirmations=1))
    assert single.verdict == VERIFIED


# ---------------------------------------------------------------------------
# Matching and thresholds
# ---------------------------------------------------------------------------


def test_title_similarity_ignores_case_punctuation_and_word_order() -> None:
    assert title_similarity("Deep Learning: A Review", "deep learning - a review") == 1.0


def test_title_similarity_survives_truncation() -> None:
    full = "Sharing Detailed Research Data Is Associated with Increased Citation Rate"
    truncated = "Sharing Detailed Research Data Is Associated"
    assert title_similarity(truncated, full) == 1.0


def test_title_similarity_alone_cannot_establish_identity() -> None:
    """The measured reason the surname check is mandatory (see CALIBRATION.md).

    The fabricated title from the gold set scores 0.746 against a REAL and completely
    unrelated paper, above the 0.70 title bar. Title similarity alone would confirm a
    fabricated reference against the wrong work. It is the conjunction with the first-author
    surname (and the year) that stops it, which is why require_first_author_surname is True.
    """
    claimed = "Contrastive masked autoencoders for single-lead ECG anomaly detection"
    other = "Masked Contrastive Learning for Anomaly Detection"
    score = title_similarity(claimed, other)
    assert score is not None and score > DEFAULT_THRESHOLDS.title_similarity

    claim = ReferenceClaim(title=claimed, year=2021, authors=["Kessler, Marta"])
    assessment = assess_match(claim, record(title=other, year=2022, surname="Cho"))
    assert not assessment.matched
    assert "first_author_surname" in assessment.reasons


def test_title_similarity_is_none_without_a_title() -> None:
    assert title_similarity("", "anything") is None


def test_a_missing_year_is_not_a_disagreement() -> None:
    """Absence of a field in the bib entry is not evidence against the reference."""
    claim = ReferenceClaim(title="Sharing Detailed Research Data", authors=["Piwowar, H."])
    assessment = assess_match(claim, record())
    assert assessment.year_delta is None
    assert "year" not in assessment.reasons


def test_year_outside_tolerance_disagrees() -> None:
    claim = ReferenceClaim(
        title="Sharing Detailed Research Data Is Associated with Increased Citation Rate",
        year=2001,
        authors=["Piwowar, Heather"],
    )
    assessment = assess_match(claim, record(year=2007))
    assert assessment.reasons == ("year",)
    assert assessment.year_delta == 6
    # A wrong year is not a wrong work: identity is intact, only the date disagrees.
    assert assessment.identity_broken is False


def test_year_within_tolerance_matches() -> None:
    claim = ReferenceClaim(
        title="Sharing Detailed Research Data Is Associated with Increased Citation Rate",
        year=2006,
        authors=["Piwowar, Heather"],
    )
    assert assess_match(claim, record(year=2007)).matched


def test_surname_overlap_tolerates_initials_and_ordering() -> None:
    claim = ReferenceClaim(
        title="Sharing Detailed Research Data Is Associated with Increased Citation Rate",
        year=2007,
        authors=["Fridsma, D. B.", "Piwowar, H. A."],
    )
    assert assess_match(claim, record()).matched


def test_a_different_first_author_breaks_identity() -> None:
    claim = ReferenceClaim(
        title="Sharing Detailed Research Data Is Associated with Increased Citation Rate",
        year=2007,
        authors=["Vaswani, Ashish"],
    )
    assessment = assess_match(claim, record())
    assert "first_author_surname" in assessment.reasons
    assert assessment.identity_broken is True


def test_the_preprint_year_relaxation_needs_a_strong_title_and_author_match() -> None:
    """It only ever relaxes the year, and only when identity is already established."""
    preprint = record(
        title="Mask R-CNN", year=2017, surname="He", doi="10.48550/arxiv.1703.06870"
    )
    same_work = ReferenceClaim(title="Mask R-CNN", year=2020, authors=["He, Kaiming"])
    assert assess_match(same_work, preprint).matched
    assert assess_match(same_work, preprint).year_relaxed

    other_work = ReferenceClaim(title="Attention Is All You Need", year=2020, authors=["He, K."])
    assessment = assess_match(other_work, preprint)
    assert not assessment.matched
    assert "title_similarity" in assessment.reasons  # relaxation cannot rescue a wrong title


def test_the_year_relaxation_does_not_apply_to_a_journal_article() -> None:
    journal = record(year=2007)
    claim = ReferenceClaim(
        title="Sharing Detailed Research Data Is Associated with Increased Citation Rate",
        year=2010,
        authors=["Piwowar, H."],
    )
    assert not assess_match(claim, journal).matched


# ---------------------------------------------------------------------------
# The gold set, replayed offline
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_gold_case_produces_its_expected_verdict(case: dict[str, Any]) -> None:
    entry = run_case(case)
    assert entry["verdict"] == case["expected"], entry["reason"]
    assert entry["refusal_grade"] is case["expected_refusal_grade"]
    if "expected_disagreements" in case:
        assert entry["disagreements"] == case["expected_disagreements"]


def test_gold_single_index_paper_is_inconclusive_and_never_unresolvable() -> None:
    """A real dataset only DataCite holds. Calling it fabricated would be a false accusation."""
    entry = run_case(CASES_BY_NAME["single_index_only"])
    assert entry["verdict"] == INCONCLUSIVE
    assert entry["refusal_grade"] is False
    assert entry["tally"] == {"confirmed": 1, "negative": 2, "source_error": 0}


def test_gold_invented_reference_is_unresolvable_on_clean_negatives() -> None:
    entry = run_case(CASES_BY_NAME["invented_reference"])
    assert entry["verdict"] == UNRESOLVABLE
    assert entry["refusal_grade"] is True
    assert entry["tally"] == {"confirmed": 0, "negative": 3, "source_error": 0}
    assert all(o["resolved"] is False for o in entry["source_outcomes"])


def test_gold_invented_reference_degrades_to_inconclusive_when_a_source_errors() -> None:
    """Same fabricated entry, one index down. The verdict MUST NOT stay refusal-grade."""
    entry = run_case(CASES_BY_NAME["invented_reference_with_source_error"])
    assert entry["verdict"] == INCONCLUSIVE
    assert entry["refusal_grade"] is False
    assert entry["tally"] == {"confirmed": 0, "negative": 2, "source_error": 1}
    errored = next(o for o in entry["source_outcomes"] if o["outcome"] == SOURCE_ERROR)
    assert errored["source"] == "openalex"
    assert errored["error"]["type"] == "timeout"


def test_gold_preprint_citation_is_verified_not_flagged_as_wrong() -> None:
    entry = run_case(CASES_BY_NAME["preprint_later_published"])
    assert entry["verdict"] == VERIFIED
    deltas = [o["year_delta"] for o in entry["source_outcomes"] if o["year_delta"] is not None]
    assert deltas and all(abs(d) > DEFAULT_THRESHOLDS.year_tolerance for d in deltas)


def test_gold_lone_disagreeing_index_is_logged_and_outranked() -> None:
    entry = run_case(CASES_BY_NAME["lone_disagreeing_index"])
    assert entry["verdict"] == VERIFIED
    assert entry["disagreements"] == ["openalex"]
    disagreeing = next(o for o in entry["source_outcomes"] if o["source"] == "openalex")
    assert disagreeing["outcome"] == NEGATIVE
    assert disagreeing["resolved"] is True
    assert disagreeing["mismatch_reasons"] == ["year"]


def test_gold_wrong_doi_on_a_real_paper_is_a_mismatch_not_an_unresolvable() -> None:
    entry = run_case(CASES_BY_NAME["wrong_doi_real_paper"])
    assert entry["verdict"] == MISMATCH
    reasons = {
        tuple(o["mismatch_reasons"]) for o in entry["source_outcomes"] if o["mismatch_reasons"]
    }
    assert reasons == {("doi_mismatch",)}


def test_gold_valid_doi_with_wrong_metadata_is_a_mismatch() -> None:
    entry = run_case(CASES_BY_NAME["valid_doi_wrong_metadata"])
    assert entry["verdict"] == MISMATCH
    resolving = [o for o in entry["source_outcomes"] if o["resolved"]]
    assert len(resolving) >= 2
    assert all("title_similarity" in o["mismatch_reasons"] for o in resolving)


# ---------------------------------------------------------------------------
# A source that does not hold a DOI has no opinion about it
#
# The refusal-grade false positives measured in evals/BENCHMARKS.md (3/99, of which these
# rules kill all three). An index that does not mint or hold a DOI, asked about it, must
# return a CLEAN NEGATIVE. It must not fall back to a title search, find a similar-looking
# record, and report `doi_mismatch`, because it never had an opinion about the identifier at
# all. Two such non-holding indexes were outvoting one genuine confirmation and producing a
# refusal-grade `mismatch` on real, correctly cited references.
# ---------------------------------------------------------------------------


def title_hit(source: str) -> SourceOutcome:
    """A source that does NOT hold the claimed DOI and found the work by title search."""
    return outcome(
        source,
        NEGATIVE,
        resolved=True,
        matched_by=BY_TITLE_SEARCH,
        mismatch_reasons=("doi_mismatch",),
        matched_record=record(doi="10.5555/some.other.id"),
    )


def test_a_title_search_hit_is_not_a_resolving_disagreement() -> None:
    hit = title_hit("datacite")
    assert hit.disagrees is False  # it never resolved the identifier: it cannot disagree
    assert hit.resolved_identifier is False
    assert hit.found_work_under_another_id is True


def test_two_non_holding_indexes_cannot_outvote_one_confirmation() -> None:
    """10.5281/zenodo.21358727, measured: DataCite confirms, the other two do not hold it.

    Under the old rule the two title-search hits were counted as resolving disagreements and
    D9 rule 2 fired: refusal-grade `mismatch` on a real Zenodo dataset. It must be
    `inconclusive` (one confirmation, below the bar), which is never refusal-grade.
    """
    decision = decide(
        [outcome("datacite", CONFIRMED), title_hit("openalex"), title_hit("crossref")]
    )
    assert decision.verdict == INCONCLUSIVE
    assert decision.refusal_grade is False


def test_a_non_holding_index_cannot_disagree_with_a_resolving_one() -> None:
    """10.1109/taffc.2020.3014842, measured: OpenAlex confirms, Crossref resolves with a year
    two off (IEEE early access versus issue), DataCite does not mint the DOI at all.

    One resolving disagreement plus one confirmation is thin evidence, not a refusal.
    """
    decision = decide(
        [
            outcome("openalex", CONFIRMED),
            outcome(
                "crossref",
                NEGATIVE,
                resolved=True,
                matched_by=BY_IDENTIFIER,
                mismatch_reasons=("year",),
            ),
            title_hit("datacite"),
        ]
    )
    assert decision.verdict == INCONCLUSIVE
    assert decision.refusal_grade is False


def test_wrong_doi_on_a_real_paper_is_still_a_mismatch() -> None:
    """Rule 2b, the ONLY route by which a title-search hit may convict an identifier.

    Nobody resolved the DOI, nobody errored, and two indexes hold the work under a different
    identifier. The work is real and the identifier in the entry is not its own.
    """
    decision = decide([title_hit("openalex"), title_hit("crossref"), outcome("datacite", NEGATIVE)])
    assert decision.verdict == MISMATCH
    assert decision.refusal_grade is True
    assert decision.disagreements == ("openalex", "crossref")


def test_rule_2b_needs_two_sources_not_one() -> None:
    """One index's fuzzy title hit is never enough to call an identifier wrong."""
    decision = decide([title_hit("openalex"), outcome("crossref", NEGATIVE)])
    assert decision.verdict == INCONCLUSIVE
    assert decision.refusal_grade is False


def test_rule_2b_is_unreachable_once_any_source_errored() -> None:
    """A downed index might have been the one holding the DOI. Same law as `unresolvable`."""
    decision = decide(
        [
            title_hit("openalex"),
            title_hit("crossref"),
            outcome("datacite", SOURCE_ERROR, error={"type": "timeout", "message": "down"}),
        ]
    )
    assert decision.verdict == INCONCLUSIVE
    assert decision.refusal_grade is False


def test_one_source_resolving_the_doi_strips_the_non_holding_indexes_of_a_say() -> None:
    """The DOI exists. Whatever the indexes that do not hold it found by title is irrelevant."""
    decision = decide(
        [
            outcome("datacite", CONFIRMED),
            outcome("semantic_scholar", CONFIRMED),
            title_hit("openalex"),
            title_hit("crossref"),
        ]
    )
    assert decision.verdict == VERIFIED
    assert decision.refusal_grade is False


# ---------------------------------------------------------------------------
# Truncated titles: an exact prefix is truncation, not a different paper
# ---------------------------------------------------------------------------

DANS_TITLE = (
    "DO Beatrixstraat 2-12 Zetten Vondsten van laat-middeleeuwse en nieuwetijdse dorpsbewoning "
    "in plangebied Beatrixstraat 2-12 te Zetten, gemeente Overbetuwe. Een inventariserend "
    "veldonderzoek door middel van proefsleuven (IVO-P) en een opgraving (DO)"
)
DANS_TITLE_TRUNCATED = (
    "DO Beatrixstraat 2-12 Zetten Vondsten van laat-middeleeuwse en nieuwetijdse dorpsbewoning"
)


def test_a_long_exact_prefix_is_read_as_truncation() -> None:
    """10.17026/ar/sraj8f, measured: a real DANS dataset whose title a harvester cut at 88
    characters. DataCite resolves the DOI, token_sort_ratio scores 0.539 against the full
    title (the real one runs nearly three times as long, so the 40%-of-the-longer guard also
    refuses to fire), and the verdict was refusal-grade `mismatch` on an honest reference.
    """
    base = fuzz.token_sort_ratio(
        title_fingerprint(DANS_TITLE_TRUNCATED), title_fingerprint(DANS_TITLE)
    ) / 100.0
    assert base < DEFAULT_THRESHOLDS.title_similarity  # what the base ratio alone scores
    assert title_similarity(DANS_TITLE_TRUNCATED, DANS_TITLE) == 1.0


def test_the_prefix_rule_does_not_fire_on_a_short_prefix() -> None:
    """The guard against the rule's own risk: a short shared opening is NOT identity.

    Two different papers routinely open with the same handful of words. The rule requires an
    exact prefix of at least `truncated_prefix_min_chars`, which no such opening reaches.
    """
    short = "Deep learning for medical"  # 25 chars: a real, common title opening
    longer = "Deep learning for medical image segmentation: a comprehensive survey"
    assert len(title_fingerprint(short)) < DEFAULT_THRESHOLDS.truncated_prefix_min_chars
    score = title_similarity(short, longer)
    assert score is not None and score < 1.0


def test_the_prefix_rule_is_exact_not_fuzzy() -> None:
    """A title that DIVERGES from the longer one is not a truncation of it, however early."""
    claimed = "Cardiologist-level arrhythmia detection using support vector machines in ambulatory"
    found = (
        "Cardiologist-level arrhythmia detection and classification in ambulatory "
        "electrocardiograms using a deep neural network"
    )
    score = title_similarity(claimed, found)
    assert score is not None and score < 1.0


def test_the_prefix_rule_lifts_the_title_only_and_the_author_check_still_stands() -> None:
    """It cannot confirm a different work: year and first author are still checked."""
    claim = ReferenceClaim(
        title=DANS_TITLE_TRUNCATED, year=2026, authors=["Someone, Entirely Different"]
    )
    assessment = assess_match(claim, record(title=DANS_TITLE, year=2026, surname="Bakker"))
    assert assessment.similarity == 1.0
    assert not assessment.matched
    assert "first_author_surname" in assessment.reasons
    assert assessment.identity_broken is True


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def full_report() -> dict[str, Any]:
    """Every gold case in one report, as `verify-bib` would produce it over a library.

    Each case keeps its own source list (that is part of what the case IS), so the entries
    are built one at a time and assembled into a single report.
    """
    import asyncio

    from researcher_core.verify import build_report, verify_claim_async

    async def go() -> list[Any]:
        entries = []
        for case in CASES:
            connectors = gold_connectors(case)
            try:
                claim = ReferenceClaim.from_mapping(case["claim"])
                entries.append(await verify_claim_async(claim, connectors))
            finally:
                for connector in connectors:
                    await connector.aclose()
        return entries

    return build_report(
        asyncio.run(go()),
        sources=["openalex", "crossref", "datacite", "semantic_scholar"],
        input_kind="bib",
        input_path="library.bib",
    )


def test_report_validates_against_its_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(full_report())


def test_report_summary_counts_every_axis() -> None:
    report = full_report()
    summary = report["summary"]
    assert summary["total"] == len(report["entries"])
    assert sum(summary["identity"].values()) == summary["total"]
    assert summary["refusal_grade"] == (
        summary["identity"]["unresolvable"] + summary["identity"]["mismatch"]
    )
    assert sum(summary["status"].values()) == summary["total"]
    assert sum(summary["accessibility"].values()) == summary["total"]


def test_report_carries_the_thresholds_that_produced_it() -> None:
    thresholds = full_report()["thresholds"]
    assert thresholds == {
        "title_similarity": 0.70,
        "year_tolerance": 1,
        "require_first_author_surname": True,
        "min_confirmations": 2,
    }


def test_report_carries_axis_b_and_axis_d_per_entry() -> None:
    for entry in full_report()["entries"]:
        assert entry["status"]["verdict"] in {
            "current",
            "corrected",
            "retracted",
            "expression-of-concern",
        }
        assert entry["accessibility"]["verdict"] in {"full-text", "abstract-only", "unavailable"}


def test_replay_is_byte_identical(tmp_path: Path) -> None:
    """D15: same snapshots, same configuration, same versions, same bytes."""
    first = canonical_json(full_report())
    second = canonical_json(full_report())
    assert first == second


def test_a_reference_with_no_doi_is_verified_by_title_and_reports_status_unchecked() -> None:
    entry = run_case(CASES_BY_NAME["title_only_reference"])
    # Confirmed by title search in both indexes; axis (b) needs a DOI and was never asked.
    assert entry["verdict"] == VERIFIED
    assert entry["reference"]["doi"] is None
    assert entry["status"] == {"verdict": "current", "checked": False, "notices": [], "sources": []}
    assert all(o["resolved"] for o in entry["source_outcomes"])


def test_verify_claims_sync_entry_point_runs_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(GOLD_ROOT))
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_MODE", SnapshotMode.REPLAY.value)
    case = CASES_BY_NAME["clean_two_index"]
    report = verify_claims(
        [ReferenceClaim.from_mapping(case["claim"])],
        sources=case["sources"],
        input_kind="reference",
        input_reference=case["claim"]["doi"],
    )
    assert report["entries"][0]["verdict"] == VERIFIED
    assert report["input"] == {"kind": "reference", "reference": case["claim"]["doi"]}
    assert report["sources_queried"] == case["sources"]
