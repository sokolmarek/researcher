"""Concurrent fan-out search with per-source error isolation.

The point of this module is the isolation, not the concurrency. One failing source must
NEVER fail the query. Semantic Scholar rate-limits the keyless tier most of the time;
OpenCitations has outages; PubMed's E-utilities throttle. A kernel that answers "the search
failed" because one of six indexes returned a 429 is a kernel nobody can use. So:

* Every source is queried concurrently (``asyncio.gather`` over httpx async clients).
* A source that raises :class:`~researcher_core.connectors.base.SourceError` contributes a
  :class:`SourceWarning` to :attr:`SearchResult.warnings` and NOTHING ELSE. Every other
  source still returns its records.
* A source that raises anything unexpected is isolated the same way, under the
  :data:`UNEXPECTED_KIND` kind, rather than taking the process down.
* A source that does not implement ``search`` at all (OpenCitations, Unpaywall) is skipped
  with an ``unsupported`` outcome and no warning: nothing was asked of it, so there is
  nothing to report.

The one exception, and it is deliberate:
:class:`~researcher_core.snapshots.SnapshotMissingError` is re-raised, never converted into
a warning. A gap in the snapshot store is a defect in the test fixtures, not a source
outage, and swallowing it here would let the offline suite silently test nothing.

The warnings are also what makes a search result honest downstream: a result set assembled
while two indexes were down is not the same evidence as one assembled with all six
answering, and ``verify.py`` (D9) has to be able to tell those apart.

Determinism (D15): sources are queried in a fixed order and their records are concatenated
in that order before dedupe, so the same snapshots produce the same result set, in the same
order, every time. Concurrency changes when each response arrives, never where it lands.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .connectors import (
    BaseConnector,
    SourceError,
    UnsupportedOperation,
    create_connector,
)
from .dedupe import DedupDecision, dedupe
from .model import CSLRecord
from .rank import DEFAULT_WEIGHTS, RankWeights, rank_records
from .snapshots import SnapshotMissingError, SnapshotSession

__all__ = [
    "DEFAULT_SEARCH_SOURCES",
    "OUTCOME_ERROR",
    "OUTCOME_OK",
    "OUTCOME_UNSUPPORTED",
    "UNEXPECTED_KIND",
    "SearchResult",
    "SourceOutcome",
    "SourceWarning",
    "fan_out",
    "search",
    "search_sync",
]

#: The default fan-out: the three keyless indexes that need no configuration and between
#: them cover journals (Crossref), the open graph (OpenAlex), and preprints (arXiv).
#: OpenAlex and Crossref alone satisfy the D9 two-confirmation identity gate.
DEFAULT_SEARCH_SOURCES: tuple[str, ...] = ("openalex", "crossref", "arxiv")

#: Per-source outcome states. A source is never silently absent from the report.
OUTCOME_OK = "ok"
OUTCOME_ERROR = "error"
OUTCOME_UNSUPPORTED = "unsupported"

#: Warning kind for an exception that is not a SourceError. SourceError kinds come from
#: :class:`~researcher_core.connectors.base.SourceErrorKind`; this one covers the bug case,
#: which is isolated rather than fatal so that one broken parser cannot kill a whole query.
UNEXPECTED_KIND = "unexpected"


@dataclass(frozen=True)
class SourceWarning:
    """One source's failure, carried alongside the results the other sources returned."""

    source: str
    operation: str
    kind: str
    message: str
    status_code: int | None = None

    @classmethod
    def from_source_error(cls, error: SourceError, *, operation: str) -> SourceWarning:
        return cls(
            source=error.source,
            operation=operation,
            kind=error.kind.value,
            message=error.message,
            status_code=error.status_code,
        )

    @classmethod
    def from_exception(
        cls, source: str, error: BaseException, *, operation: str
    ) -> SourceWarning:
        return cls(
            source=source,
            operation=operation,
            kind=UNEXPECTED_KIND,
            message=f"{type(error).__name__}: {error}",
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "operation": self.operation,
            "kind": self.kind,
            "message": self.message,
            "status_code": self.status_code,
        }


@dataclass(frozen=True)
class SourceOutcome:
    """What one source did: answered, failed, or was never asked."""

    source: str
    status: str
    record_count: int = 0
    warning: SourceWarning | None = None

    @property
    def ok(self) -> bool:
        return self.status == OUTCOME_OK

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "source": self.source,
            "status": self.status,
            "record_count": self.record_count,
        }
        if self.warning is not None:
            out["warning"] = self.warning.to_json_dict()
        return out


@dataclass
class SearchResult:
    """Deduplicated, ranked records plus the full per-source story of how they were got."""

    query: str = ""
    records: list[CSLRecord] = field(default_factory=list)
    warnings: list[SourceWarning] = field(default_factory=list)
    outcomes: list[SourceOutcome] = field(default_factory=list)
    decisions: list[DedupDecision] = field(default_factory=list)
    #: Records retrieved before dedupe. PRISMA "identified" counts derive from this.
    retrieved_count: int = 0

    @property
    def sources_queried(self) -> list[str]:
        return [o.source for o in self.outcomes]

    @property
    def sources_ok(self) -> list[str]:
        return [o.source for o in self.outcomes if o.status == OUTCOME_OK]

    @property
    def sources_failed(self) -> list[str]:
        return [o.source for o in self.outcomes if o.status == OUTCOME_ERROR]

    @property
    def duplicates_removed(self) -> int:
        return len(self.decisions)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "records": [r.to_csl_json() for r in self.records],
            "warnings": [w.to_json_dict() for w in self.warnings],
            "sources": [o.to_json_dict() for o in self.outcomes],
            "dedup_decisions": [d.to_json_dict() for d in self.decisions],
            "counts": {
                "retrieved": self.retrieved_count,
                "deduplicated": len(self.records),
                "duplicates_removed": self.duplicates_removed,
            },
        }


# ---------------------------------------------------------------------------
# Fan-out
# ---------------------------------------------------------------------------


async def _search_one(
    connector: BaseConnector,
    query: str,
    *,
    limit: int,
    since: int | None,
) -> tuple[list[CSLRecord], SourceOutcome]:
    """Query one source. Never raises, except on a missing snapshot (which must be loud)."""
    name = connector.name
    if not connector.supports("search"):
        return [], SourceOutcome(source=name, status=OUTCOME_UNSUPPORTED)

    try:
        records = await connector.search(query, limit=limit, since=since)
    except SnapshotMissingError:
        # Never isolated. A gap in the snapshot store is a fixture defect, not an outage,
        # and degrading it to a warning would make the offline suite pass vacuously.
        raise
    except UnsupportedOperation:
        return [], SourceOutcome(source=name, status=OUTCOME_UNSUPPORTED)
    except SourceError as exc:
        warning = SourceWarning.from_source_error(exc, operation="search")
        return [], SourceOutcome(source=name, status=OUTCOME_ERROR, warning=warning)
    except Exception as exc:  # noqa: BLE001 - isolation is the whole point of this module
        warning = SourceWarning.from_exception(name, exc, operation="search")
        return [], SourceOutcome(source=name, status=OUTCOME_ERROR, warning=warning)

    for position, record in enumerate(records):
        # The per-source rank feeds rank.py's reciprocal-rank-fusion relevance term, and
        # dedupe.py unions these dicts on merge, which is how cross-source agreement
        # survives deduplication.
        ranks = record.extra.get("source_ranks")
        if not isinstance(ranks, dict):
            ranks = {}
        ranks[name] = position
        record.extra["source_ranks"] = ranks

    return list(records), SourceOutcome(
        source=name, status=OUTCOME_OK, record_count=len(records)
    )


async def fan_out(
    query: str,
    connectors: Sequence[BaseConnector],
    *,
    limit: int = 25,
    since: int | None = None,
) -> tuple[list[CSLRecord], list[SourceOutcome]]:
    """Query every connector concurrently, isolating failures per source.

    Returns the concatenated records (in connector order, not in completion order, so the
    result is deterministic) and one :class:`SourceOutcome` per connector.
    """
    if not connectors:
        return [], []

    tasks = [
        _search_one(connector, query, limit=limit, since=since) for connector in connectors
    ]
    results = await asyncio.gather(*tasks)

    records: list[CSLRecord] = []
    outcomes: list[SourceOutcome] = []
    for source_records, outcome in results:
        records.extend(source_records)
        outcomes.append(outcome)
    return records, outcomes


async def search(
    query: str,
    *,
    sources: Iterable[str] | None = None,
    limit: int = 25,
    since: int | None = None,
    connectors: Sequence[BaseConnector] | None = None,
    session: SnapshotSession | None = None,
    weights: RankWeights = DEFAULT_WEIGHTS,
    rank: bool = True,
) -> SearchResult:
    """Fan out, dedupe, rank.

    ``connectors`` lets a caller (and every test in this suite) inject connectors that are
    already bound to a snapshot session; when it is omitted, connectors are built from the
    registry for ``sources`` and closed again before returning.
    """
    if connectors is None:
        names = list(sources) if sources is not None else list(DEFAULT_SEARCH_SOURCES)
        built = [_build(name, session) for name in names]
        try:
            return await search(
                query,
                limit=limit,
                since=since,
                connectors=built,
                weights=weights,
                rank=rank,
            )
        finally:
            for connector in built:
                await connector.aclose()

    raw, outcomes = await fan_out(query, connectors, limit=limit, since=since)
    merged = dedupe(raw)
    records = (
        rank_records(merged.records, weights=weights) if rank else list(merged.records)
    )
    return SearchResult(
        query=query,
        records=records,
        warnings=[o.warning for o in outcomes if o.warning is not None],
        outcomes=outcomes,
        decisions=merged.decisions,
        retrieved_count=len(raw),
    )


def search_sync(query: str, **kwargs: Any) -> SearchResult:
    """Blocking :func:`search`, for the CLI and for callers with no event loop."""
    return asyncio.run(search(query, **kwargs))


def _build(name: str, session: SnapshotSession | None) -> BaseConnector:
    """Instantiate one connector, sharing the caller's snapshot session when there is one."""
    if session is None:
        return create_connector(name)
    return create_connector(name, snapshots=session)
