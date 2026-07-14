"""Axis (c) claim faithfulness: the lexical baseline and its abstention rules (M2.9).

Offline, in-memory, and deterministic. The document under test is built from blocks, indexed
into an in-memory FTS5 store, and every verdict is checked against the passage it is anchored
on.

The two rules this file exists to hold down:

* A claim over a document that is not ``full-text`` on axis (d) comes back
  ``insufficient-passage`` and is NEVER clean (D11). Asserted for ``abstract-only`` and for
  ``unavailable``, and asserted on the serialized report, not just the object.
* The retired string ``unverified_no_fulltext`` appears nowhere in the kernel. The rename is
  part of this milestone; a grep over the package enforces it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from researcher_core.faithfulness import (
    CONTRADICTED,
    INSUFFICIENT_PASSAGE,
    METHOD,
    PARTIAL,
    SUPPORTED,
    ClaimVerdict,
    FaithfulnessError,
    check_claim,
    check_claims,
    score_passage,
)
from researcher_core.fulltext import (
    ABSTRACT_ONLY,
    UNAVAILABLE,
    ExtractedDocument,
    PageRect,
    TextBlock,
    build_document,
)
from researcher_core.passages import PassageIndex

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schemas" / "faithfulness-report.schema.json"
)

DOC_ID = "10.7717/peerj.4375"

BLOCKS = [
    TextBlock(text="Abstract", page=1, rect=PageRect(1, 72, 60, 200, 74)),
    TextBlock(
        text=(
            "We evaluate a self-supervised model on twelve-lead ECG recordings collected "
            "from 4200 patients across two hospitals."
        ),
        page=1,
        rect=PageRect(1, 72, 90, 540, 130),
    ),
    TextBlock(text="3. Results", page=2, rect=PageRect(2, 72, 60, 200, 74)),
    TextBlock(
        text=(
            "The self-supervised model reached an accuracy of 0.91 on the held-out test set, "
            "which exceeded the supervised baseline."
        ),
        page=2,
        rect=PageRect(2, 72, 90, 540, 140),
    ),
    TextBlock(text="4. Discussion", page=2, rect=PageRect(2, 72, 200, 200, 214)),
    TextBlock(
        text=(
            "Pretraining did not improve calibration, and the expected calibration error was "
            "unchanged relative to the supervised baseline."
        ),
        page=2,
        rect=PageRect(2, 72, 230, 540, 280),
    ),
]


def full_text_document() -> ExtractedDocument:
    return build_document(
        BLOCKS,
        doc_id=DOC_ID,
        doi=DOC_ID,
        url="https://example.org/oa/paper.pdf",
        content_type="pdf",
        source="unpaywall",
        source_response_hashes=["b" * 64],
    )


@pytest.fixture()
def index() -> Any:
    with PassageIndex(":memory:") as instance:
        instance.index_document(full_text_document())
        yield instance


def validate(report: dict[str, Any]) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(report)


# ---------------------------------------------------------------------------
# The four verdicts
# ---------------------------------------------------------------------------


def test_a_claim_the_passages_carry_is_supported_and_anchored(index: PassageIndex) -> None:
    report = check_claims(
        ["The self-supervised model reached an accuracy of 0.91 on the held-out test set."],
        DOC_ID,
        index,
    )
    verdict = report.claims[0]

    assert verdict.verdict == SUPPORTED
    assert verdict.clean is True
    assert verdict.score is not None and verdict.score >= 0.75

    anchor = verdict.evidence[0]
    assert anchor.relation == "supporting"
    assert anchor.passage.passage_id == index.search("accuracy 0.91", doc_id=DOC_ID)[0].passage_id
    assert anchor.passage.page_coords[0].page == 2
    assert anchor.passage.section_path.endswith("3. Results")
    validate(report.to_json_dict())


def test_a_claim_with_an_unsupported_number_is_partial(index: PassageIndex) -> None:
    """The passage says 0.91. A claim of 0.97 shares every other word, and is not supported."""
    verdict = check_claim(
        "The self-supervised model reached an accuracy of 0.97 on the held-out test set.",
        index.get_document(DOC_ID),
        index,
    )
    assert verdict.verdict == PARTIAL
    assert verdict.clean is True
    assert "numbers are absent" in verdict.reason
    assert verdict.evidence[0].numeric_mismatch is True


def test_a_claim_the_passages_deny_is_contradicted(index: PassageIndex) -> None:
    verdict = check_claim(
        "Pretraining improved calibration relative to the supervised baseline.",
        index.get_document(DOC_ID),
        index,
    )
    assert verdict.verdict == CONTRADICTED
    assert verdict.evidence[0].relation == "contradicting"
    assert "calibration" in verdict.evidence[0].passage.text
    assert verdict.clean is True


def test_a_claim_no_passage_addresses_abstains(index: PassageIndex) -> None:
    verdict = check_claim(
        "Transformer language models memorize their training corpora verbatim.",
        index.get_document(DOC_ID),
        index,
    )
    assert verdict.verdict == INSUFFICIENT_PASSAGE
    assert verdict.clean is False
    assert verdict.evidence == []


# ---------------------------------------------------------------------------
# D11: no full text, no clean verdict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", [ABSTRACT_ONLY, UNAVAILABLE])
def test_a_claim_over_a_document_without_full_text_is_never_clean(verdict: str) -> None:
    document = ExtractedDocument(
        doc_id=DOC_ID,
        accessibility=verdict,
        doi=DOC_ID,
        abstract="We evaluate a self-supervised model and reach an accuracy of 0.91.",
    )
    with PassageIndex(":memory:") as index:
        index.index_document(document)
        report = check_claims(
            [
                # Note: the abstract literally contains this sentence. It STILL must not come
                # back clean, because no passage exists to anchor it (D11).
                "The self-supervised model reached an accuracy of 0.91.",
                "The model was trained on data from 4200 patients.",
            ],
            DOC_ID,
            index,
        )

    assert report.document.accessibility == verdict
    for claim in report.claims:
        assert claim.verdict == INSUFFICIENT_PASSAGE
        assert claim.clean is False
        assert claim.evidence == []
        assert "no full text" in claim.reason

    serialized = report.to_json_dict()
    assert serialized["summary"]["abstention_rate"] == 1.0
    assert serialized["summary"]["coverage"] == 0.0
    assert serialized["summary"]["verdicts"]["insufficient-passage"] == 2
    assert all(claim["clean"] is False for claim in serialized["claims"])
    validate(serialized)


def test_an_abstaining_verdict_is_the_only_one_allowed_to_have_no_anchor() -> None:
    with pytest.raises(FaithfulnessError, match="anchored"):
        ClaimVerdict(claim_id="c1", claim="x", verdict=SUPPORTED, reason="none", evidence=[])
    # The abstention is fine without one, because that is exactly what it means.
    abstained = ClaimVerdict(
        claim_id="c1", claim="x", verdict=INSUFFICIENT_PASSAGE, reason="none", evidence=[]
    )
    assert abstained.clean is False


#: The retired verdict name, assembled at runtime so this file does not itself contain the
#: literal the guard below forbids.
RETIRED_VERDICT = "unverified" + "_no_" + "fulltext"


def test_an_unknown_verdict_string_is_rejected() -> None:
    with pytest.raises(FaithfulnessError):
        ClaimVerdict(claim_id="c1", claim="x", verdict=RETIRED_VERDICT, reason="r")


def test_the_retired_verdict_name_appears_nowhere_in_the_kernel() -> None:
    """The rename lands in this milestone. The old string must not come back in the code."""
    package = Path(__file__).resolve().parent.parent / "researcher_core"
    offenders = [
        path.name
        for path in package.rglob("*.py")
        if RETIRED_VERDICT in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_a_document_absent_from_the_index_raises_rather_than_guessing() -> None:
    with PassageIndex(":memory:") as index:
        with pytest.raises(FaithfulnessError, match="not in the passage index"):
            check_claims(["anything"], "10.9999/never-indexed", index)


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def test_the_report_prices_abstention_and_validates(index: PassageIndex) -> None:
    report = check_claims(
        [
            "The self-supervised model reached an accuracy of 0.91 on the held-out test set.",
            "Transformer language models memorize their training corpora verbatim.",
        ],
        DOC_ID,
        index,
        run_id="run-1",
        generated_at="2026-07-14T12:00:00Z",
    )
    serialized = report.to_json_dict()

    assert serialized["method"] == METHOD
    assert serialized["run_id"] == "run-1"
    assert serialized["versions"]["parser"] == report.document.parser_version
    assert serialized["document"]["doc_hash"] == index.get_document(DOC_ID).doc_hash
    assert serialized["summary"]["total"] == 2
    assert serialized["summary"]["coverage"] == 0.5
    assert serialized["summary"]["abstention_rate"] == 0.5
    validate(serialized)


def test_the_report_is_deterministic(index: PassageIndex) -> None:
    claims = ["The model reached an accuracy of 0.91.", "The study enrolled 4200 patients."]
    first = check_claims(claims, DOC_ID, index).to_json_dict()
    second = check_claims(claims, DOC_ID, index).to_json_dict()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    # No self-generated timestamp: a clock would break byte-identical replay (D15).
    assert "generated_at" not in first


def test_claim_ids_are_stable_and_positional(index: PassageIndex) -> None:
    report = check_claims(["first claim about ECG", "second claim about ECG"], DOC_ID, index)
    assert [c.claim_id for c in report.claims] == ["c1", "c2"]


# ---------------------------------------------------------------------------
# Scoring internals
# ---------------------------------------------------------------------------


def test_score_passage_reports_overlap_and_polarity(index: PassageIndex) -> None:
    passage = index.search("calibration", doc_id=DOC_ID)[0]

    supporting = score_passage("Pretraining did not improve calibration.", passage)
    assert supporting.relation == "supporting"
    assert supporting.score > 0.5

    opposing = score_passage("Pretraining improved calibration.", passage)
    assert opposing.relation == "contradicting"


def test_score_passage_caps_a_numeric_mismatch(index: PassageIndex) -> None:
    passage = index.search("accuracy 0.91", doc_id=DOC_ID)[0]
    assessment = score_passage("The model reached an accuracy of 0.42.", passage)
    assert assessment.numeric_mismatch is True
    assert assessment.score <= 0.60
