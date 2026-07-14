"""Axis (c): claim faithfulness, anchored on stable passage IDs (M2.9, D11, D16, D21).

Four verdicts, and exactly four:

* ``supported``            - the retrieved passages carry the claim.
* ``partial``              - they carry part of it, or carry it with weaker qualifiers.
* ``contradicted``         - at least one passage states the opposite.
* ``insufficient-passage`` - no passage adequate to decide. This is ABSTENTION.

``insufficient-passage`` is the rename of the retired "unverified, no full text" verdict. The
old string appears nowhere in this kernel, and it must not be reintroduced: the new name says
what actually happened (no adequate passage), while the old one described only one of the
several ways to get there, and a test greps the package to keep it out.

Two invariants, both load-bearing, both tested:

1. **Every non-abstaining verdict is anchored on at least one passage ID**, with the
   passage's content hash, character offsets, and page coordinates. A faithfulness claim that
   cannot point at the text that justified it is not evidence, it is an opinion.
2. **An abstention is never clean.** When axis (d) is not ``full-text``, or the document has
   no indexed passages, every claim degrades to abstract level with verdict
   ``insufficient-passage`` and ``clean: false`` (D11). There is no code path where a claim
   over an ``abstract-only`` document comes back clean.

M2 ships the LEXICAL baseline: BM25 retrieval over the D21 index plus token-overlap and
polarity heuristics, which is enough to benchmark the axis and to price abstention on a
risk-coverage curve. M3 layers richer claim anchoring on this same verdict vocabulary, this
same report schema, and these same passage IDs, so nothing downstream has to change.

Reports validate against ``core/schemas/faithfulness-report.schema.json``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from . import PROTOCOL_VERSION as _RAW_PROTOCOL_VERSION
from . import __version__
from .fulltext import ABSTRACT_ONLY, FULL_TEXT, dotted_version
from .passages import IndexedDocument, Passage, PassageIndex, tokenize

__all__ = [
    "CONTRADICTED",
    "CONTRADICTION_THRESHOLD",
    "INSUFFICIENT_PASSAGE",
    "METHOD",
    "PARTIAL",
    "PARTIAL_THRESHOLD",
    "PROTOCOL_VERSION",
    "SCHEMA_VERSION",
    "SUPPORTED",
    "SUPPORT_THRESHOLD",
    "VERDICTS",
    "ClaimVerdict",
    "FaithfulnessError",
    "FaithfulnessReport",
    "PassageAssessment",
    "check_claim",
    "check_claims",
    "score_passage",
]

SUPPORTED = "supported"
PARTIAL = "partial"
CONTRADICTED = "contradicted"
INSUFFICIENT_PASSAGE = "insufficient-passage"

#: The axis (c) vocabulary. Nothing outside this tuple is a valid verdict.
VERDICTS = (SUPPORTED, PARTIAL, CONTRADICTED, INSUFFICIENT_PASSAGE)

#: The only method M2 ships. The schema pins it, so a future method must extend both.
METHOD = "lexical-bm25"

SCHEMA_VERSION = "1.0"
PROTOCOL_VERSION = dotted_version(_RAW_PROTOCOL_VERSION)

# Thresholds on the token-overlap score. They are the lexical baseline's calibration knobs,
# stated once here so a change is one edit and shows up in one diff.
SUPPORT_THRESHOLD = 0.75
PARTIAL_THRESHOLD = 0.40
CONTRADICTION_THRESHOLD = 0.40

#: How many BM25 candidates the baseline scores per claim. Beyond this the tail is noise.
DEFAULT_TOP_K = 8
#: How many anchors a verdict carries. Enough to check by hand, few enough to read.
MAX_EVIDENCE = 3
#: The most an overlap score may reach when the claim's numbers are absent from the passage.
#: A passage that shares every word of a claim but not its number does not carry that number.
NUMERIC_MISMATCH_CEILING = 0.60

_NEGATION_CUES = frozenset(
    {
        "no",
        "not",
        "never",
        "neither",
        "nor",
        "none",
        "cannot",
        "without",
        "absent",
        "absence",
        "lack",
        "lacked",
        "lacking",
        "lacks",
        "fail",
        "failed",
        "fails",
        "unable",
        "insignificant",
        "nonsignificant",
        "unchanged",
        "n.s",
        "ns",
    }
)

_NEGATION_PHRASES = (
    "did not",
    "does not",
    "do not",
    "was not",
    "were not",
    "is not",
    "are not",
    "no significant",
    "not significant",
    "no evidence",
    "no difference",
    "no effect",
    "failed to",
)

# Directional antonym pairs. A claim that says "increased" against a passage that says
# "decreased" is a contradiction even when every other token overlaps.
_ANTONYMS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (
        frozenset(
            {"increase", "increased", "increases", "increasing", "higher", "greater", "rose"}
        ),
        frozenset(
            {"decrease", "decreased", "decreases", "decreasing", "lower", "smaller", "fell"}
        ),
    ),
    (
        frozenset({"improve", "improved", "improves", "improvement", "better", "gain", "gains"}),
        frozenset({"worsen", "worsened", "worsens", "degrade", "degraded", "worse", "loss"}),
    ),
    (
        frozenset({"outperform", "outperformed", "outperforms", "superior", "exceeded"}),
        frozenset({"underperform", "underperformed", "inferior", "trailed"}),
    ),
    (
        frozenset({"significant", "significantly"}),
        frozenset({"insignificant", "nonsignificant", "negligible"}),
    ),
)

_DIGIT_RE = re.compile(r"\d")


class FaithfulnessError(RuntimeError):
    """The faithfulness layer cannot answer the question it was asked."""


# ---------------------------------------------------------------------------
# Scoring one passage against one claim
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PassageAssessment:
    """How one passage relates to one claim, under the lexical baseline."""

    passage: Passage
    score: float
    relation: str  # "supporting" | "contradicting"
    overlap: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    numeric_mismatch: bool = False

    @property
    def is_contradicting(self) -> bool:
        return self.relation == "contradicting"

    def anchor_dict(self) -> dict[str, Any]:
        anchor = self.passage.anchor_dict()
        anchor["relation"] = self.relation
        return anchor


def score_passage(claim: str, passage: Passage) -> PassageAssessment:
    """Score one passage against one claim: overlap, polarity, and numeric agreement.

    The score is the fraction of the claim's content tokens the passage contains, capped at
    :data:`NUMERIC_MISMATCH_CEILING` when the claim states a number the passage does not.
    The relation is ``contradicting`` when the passage's polarity opposes the claim's, either
    by negation (one of them negates, the other does not) or by a directional antonym.
    """
    claim_tokens = list(dict.fromkeys(tokenize(claim)))
    if not claim_tokens:
        return PassageAssessment(passage=passage, score=0.0, relation="supporting")

    passage_tokens = set(tokenize(passage.text))
    overlap = [token for token in claim_tokens if token in passage_tokens]
    missing = [token for token in claim_tokens if token not in passage_tokens]
    score = len(overlap) / len(claim_tokens)

    claim_numbers = {t for t in claim_tokens if _DIGIT_RE.search(t)}
    numeric_mismatch = bool(claim_numbers - passage_tokens)
    if numeric_mismatch:
        score = min(score, NUMERIC_MISMATCH_CEILING)

    relation = (
        "contradicting"
        if _opposes(claim, passage.text, claim_tokens, passage_tokens)
        else "supporting"
    )
    return PassageAssessment(
        passage=passage,
        score=round(score, 4),
        relation=relation,
        overlap=tuple(overlap),
        missing=tuple(missing),
        numeric_mismatch=numeric_mismatch,
    )


def _opposes(
    claim: str,
    passage_text: str,
    claim_tokens: Sequence[str],
    passage_tokens: set[str],
) -> bool:
    """True when the passage's polarity opposes the claim's."""
    claim_set = set(claim_tokens)
    if _negated(claim, claim_set) != _negated(passage_text, passage_tokens):
        return True
    for left, right in _ANTONYMS:
        if (claim_set & left and passage_tokens & right) or (
            claim_set & right and passage_tokens & left
        ):
            return True
    return False


def _negated(text: str, tokens: set[str]) -> bool:
    lowered = str(text).casefold()
    if any(phrase in lowered for phrase in _NEGATION_PHRASES):
        return True
    return bool(tokens & _NEGATION_CUES)


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


@dataclass
class ClaimVerdict:
    """The axis (c) verdict for one claim, with its passage anchors."""

    claim_id: str
    claim: str
    verdict: str
    reason: str
    evidence: list[PassageAssessment] = field(default_factory=list)
    score: float | None = None

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise FaithfulnessError(
                f"Unknown faithfulness verdict {self.verdict!r}. Valid: {', '.join(VERDICTS)}."
            )
        if self.verdict != INSUFFICIENT_PASSAGE and not self.evidence:
            # The anchoring invariant, enforced at construction rather than trusted to the
            # caller: a verdict with no passage behind it cannot exist.
            raise FaithfulnessError(
                f"A {self.verdict!r} verdict must be anchored on at least one passage."
            )

    @property
    def clean(self) -> bool:
        """False for every abstention. An ``insufficient-passage`` is never emitted clean (D11)."""
        return self.verdict != INSUFFICIENT_PASSAGE

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "verdict": self.verdict,
            "clean": self.clean,
            "score": self.score,
            "reason": self.reason,
            "evidence": [a.anchor_dict() for a in self.evidence],
        }


@dataclass
class FaithfulnessReport:
    """The axis (c) report for one document. Validates against the report schema."""

    document: IndexedDocument
    claims: list[ClaimVerdict] = field(default_factory=list)
    method: str = METHOD
    run_id: str = ""
    generated_at: str = ""

    @property
    def abstentions(self) -> int:
        return sum(1 for c in self.claims if c.verdict == INSUFFICIENT_PASSAGE)

    @property
    def abstention_rate(self) -> float:
        return round(self.abstentions / len(self.claims), 4) if self.claims else 0.0

    @property
    def coverage(self) -> float:
        return round(1.0 - self.abstention_rate, 4) if self.claims else 0.0

    def counts(self) -> dict[str, int]:
        return {
            verdict: sum(1 for c in self.claims if c.verdict == verdict) for verdict in VERDICTS
        }

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "versions": {"core": __version__, "parser": self.document.parser_version},
            "method": self.method,
            "document": self.document.to_json_dict(),
            "claims": [c.to_json_dict() for c in self.claims],
            "summary": {
                "total": len(self.claims),
                "verdicts": self.counts(),
                "coverage": self.coverage,
                "abstention_rate": self.abstention_rate,
            },
        }
        # Omitted unless supplied: a self-generated timestamp would break byte-identical
        # replay (D15), and the schema does not require either field.
        if self.run_id:
            out["run_id"] = self.run_id
        if self.generated_at:
            out["generated_at"] = self.generated_at
        return out


# ---------------------------------------------------------------------------
# The entry points
# ---------------------------------------------------------------------------


def check_claims(
    claims: Sequence[str],
    doc_id: str,
    index: PassageIndex,
    *,
    top_k: int = DEFAULT_TOP_K,
    run_id: str = "",
    generated_at: str = "",
) -> FaithfulnessReport:
    """Check every claim against one indexed document and build the axis (c) report.

    The degradation rule is applied first and unconditionally: if the document is unknown to
    the index, or its axis (d) verdict is not ``full-text``, or it has no indexed passages,
    every claim comes back ``insufficient-passage`` with ``clean: false`` and no anchors. No
    scoring happens, because there is nothing honest to score against.
    """
    document = index.get_document(doc_id)
    if document is None:
        raise FaithfulnessError(
            f"Document {doc_id!r} is not in the passage index. Run `passages index {doc_id}` "
            "first, or pass the doc_id it was indexed under."
        )

    verdicts = [
        check_claim(
            claim,
            document,
            index,
            top_k=top_k,
            claim_id=f"c{position}",
        )
        for position, claim in enumerate(claims, start=1)
    ]
    return FaithfulnessReport(
        document=document,
        claims=verdicts,
        run_id=run_id,
        generated_at=generated_at,
    )


def check_claim(
    claim: str,
    document: IndexedDocument,
    index: PassageIndex,
    *,
    top_k: int = DEFAULT_TOP_K,
    claim_id: str = "c1",
) -> ClaimVerdict:
    """The axis (c) verdict for one claim against one indexed document."""
    degraded = _degradation_reason(document)
    if degraded is not None:
        return ClaimVerdict(
            claim_id=claim_id,
            claim=claim,
            verdict=INSUFFICIENT_PASSAGE,
            reason=degraded,
            evidence=[],
            score=None,
        )

    candidates = index.search(claim, doc_id=document.doc_id, limit=top_k)
    if not candidates:
        return ClaimVerdict(
            claim_id=claim_id,
            claim=claim,
            verdict=INSUFFICIENT_PASSAGE,
            reason="no passage in this document matched any term of the claim",
            evidence=[],
            score=None,
        )

    assessments = [score_passage(claim, passage) for passage in candidates]
    supporting = sorted(
        (a for a in assessments if not a.is_contradicting), key=lambda a: -a.score
    )
    contradicting = sorted((a for a in assessments if a.is_contradicting), key=lambda a: -a.score)
    best_support = supporting[0].score if supporting else 0.0
    best_contra = contradicting[0].score if contradicting else 0.0

    if best_contra >= CONTRADICTION_THRESHOLD and best_contra >= best_support:
        return ClaimVerdict(
            claim_id=claim_id,
            claim=claim,
            verdict=CONTRADICTED,
            reason=(
                f"passage {contradicting[0].passage.passage_id[:12]} overlaps the claim "
                f"({best_contra:.2f}) with opposing polarity"
            ),
            evidence=contradicting[:MAX_EVIDENCE],
            score=best_contra,
        )

    if best_support >= SUPPORT_THRESHOLD:
        return ClaimVerdict(
            claim_id=claim_id,
            claim=claim,
            verdict=SUPPORTED,
            reason=(
                f"passage {supporting[0].passage.passage_id[:12]} carries "
                f"{best_support:.0%} of the claim's terms"
            ),
            evidence=supporting[:MAX_EVIDENCE],
            score=best_support,
        )

    if best_support >= PARTIAL_THRESHOLD:
        missing = ", ".join(supporting[0].missing[:5])
        qualifier = (
            "the claim's numbers are absent from the passage"
            if supporting[0].numeric_mismatch
            else f"terms not found in the passage: {missing}"
            if missing
            else "the passage carries the claim only in part"
        )
        return ClaimVerdict(
            claim_id=claim_id,
            claim=claim,
            verdict=PARTIAL,
            reason=(
                f"best passage {supporting[0].passage.passage_id[:12]} covers "
                f"{best_support:.0%} of the claim; {qualifier}"
            ),
            evidence=supporting[:MAX_EVIDENCE],
            score=best_support,
        )

    return ClaimVerdict(
        claim_id=claim_id,
        claim=claim,
        verdict=INSUFFICIENT_PASSAGE,
        reason=(
            f"no passage covers enough of the claim (best overlap {best_support:.0%}, "
            f"threshold {PARTIAL_THRESHOLD:.0%})"
        ),
        evidence=[],
        score=best_support if best_support else None,
    )


def _degradation_reason(document: IndexedDocument) -> str | None:
    """The D11 abstract-level degradation, or ``None`` when full-text checking is possible."""
    if document.accessibility != FULL_TEXT:
        detail = (
            "only the abstract and metadata are reachable"
            if document.accessibility == ABSTRACT_ONLY
            else "no open-access copy of this work could be resolved"
        )
        return (
            f"no full text: axis (d) accessibility is {document.accessibility}, so {detail}. "
            "The claim is checked at abstract level only and is not emitted as clean."
        )
    if document.passage_count == 0:
        return (
            "the document is marked full-text but has no indexed passages, so there is "
            "nothing to anchor a verdict on"
        )
    return None
