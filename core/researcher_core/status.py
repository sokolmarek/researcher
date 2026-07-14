"""Axis (b): publication status (D16).

Is the work still standing? Verdicts, exactly four:

* ``current``               no editorial notice found
* ``corrected``             a correction, erratum, or addendum was issued
* ``expression-of-concern`` the journal has flagged concerns, but has not retracted
* ``retracted``             retracted, withdrawn, or removed

Axis (b) is INDEPENDENT of axis (a). A reference can be perfectly ``verified`` on identity
and still be ``retracted`` here; the report carries both, side by side, and never folds one
into the other. A retraction is not a fabrication, and a fabrication is not a retraction.

Sources
-------
**Crossref** carries the update graph. Two arrays, and they point in OPPOSITE directions:

* ``updated-by``  updates other works make to THIS one. "This paper was retracted" lives here.
* ``update-to``   updates THIS work makes to other works. A retraction NOTICE carries
  ``update-to: [{DOI: <the retracted paper>, type: retraction}]`` while being a perfectly
  current document itself. Publishers ALSO deposit ``update-to`` on the retracted article,
  pointing at its notice.

So ``update-to`` cannot be read naively in either direction. The disambiguation is in
:func:`_crossref_notices`: an ``update-to`` entry that points at the queried DOI itself is
about it; otherwise it is only counted when the queried work does not itself look like a
notice document. Skipping that check would mark every retraction notice in the literature as
retracted.

**OpenAlex** carries ``is_retracted`` on the work object, which is a straight cross-check of
the Crossref retraction signal. When the two disagree, the disagreement is REPORTED
(``conflict: true``) and the stronger verdict is taken. Under-reporting a retraction is the
dangerous error on this axis, and unlike axis (a) the verdict is not refusal-grade on its
own: it surfaces at a human checkpoint.

The connector layer's clean-negative / source-error split carries through unchanged. If
every status source errors, the entry is ``checked: false`` and its ``current`` verdict must
NOT be presented as a clean bill of health: an unchecked status is an absence of evidence,
not evidence of currency.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import PARSER_VERSION, __version__
from .connectors import BaseConnector, SourceError, create_connector
from .connectors.crossref import UPDATE_TO_KEY, UPDATED_BY_KEY
from .model import CSLRecord, normalize_doi
from .snapshots import SnapshotSession

__all__ = [
    "DEFAULT_STATUS_SOURCES",
    "STATUS_PROTOCOL_VERSION",
    "STATUS_SCHEMA_VERSION",
    "Notice",
    "StatusEntry",
    "StatusSourceOutcome",
    "build_report",
    "check_status",
    "check_status_async",
    "classify",
]

#: Version of the report shape (``core/schemas/status-report.schema.json``).
STATUS_SCHEMA_VERSION = "1.0"

#: Version of the axis (b) decision rules implemented here.
STATUS_PROTOCOL_VERSION = "1.0"

#: The two sources that carry publication-status metadata. Crossref is the authority (it
#: holds the update graph); OpenAlex is the cross-check.
DEFAULT_STATUS_SOURCES: tuple[str, ...] = ("crossref", "openalex")

CURRENT = "current"
CORRECTED = "corrected"
RETRACTED = "retracted"
EXPRESSION_OF_CONCERN = "expression-of-concern"

CONFIRMED = "confirmed"
NEGATIVE = "negative"
SOURCE_ERROR = "source_error"

#: Crossref update types -> the schema's notice vocabulary. Anything unlisted (``new_version``,
#: ``clarification``, ``comment``) is not status-changing and is deliberately dropped.
_CROSSREF_UPDATE_TYPES: dict[str, str] = {
    "retraction": "retraction",
    "partial_retraction": "retraction",
    "withdrawal": "withdrawal",
    "removal": "removal",
    "expression_of_concern": "expression-of-concern",
    "expression-of-concern": "expression-of-concern",
    "correction": "correction",
    "corrigendum": "correction",
    "erratum": "erratum",
    "addendum": "addendum",
}

#: Notice -> verdict, and the strength ordering. The strongest notice on a work wins.
#: An expression of concern is reported separately and is NEVER collapsed into a retraction:
#: it is a weaker signal, and treating it as a retraction would misrepresent the record.
_NOTICE_VERDICT: dict[str, str] = {
    "retraction": RETRACTED,
    "withdrawal": RETRACTED,
    "removal": RETRACTED,
    "expression-of-concern": EXPRESSION_OF_CONCERN,
    "correction": CORRECTED,
    "erratum": CORRECTED,
    "addendum": CORRECTED,
}

_VERDICT_RANK: dict[str, int] = {
    CURRENT: 0,
    CORRECTED: 1,
    EXPRESSION_OF_CONCERN: 2,
    RETRACTED: 3,
}

#: Title of a NOTICE document (the retraction notice, the corrigendum), as opposed to the
#: article that was retracted. The separator after the leading word varies by publisher
#: ("Retraction: X", "Retraction-X", "Retraction of X", "Retraction notice to X"), so the
#: match is on the leading word with a word boundary rather than on a fixed prefix.
_NOTICE_TITLE_RE = re.compile(
    r"^(retraction|partial retraction|notice of retraction|expression of concern|"
    r"editorial expression of concern|corrigendum|corrigenda|erratum|errata|"
    r"withdrawal notice|removal notice|addendum)\b",
    re.IGNORECASE,
)

#: Title prefixes publishers stamp on the RETRACTED ARTICLE itself. One colon apart from a
#: notice, and the opposite verdict, so they are excluded before the notice test runs.
_RETRACTED_ARTICLE_PREFIXES: tuple[str, ...] = (
    "retracted",
    "withdrawn",
    "removed",
)

_ERROR_TYPE_MAP = {
    "timeout": "timeout",
    "rate_limit": "rate_limit",
    "server_error": "http_error",
    "network": "network",
    "bad_response": "parse_error",
    "config": "auth_error",
}


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Notice:
    """One editorial notice attached to a work by one source."""

    type: str
    source: str
    doi: str = ""
    label: str = ""
    date: str = ""
    url: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "source": self.source,
            "doi": self.doi or None,
            "label": self.label or None,
            "date": self.date or None,
            "url": self.url or None,
        }

    def to_block_dict(self) -> dict[str, Any]:
        """The projection carried inside a verification report entry (axis (a) schema)."""
        return {
            "type": self.type,
            "source": self.source,
            "doi": self.doi or None,
            "label": self.label or None,
            "date": self.date or None,
        }


@dataclass
class StatusSourceOutcome:
    """What one status source said. Same three-state vocabulary as axis (a)."""

    source: str
    outcome: str
    is_retracted: bool | None = None
    notice_count: int = 0
    error: dict[str, Any] | None = None

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "source": self.source,
            "outcome": self.outcome,
            "notice_count": self.notice_count,
        }
        if self.is_retracted is not None:
            out["is_retracted"] = self.is_retracted
        if self.outcome == SOURCE_ERROR:
            out["error"] = self.error or {"type": "network", "message": "unspecified failure"}
        return out


@dataclass
class StatusEntry:
    """The axis (b) verdict for one work, with every source outcome retained."""

    id: str
    verdict: str
    checked: bool
    reason: str
    notices: list[Notice] = field(default_factory=list)
    sources: list[StatusSourceOutcome] = field(default_factory=list)
    doi: str = ""
    key: str = ""
    title: str = ""
    conflict: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "doi": self.doi or None,
            "key": self.key or None,
            "title": self.title or None,
            "verdict": self.verdict,
            "checked": self.checked,
            "reason": self.reason,
            "conflict": self.conflict,
            "notices": [n.to_json_dict() for n in self.notices],
            "sources": [s.to_json_dict() for s in self.sources],
        }

    def to_block_dict(self) -> dict[str, Any]:
        """The per-entry projection carried by the axis (a) verification report."""
        return {
            "verdict": self.verdict,
            "checked": self.checked,
            "notices": [n.to_block_dict() for n in self.notices],
            "sources": [s.source for s in self.sources],
        }


# ---------------------------------------------------------------------------
# Notice extraction
# ---------------------------------------------------------------------------


def _looks_like_a_notice(record: CSLRecord) -> bool:
    """Is this work itself an editorial notice about ANOTHER work?

    "Retraction-Hydroxychloroquine or chloroquine ... a multinational registry analysis" is
    the NOTICE, and it is a current document. "RETRACTED: Hydroxychloroquine or chloroquine
    ..." is the article that was retracted. One word apart, opposite verdicts, and both carry
    a Crossref ``update-to`` entry of type ``retraction``. Telling them apart is the whole job
    of this function, and getting it backwards would report every retraction notice in the
    literature as retracted.
    """
    title = record.title.casefold().strip()
    if not title or title.startswith(_RETRACTED_ARTICLE_PREFIXES):
        return False
    return bool(_NOTICE_TITLE_RE.match(title))


def _partner_dois(record: CSLRecord) -> set[str]:
    """The works this one UPDATES: the articles it is a notice for.

    Non-empty exactly when the work claims to update something other than itself, which is
    what a notice document does.
    """
    own = record.DOI
    partners = {
        normalize_doi(entry.get("DOI")) for entry in _entries(record.extra.get(UPDATE_TO_KEY))
    }
    return {doi for doi in partners if doi and doi != own}


def _crossref_notices(record: CSLRecord, doi: str, *, is_notice: bool = False) -> list[Notice]:
    """Every status-changing notice Crossref attaches to this work.

    For an ORDINARY work, both arrays count. ``updated-by`` is the direction that says "this
    paper was retracted"; ``update-to`` is deposited on the retracted article too (Elsevier),
    pointing at its notice or at itself.

    For a NOTICE document, the pairing with the article it updates is deposited in BOTH
    directions with the SAME type, and neither direction is usable. Crossref holds this for
    the Lancet Surgisphere retraction notice: ``update-to`` carries ``retraction -> the
    paper`` (correct: this notice retracts it) and ``updated-by`` carries ``retraction -> the
    paper`` as well. Read either one and the notice itself classifies as retracted, which is
    exactly backwards. So every entry pointing at a partner it updates is dropped, and so is
    the whole ``update-to`` array (by definition it describes other works).

    What survives that filter is a notice from a THIRD document, and it is real. The Lancet
    Neurology expression-of-concern notice ``10.1016/s1474-4422(22)00030-8`` was itself later
    flagged by a separate expression of concern from a different DOI: a notice document that
    genuinely acquired a status of its own. Dropping the whole update graph for notices, as
    an earlier cut of this function did, would have silently lost that.
    """
    notices: list[Notice] = []
    partners = _partner_dois(record) if is_notice else set()

    for entry in _entries(record.extra.get(UPDATED_BY_KEY)):
        if normalize_doi(entry.get("DOI")) in partners:
            continue  # the mirror of this notice's own pairing, not an update to it
        notice = _to_notice(entry, "crossref")
        if notice is not None:
            notices.append(notice)

    if not is_notice:
        for entry in _entries(record.extra.get(UPDATE_TO_KEY)):
            notice = _to_notice(entry, "crossref")
            if notice is not None:
                notices.append(notice)

    return _dedupe(notices)


def _entries(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [e for e in value if isinstance(e, Mapping)]


def _to_notice(entry: Mapping[str, Any], source: str) -> Notice | None:
    kind = _CROSSREF_UPDATE_TYPES.get(str(entry.get("type") or "").strip().lower())
    if kind is None:
        return None
    return Notice(
        type=kind,
        source=source,
        doi=normalize_doi(entry.get("DOI")),
        label=str(entry.get("label") or ""),
        date=str(entry.get("updated") or ""),
    )


def _dedupe(notices: Iterable[Notice]) -> list[Notice]:
    """Drop duplicate (type, doi) notices, preserving order. Crossref deposits both ways."""
    seen: set[tuple[str, str]] = set()
    out: list[Notice] = []
    for notice in notices:
        key = (notice.type, notice.doi)
        if key in seen:
            continue
        seen.add(key)
        out.append(notice)
    return out


def classify(notices: Sequence[Notice]) -> str:
    """The verdict implied by a set of notices: the strongest one wins."""
    verdict = CURRENT
    for notice in notices:
        candidate = _NOTICE_VERDICT.get(notice.type, CURRENT)
        if _VERDICT_RANK[candidate] > _VERDICT_RANK[verdict]:
            verdict = candidate
    return verdict


# ---------------------------------------------------------------------------
# Querying
# ---------------------------------------------------------------------------


def _crossref_outcome(
    record: CSLRecord, doi: str, *, is_notice: bool
) -> tuple[StatusSourceOutcome, list[Notice]]:
    notices = _crossref_notices(record, doi, is_notice=is_notice)
    outcome = StatusSourceOutcome(
        "crossref",
        CONFIRMED if notices else NEGATIVE,
        notice_count=len(notices),
    )
    return outcome, notices


def _openalex_outcome(
    record: CSLRecord, doi: str, *, is_notice: bool
) -> tuple[StatusSourceOutcome, list[Notice]]:
    """OpenAlex's ``is_retracted``, with one carve-out that the data forces.

    OpenAlex sets ``is_retracted`` on retraction NOTICES as well as on the papers they
    retract (it does so for the Lancet Surgisphere notice, for one). Taken at face value that
    would report the notice itself as retracted. So when the work is an editorial notice, the
    flag is recorded verbatim on the source outcome but produces no notice of its own; the
    disagreement with Crossref then surfaces as ``conflict: true`` rather than being silently
    resolved either way.
    """
    retracted = record.is_retracted
    if retracted and not is_notice:
        notice = Notice(type="retraction", source="openalex", doi=normalize_doi(doi))
        return (
            StatusSourceOutcome("openalex", CONFIRMED, is_retracted=True, notice_count=1),
            [notice],
        )
    return StatusSourceOutcome("openalex", NEGATIVE, is_retracted=retracted), []


def _error_dict(exc: SourceError) -> dict[str, Any]:
    return {
        "type": _ERROR_TYPE_MAP.get(exc.kind.value, "network"),
        "message": exc.message or str(exc),
        "http_status": exc.status_code,
    }


async def check_status_async(
    doi: str,
    connectors: Sequence[BaseConnector],
    *,
    key: str = "",
    title: str = "",
) -> StatusEntry:
    """The axis (b) verdict for one DOI, cross-checked across the given connectors.

    Connectors that carry no status metadata (arXiv, OpenCitations, Unpaywall) are skipped:
    they are not asked, so they contribute neither a notice nor a silence. Only Crossref and
    OpenAlex are consulted, and the entry records which.
    """
    normalized = normalize_doi(doi)

    # Pass 1: resolve the work at every status source. Both sources have to be in hand before
    # either can be interpreted, because whether this work IS an editorial notice changes how
    # both the Crossref update graph and the OpenAlex flag must be read.
    resolved: list[tuple[str, CSLRecord | None, SourceError | None]] = []
    for connector in connectors:
        if connector.name not in ("crossref", "openalex"):
            continue  # arXiv, Unpaywall and friends carry no status metadata; not asked
        try:
            resolved.append((connector.name, await connector.resolve_doi(normalized), None))
        except SourceError as exc:
            resolved.append((connector.name, None, exc))

    is_notice = _notice_document(resolved)

    # Pass 2: classify, in the order the sources were queried.
    outcomes: list[StatusSourceOutcome] = []
    notices: list[Notice] = []
    for name, record, error in resolved:
        if error is not None:
            outcomes.append(StatusSourceOutcome(name, SOURCE_ERROR, error=_error_dict(error)))
            continue
        if record is None:
            # A clean negative: the source answered and holds no such DOI. No notice can be
            # asserted from it, but the answer is clean, so the entry still counts as checked.
            outcomes.append(StatusSourceOutcome(name, NEGATIVE))
            continue
        if name == "crossref":
            outcome, found = _crossref_outcome(record, normalized, is_notice=is_notice)
        else:
            outcome, found = _openalex_outcome(record, normalized, is_notice=is_notice)
        outcomes.append(outcome)
        notices.extend(found)

    notices = _dedupe(notices)
    checked = any(o.outcome != SOURCE_ERROR for o in outcomes)
    verdict = classify(notices) if checked else CURRENT
    conflict = _conflicted(outcomes, notices)

    if not outcomes:
        reason = "no status source was queried, so the status is unchecked"
    elif not checked:
        reason = (
            "every status source errored, so no clean answer was obtained; "
            "an unchecked status is not evidence of currency"
        )
    elif is_notice and verdict == CURRENT:
        reason = (
            "this work is itself an editorial notice about another work, so the update "
            "metadata it carries describes that work, not this one"
        )
    elif verdict == CURRENT:
        reason = f"no editorial notice found by {', '.join(o.source for o in outcomes)}"
    else:
        kinds = ", ".join(sorted({n.type for n in notices}))
        sources = ", ".join(sorted({n.source for n in notices}))
        reason = f"{kinds} notice reported by {sources}"
    if conflict:
        reason += "; status sources disagree, and the disagreement is reported, not resolved away"

    return StatusEntry(
        id=normalized or key or "unknown",
        verdict=verdict,
        checked=checked,
        reason=reason,
        notices=notices,
        sources=outcomes,
        doi=normalized,
        key=key,
        title=title,
        conflict=conflict,
    )


def _notice_document(
    resolved: Sequence[tuple[str, CSLRecord | None, SourceError | None]],
) -> bool:
    """Is the queried work an editorial notice about another work?

    Two signals must agree: the title reads as a notice, AND (when Crossref answered) the
    work is linked to a different DOI in its update graph. A research article about
    retractions carries the first signal and not the second, and must not be treated as a
    notice; a real notice carries both.
    """
    records = [r for _, r, _ in resolved if r is not None]
    if not any(_looks_like_a_notice(r) for r in records):
        return False
    crossref = next((r for name, r, _ in resolved if name == "crossref" and r is not None), None)
    if crossref is None:
        return True  # no update graph to consult; the title is all the evidence there is
    return bool(_partner_dois(crossref))


def _conflicted(outcomes: Sequence[StatusSourceOutcome], notices: Sequence[Notice]) -> bool:
    """Do the sources disagree about retraction?

    Only a genuine contradiction counts. OpenAlex not holding the DOI at all (a clean
    negative with ``is_retracted`` unset) is silence, not disagreement.
    """
    openalex = next((o for o in outcomes if o.source == "openalex"), None)
    crossref = next((o for o in outcomes if o.source == "crossref"), None)
    if openalex is None or crossref is None:
        return False
    if openalex.outcome == SOURCE_ERROR or crossref.outcome == SOURCE_ERROR:
        return False
    if openalex.is_retracted is None:
        return False
    crossref_retracted = any(
        n.source == "crossref" and _NOTICE_VERDICT.get(n.type) == RETRACTED for n in notices
    )
    return bool(openalex.is_retracted) != crossref_retracted


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _schema_version(value: str) -> str:
    return value if "." in value else f"{value}.0"


def build_report(
    entries: Sequence[StatusEntry],
    *,
    input_kind: str = "doi",
    input_path: str = "",
    input_doi: str = "",
    run_id: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    """Assemble the axis (b) report (``core/schemas/status-report.schema.json``)."""
    status = {CURRENT: 0, CORRECTED: 0, RETRACTED: 0, EXPRESSION_OF_CONCERN: 0}
    for entry in entries:
        status[entry.verdict] += 1
    payload: dict[str, Any] = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "protocol_version": STATUS_PROTOCOL_VERSION,
        "versions": {"core": __version__, "parser": _schema_version(PARSER_VERSION)},
        "input": {"kind": input_kind},
        "entries": [e.to_json_dict() for e in entries],
        "summary": {
            "total": len(entries),
            "status": status,
            "unchecked": sum(1 for e in entries if not e.checked),
            "conflicts": sum(1 for e in entries if e.conflict),
        },
    }
    if input_kind == "bib" and input_path:
        payload["input"]["path"] = input_path
    if input_kind == "doi" and input_doi:
        payload["input"]["doi"] = input_doi
    if run_id:
        payload["run_id"] = run_id
    if generated_at:
        payload["generated_at"] = generated_at
    return payload


def check_status(
    dois: Iterable[str],
    *,
    sources: Sequence[str] = DEFAULT_STATUS_SOURCES,
    snapshots: SnapshotSession | None = None,
    **report_kwargs: Any,
) -> dict[str, Any]:
    """Synchronous entry point: check every DOI and build the axis (b) report."""

    async def run() -> dict[str, Any]:
        connectors = [create_connector(name, snapshots=snapshots) for name in sources]
        try:
            entries = [await check_status_async(doi, connectors) for doi in dois]
        finally:
            for connector in connectors:
                await connector.aclose()
        return build_report(entries, **report_kwargs)

    return asyncio.run(run())
