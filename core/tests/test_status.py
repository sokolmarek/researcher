"""Axis (b) publication-status tests (D16).

Every test runs OFFLINE against ``core/tests/snapshots/verify-gold/``, whose Crossref and
OpenAlex responses were recorded from the live APIs. The DOIs classified here are a
snapshot-backed subset of the real 120-DOI gold set in ``evals/gold/status.yaml``
(25 retracted / 25 corrected / 25 expression-of-concern / 45 current), three per class, plus
the two rows that carry the trap this axis exists to survive: the Lancet Surgisphere paper
(retracted) and its retraction NOTICE, which is a current document that carries a Crossref
``update-to`` of type ``retraction`` in both directions.

Axis (b) is independent of axis (a): the last test in this file verifies a retracted paper on
identity and still reports it retracted on status.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from researcher_core.connectors import create_connector
from researcher_core.connectors.base import BaseConnector, SourceError, SourceErrorKind
from researcher_core.connectors.crossref import UPDATED_BY_KEY
from researcher_core.model import CSLRecord, canonical_json
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore
from researcher_core.status import (
    CORRECTED,
    CURRENT,
    EXPRESSION_OF_CONCERN,
    RETRACTED,
    Notice,
    build_report,
    check_status,
    check_status_async,
    classify,
)
from researcher_core.verify import ReferenceClaim, verify_claim_async

GOLD_ROOT = Path(__file__).resolve().parent / "snapshots" / "verify-gold"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "status-report.schema.json"

GOLD: dict[str, Any] = json.loads((GOLD_ROOT / "status-cases.json").read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = GOLD["cases"]
STATUS_SOURCES: list[str] = GOLD["sources"]

RETRACTED_PAPER = "10.1016/s0140-6736(20)31180-6"  # Mehra et al. 2020 (Surgisphere)
RETRACTION_NOTICE = "10.1016/s0140-6736(20)31324-6"  # the notice for the paper above
CLEAN_DOI = "10.1038/s41597-020-0495-6"


def gold_connectors(sources: list[str] | None = None) -> list[BaseConnector]:
    session = SnapshotSession(SnapshotStore(GOLD_ROOT), SnapshotMode.REPLAY)
    return [create_connector(name, snapshots=session) for name in (sources or STATUS_SOURCES)]


def check(doi: str, connectors: list[BaseConnector] | None = None) -> Any:
    async def go() -> Any:
        built = connectors if connectors is not None else gold_connectors()
        try:
            return await check_status_async(doi, built)
        finally:
            for connector in built:
                await connector.aclose()

    return asyncio.run(go())


def _make_it_fail(
    connector: BaseConnector, kind: SourceErrorKind = SourceErrorKind.RATE_LIMIT
) -> None:
    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise SourceError(connector.name, "429 Too Many Requests", kind=kind, status_code=429)

    connector.resolve_doi = boom  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# The gold subset
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[c["doi"] for c in CASES])
def test_gold_doi_classifies_as_expected(case: dict[str, Any]) -> None:
    entry = check(case["doi"])
    assert entry.verdict == case["expected"], entry.reason
    assert entry.checked is True


def test_a_retracted_paper_is_retracted() -> None:
    entry = check(RETRACTED_PAPER)
    assert entry.verdict == RETRACTED
    assert {n.type for n in entry.notices} >= {"retraction"}
    # The real Lancet update graph also carries a correction and an expression of concern.
    # The strongest notice wins, and the weaker ones are still reported, not discarded.
    assert {n.type for n in entry.notices} >= {"correction", "expression-of-concern"}
    assert entry.conflict is False  # OpenAlex agrees: is_retracted is true


def test_the_retraction_notice_itself_is_current() -> None:
    """THE trap. The notice carries `update-to: retraction` AND `updated-by: retraction`,
    both pointing at the paper it retracts, and OpenAlex sets is_retracted on it. Every one
    of those signals, read naively, says 'retracted'. The document is a current one."""
    entry = check(RETRACTION_NOTICE)
    assert entry.verdict == CURRENT
    assert entry.notices == []
    assert "itself an editorial notice" in entry.reason
    # OpenAlex disagrees, and the disagreement is reported rather than resolved away.
    assert entry.conflict is True
    openalex = next(s for s in entry.sources if s.source == "openalex")
    assert openalex.is_retracted is True


def test_a_notice_that_itself_acquired_a_notice_keeps_it() -> None:
    """A Lancet Neurology expression-of-concern notice that later received one of its own."""
    entry = check("10.1016/s1474-4422(22)00030-8")
    assert entry.verdict == EXPRESSION_OF_CONCERN
    kinds = {n.type for n in entry.notices}
    assert kinds == {"expression-of-concern"}


def test_a_clean_doi_is_current_and_checked() -> None:
    entry = check(CLEAN_DOI)
    assert entry.verdict == CURRENT
    assert entry.checked is True
    assert entry.notices == []
    assert {s.outcome for s in entry.sources} == {"negative"}


def test_withdrawal_maps_to_retracted_and_erratum_to_corrected() -> None:
    assert check("10.1016/j.ijhydene.2022.01.206").verdict == RETRACTED
    assert check("10.1016/j.cellsig.2012.01.015").verdict == CORRECTED


def test_expression_of_concern_is_never_collapsed_into_retracted() -> None:
    for case in (c for c in CASES if c["class"] == "expression-of-concern"):
        entry = check(case["doi"])
        assert entry.verdict == EXPRESSION_OF_CONCERN
        assert entry.verdict != RETRACTED


# ---------------------------------------------------------------------------
# The clean-negative / source-error split
# ---------------------------------------------------------------------------


def test_every_source_erroring_leaves_the_status_unchecked() -> None:
    """An unchecked status is an absence of evidence, not evidence of currency."""
    connectors = gold_connectors()
    for connector in connectors:
        _make_it_fail(connector)
    entry = check(RETRACTED_PAPER, connectors)
    assert entry.checked is False
    assert entry.verdict == CURRENT  # the schema has no fifth verdict; `checked` is the flag
    assert "not evidence of currency" in entry.reason
    assert {s.outcome for s in entry.sources} == {"source_error"}
    for source in entry.sources:
        assert source.error["type"] == "rate_limit"
        assert source.error["http_status"] == 429


def test_one_source_erroring_still_yields_the_notice_the_other_found() -> None:
    connectors = gold_connectors()
    _make_it_fail(next(c for c in connectors if c.name == "openalex"))
    entry = check(RETRACTED_PAPER, connectors)
    assert entry.verdict == RETRACTED
    assert entry.checked is True  # Crossref answered cleanly
    assert entry.conflict is False  # a downed source does not disagree; it says nothing


def test_a_doi_no_source_holds_is_checked_and_current() -> None:
    entry = check("10.1109/TBME.2021.3098765")  # the seeded fake from the citation example
    assert entry.checked is True
    assert entry.verdict == CURRENT
    assert {s.outcome for s in entry.sources} == {"negative"}
    # Axis (b) has nothing to say about a DOI that does not exist. Axis (a) does, and calls
    # it unresolvable. Neither axis speaks for the other.


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------


def test_the_strongest_notice_wins() -> None:
    notices = [
        Notice(type="correction", source="crossref"),
        Notice(type="expression-of-concern", source="crossref"),
        Notice(type="retraction", source="crossref"),
    ]
    assert classify(notices) == RETRACTED
    assert classify(notices[:2]) == EXPRESSION_OF_CONCERN
    assert classify(notices[:1]) == CORRECTED
    assert classify([]) == CURRENT


@pytest.mark.parametrize(
    ("notice_type", "expected"),
    [
        ("retraction", RETRACTED),
        ("withdrawal", RETRACTED),
        ("removal", RETRACTED),
        ("expression-of-concern", EXPRESSION_OF_CONCERN),
        ("correction", CORRECTED),
        ("erratum", CORRECTED),
        ("addendum", CORRECTED),
    ],
)
def test_every_notice_type_maps_to_a_verdict(notice_type: str, expected: str) -> None:
    assert classify([Notice(type=notice_type, source="crossref")]) == expected


def test_an_openalex_only_retraction_flag_is_reported_as_a_conflict() -> None:
    """OpenAlex says retracted, Crossref carries no notice. Report both, resolve neither."""
    from researcher_core.status import StatusSourceOutcome, _conflicted

    outcomes = [
        StatusSourceOutcome("crossref", "negative"),
        StatusSourceOutcome("openalex", "confirmed", is_retracted=True, notice_count=1),
    ]
    notices = [Notice(type="retraction", source="openalex")]
    assert _conflicted(outcomes, notices) is True
    assert classify(notices) == RETRACTED  # the stronger verdict is taken, and flagged


# ---------------------------------------------------------------------------
# Precedence: a specific signal outranks a coarse one
# ---------------------------------------------------------------------------
#
# OpenAlex's `is_retracted` is ONE boolean over several kinds of editorial notice, and OpenAlex
# sets it on works whose only Crossref update-type is `expression_of_concern`. The kernel used to
# mint a `retraction` notice from that flag unconditionally, so the coarse boolean silently
# overrode Crossref's specific update-type and the work came out `retracted`. An expression of
# concern is an unresolved question about a paper, not a withdrawal of it: reporting it as a
# retraction accuses the authors of work that still stands.
#
# These are SYNTHETIC records, deliberately. Every real DOI in the gold set on which OpenAlex
# reports is_retracted also carries a Crossref RETRACTION (checked live on 2026-07-14, including
# the six that were relabeled), so no live snapshot exercises this path. It is one OpenAlex
# over-flag away from firing on a real paper, and it is what these tests pin.


SYNTHETIC_DOI = "10.1234/eoc-only"
EOC_UPDATE = {"DOI": "10.1234/eoc-notice", "type": "expression_of_concern", "label": "EoC"}
RETRACTION_UPDATE = {"DOI": "10.1234/ret-notice", "type": "retraction", "label": "Retraction"}


def _crossref_record(*updated_by: dict[str, Any]) -> CSLRecord:
    return CSLRecord(
        title="A paper under an expression of concern",
        DOI=SYNTHETIC_DOI,
        extra={UPDATED_BY_KEY: list(updated_by)},
    )


def _flagged_record() -> CSLRecord:
    """What OpenAlex returns for such a paper: is_retracted, and no notice detail at all."""
    return CSLRecord(
        title="A paper under an expression of concern",
        DOI=SYNTHETIC_DOI,
        is_retracted=True,
    )


def _canned(connector: BaseConnector, record: CSLRecord | None) -> None:
    async def resolve(*_args: Any, **_kwargs: Any) -> CSLRecord | None:
        return record

    connector.resolve_doi = resolve  # type: ignore[method-assign]


def _entry_for(crossref: CSLRecord | None, openalex: CSLRecord | None) -> Any:
    connectors = gold_connectors(["crossref", "openalex"])
    _canned(connectors[0], crossref)
    _canned(connectors[1], openalex)
    return check(SYNTHETIC_DOI, connectors)


def test_crossrefs_expression_of_concern_outranks_openalexs_coarse_retracted_flag() -> None:
    """THE fix. Crossref: expression_of_concern. OpenAlex: is_retracted. Verdict: EoC."""
    entry = _entry_for(_crossref_record(EOC_UPDATE), _flagged_record())
    assert entry.verdict == EXPRESSION_OF_CONCERN
    assert entry.verdict != RETRACTED  # the coarse boolean does not get to say "retracted"
    assert [n.type for n in entry.notices] == ["expression-of-concern"]


def test_the_outranked_openalex_claim_is_still_carried_in_the_report() -> None:
    """Outranked is not discarded. A reader must see that OpenAlex disagrees."""
    entry = _entry_for(_crossref_record(EOC_UPDATE), _flagged_record())
    assert entry.verdict == EXPRESSION_OF_CONCERN
    assert entry.conflict is True
    openalex = next(s for s in entry.sources if s.source == "openalex")
    assert openalex.is_retracted is True  # the disagreeing claim, retained verbatim
    assert openalex.outcome == "confirmed"  # the source answered with a flag; it just lost
    assert openalex.notice_count == 0  # and it minted no notice
    assert "OpenAlex reports is_retracted=true" in entry.reason
    assert "not resolved away" in entry.reason


def test_openalex_alone_still_surfaces_a_retraction_when_crossref_is_silent() -> None:
    """The other direction, and the fix must not swing into it. With no Crossref opinion of any
    kind, OpenAlex is the only source with one, it is a real one, and it stands."""
    entry = _entry_for(_crossref_record(), _flagged_record())
    assert entry.verdict == RETRACTED
    assert [n.source for n in entry.notices] == ["openalex"]
    assert entry.conflict is True  # Crossref does not corroborate it, and that is reported

    # Same, when Crossref does not hold the DOI at all.
    entry = _entry_for(None, _flagged_record())
    assert entry.verdict == RETRACTED


def test_a_crossref_retraction_and_an_openalex_flag_agree_and_raise_no_conflict() -> None:
    entry = _entry_for(_crossref_record(RETRACTION_UPDATE), _flagged_record())
    assert entry.verdict == RETRACTED
    assert entry.conflict is False
    assert [n.source for n in entry.notices] == ["crossref"]


def test_an_escalated_paper_is_retracted_on_crossrefs_own_evidence() -> None:
    """The six gold papers relabeled on 2026-07-14: an expression of concern FIRST, a retraction
    LATER. Crossref carries both update-types on the paper itself, so the verdict is `retracted`
    on the SPECIFIC signal, not on OpenAlex's boolean, and it survives the precedence above."""
    entry = _entry_for(_crossref_record(EOC_UPDATE, RETRACTION_UPDATE), _flagged_record())
    assert entry.verdict == RETRACTED
    assert {n.type for n in entry.notices} == {"expression-of-concern", "retraction"}
    assert entry.conflict is False


def test_a_source_error_is_never_a_conflict() -> None:
    from researcher_core.status import StatusSourceOutcome, _conflicted

    outcomes = [
        StatusSourceOutcome("crossref", "source_error", error={"type": "timeout", "message": "x"}),
        StatusSourceOutcome("openalex", "confirmed", is_retracted=True, notice_count=1),
    ]
    assert _conflicted(outcomes, [Notice(type="retraction", source="openalex")]) is False


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def full_report() -> dict[str, Any]:
    entries = [check(case["doi"]) for case in CASES]
    return build_report(entries, input_kind="bib", input_path="library.bib")


def test_report_validates_against_its_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(full_report())


def test_report_summary_tallies_every_class() -> None:
    report = full_report()
    summary = report["summary"]
    assert summary["total"] == len(CASES)
    assert sum(summary["status"].values()) == len(CASES)
    assert summary["status"]["retracted"] == sum(1 for c in CASES if c["expected"] == "retracted")
    assert summary["status"]["corrected"] == sum(1 for c in CASES if c["expected"] == "corrected")
    assert summary["status"]["expression-of-concern"] == sum(
        1 for c in CASES if c["expected"] == "expression-of-concern"
    )
    assert summary["unchecked"] == 0
    assert summary["conflicts"] == 1  # the retraction notice OpenAlex flags as retracted


def test_replay_is_byte_identical() -> None:
    assert canonical_json(full_report()) == canonical_json(full_report())


def test_check_status_sync_entry_point_runs_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(GOLD_ROOT))
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_MODE", SnapshotMode.REPLAY.value)
    report = check_status([RETRACTED_PAPER, CLEAN_DOI], input_kind="doi", input_doi=RETRACTED_PAPER)
    assert [e["verdict"] for e in report["entries"]] == [RETRACTED, CURRENT]
    assert report["summary"]["status"]["retracted"] == 1


# ---------------------------------------------------------------------------
# The axes are independent
# ---------------------------------------------------------------------------


def test_a_reference_verified_on_axis_a_is_still_retracted_on_axis_b() -> None:
    """The whole reason axis (b) is a separate axis. The paper is real AND it is retracted."""
    claim = ReferenceClaim(
        key="mehra2020",
        title=(
            "Hydroxychloroquine or chloroquine with or without a macrolide for treatment of "
            "COVID-19: a multinational registry analysis"
        ),
        doi=RETRACTED_PAPER,
        year=2020,
        authors=["Mehra, Mandeep R."],
    )

    async def go() -> Any:
        connectors = gold_connectors(["openalex", "crossref"])
        try:
            return await verify_claim_async(claim, connectors)
        finally:
            for connector in connectors:
                await connector.aclose()

    entry = asyncio.run(go()).to_json_dict()
    assert entry["verdict"] == "verified"
    assert entry["refusal_grade"] is False
    assert entry["status"]["verdict"] == RETRACTED
    assert entry["status"]["checked"] is True
    assert "retraction" in {n["type"] for n in entry["status"]["notices"]}


def test_notice_type_vocabulary_matches_the_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    allowed = set(schema["$defs"]["noticeType"]["enum"])
    from researcher_core.status import _CROSSREF_UPDATE_TYPES, _NOTICE_VERDICT

    assert set(_CROSSREF_UPDATE_TYPES.values()) <= allowed
    assert set(_NOTICE_VERDICT) <= allowed


def test_a_record_with_no_update_metadata_yields_no_notices() -> None:
    from researcher_core.status import _crossref_notices

    assert _crossref_notices(CSLRecord(title="A paper", DOI="10.1/x"), "10.1/x") == []
