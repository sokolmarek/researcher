"""The hardened, append-only provenance ledger (D19).

The event record is exactly the nine fields D19 specifies, and nothing else::

    {schema_version, run_id, protocol_version, event_id, ts, type, payload,
     source_response_hashes: [...], versions: {core, parser, model?}}

Every event written here validates against ``core/schemas/provenance-event.schema.json``.

Four properties are load-bearing, so they are enforced in this module rather than left to
the discipline of callers:

1. **SQLite transactions are the primary store.** Writes go through ``BEGIN IMMEDIATE``
   on a WAL-mode database with a busy timeout, which is safe under concurrent writers and
   friendly to Windows file locking (D5). The v1 append-only-JSONL write path is
   superseded: JSONL is an EXPORT format (:meth:`ProvenanceLedger.export_jsonl`), never
   the write path.

2. **The ledger is append-only.** There is no update path and no delete path in this API.
   Not discouraged: absent. The only mutation is :meth:`ProvenanceLedger.append` (and its
   batched sibling :meth:`ProvenanceLedger.append_many`), and appending an ``event_id``
   that already exists raises :class:`DuplicateEventError` rather than overwriting.

3. **``ts`` is caller-supplied, never self-generated.** Nothing in this module reads the
   clock. A ledger written during a replay of the same snapshots, configuration, and
   parser version is byte-identical to the original (D15). A ``time.time()`` call in here
   would silently destroy that, so there is not one.

4. **PRISMA counts are DERIVED, never stored** (D10). :meth:`ProvenanceLedger.prisma`
   aggregates the events themselves. A stored count can drift away from the events it
   claims to summarize; a derived one cannot.

Event vocabulary (closed, per the schema): ``retrieval``, ``record_lineage``,
``dedup_decision``, ``screening_decision``, ``artifact_hash``, ``review``, ``gate``. M2
emits the first three; the rest are defined now because M3 (compile gate) and M4 (dual
screening) add them.

Payload conventions the derivations in this module rely on (the payload itself is
deliberately open in the schema, so these are conventions, not schema constraints):

* ``retrieval``: ``{"source", "query", "record_count", "record_ids": [...]}``. Either
  ``record_count`` or ``record_ids`` must be present; ``record_ids`` wins when both are.
* ``dedup_decision``: ``{"winner", "losers": [...], "reason", "similarity"}``. Every id in
  ``losers`` is one record removed as a duplicate. ``{"removed_count": n}`` is accepted as
  a fallback when the ids are not available.
* ``record_lineage``: ``{"artifact_id", "artifact_hash", "artifact_type", "inputs": [...]}``.
  See :mod:`researcher_core.lineage`, which reads these.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from . import PARSER_VERSION, PROTOCOL_VERSION, __version__
from .cache import user_cache_root
from .model import canonical_json, content_hash

__all__ = [
    "EVENT_TYPES",
    "M2_EVENT_TYPES",
    "PROVENANCE_SCHEMA_VERSION",
    "DuplicateEventError",
    "derive_prisma",
    "PrismaCounts",
    "ProvenanceError",
    "ProvenanceEvent",
    "ProvenanceLedger",
    "RunContext",
    "Versions",
    "default_ledger_path",
    "load_jsonl",
    "normalize_hash",
    "normalize_ts",
    "normalize_version",
    "parse_jsonl",
]

#: Version of the event record shape itself. Bump the minor for additive fields, the major
#: for anything that invalidates a stored ledger.
PROVENANCE_SCHEMA_VERSION = "1.0"

#: The closed event vocabulary. Mirrors the ``eventType`` enum in
#: ``core/schemas/provenance-event.schema.json``; the two must not drift apart.
EVENT_TYPES: tuple[str, ...] = (
    "retrieval",
    "record_lineage",
    "dedup_decision",
    "screening_decision",
    "artifact_hash",
    "review",
    "gate",
    # M4 (the systematic-review vertical) adds the protocol and screening lifecycle.
    "protocol_locked",
    "amendment",
    "adjudication",
)

#: The event types M2 actually emits. The others exist for M3 and M4.
M2_EVENT_TYPES: tuple[str, ...] = ("retrieval", "record_lineage", "dedup_decision")

#: The event types M4 adds on top of what M2 and M3 emit.
M4_EVENT_TYPES: tuple[str, ...] = (
    "protocol_locked",
    "amendment",
    "screening_decision",
    "adjudication",
)

_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?([-+.][0-9A-Za-z.-]+)?$")
_HASH_RE = re.compile(r"^(sha256:)?[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProvenanceError(RuntimeError):
    """A provenance event or ledger operation was rejected."""


class DuplicateEventError(ProvenanceError):
    """An event_id already present in the ledger was appended again.

    Append-only means an existing event is never overwritten, so this is an error rather
    than an update. The default ``event_id`` is a content hash of the event body, so the
    common way to hit this is genuinely appending the same event twice.
    """

    def __init__(self, event_id: str) -> None:
        self.event_id = event_id
        super().__init__(
            f"Event {event_id!r} is already in the ledger. The ledger is append-only: "
            "existing events are never updated or replaced. Supply a distinct event_id "
            "if this is a genuinely different event."
        )


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def normalize_version(value: Any, *, label: str = "version") -> str:
    """Coerce a version to the schema's ``versionString`` form (``MAJOR.MINOR[.PATCH]``).

    The package pins ``PARSER_VERSION = "1"`` and ``PROTOCOL_VERSION = "1"``, which are
    one-component strings; the schema requires at least two components. A bare integer is
    therefore widened (``"1"`` -> ``"1.0"``) rather than written out invalid. Anything
    still not matching the pattern raises, because an event that cannot validate must not
    reach the store.
    """
    text = str(value).strip()
    if not text:
        raise ProvenanceError(f"{label} must be a non-empty version string.")
    if text.isdigit():
        text = f"{text}.0"
    if not _VERSION_RE.match(text):
        raise ProvenanceError(
            f"{label} {value!r} is not a valid version string "
            "(expected MAJOR.MINOR[.PATCH], e.g. '1.0' or '0.1.0')."
        )
    return text


def normalize_hash(value: Any, *, label: str = "source_response_hash") -> str:
    """Validate a SHA-256 content hash, hex encoded, optionally ``sha256:``-prefixed.

    The value is returned unchanged (prefix and all): the ledger stores what the caller
    supplied, and :mod:`researcher_core.lineage` strips the prefix when it joins.
    """
    text = str(value).strip()
    if not _HASH_RE.match(text):
        raise ProvenanceError(
            f"{label} {value!r} is not a SHA-256 content hash "
            "(64 lowercase hex characters, optionally prefixed with 'sha256:')."
        )
    return text


def normalize_ts(value: str | datetime) -> str:
    """Validate a CALLER-SUPPLIED RFC 3339 timestamp and return it verbatim.

    This function never reads the clock, and neither does anything else in this module.
    That is the whole point: a self-generated timestamp would make two replays of the same
    run differ, and D15 forbids that. A :class:`datetime` is accepted for convenience but
    must be timezone-aware.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ProvenanceError(
                "ts must be timezone-aware; a naive datetime has no defined instant."
            )
        text = value.isoformat()
        return text[:-6] + "Z" if text.endswith("+00:00") else text

    text = str(value).strip()
    if not text:
        raise ProvenanceError(
            "ts is required and is caller-supplied; the ledger never generates it "
            "(a self-generated timestamp would break replay determinism, D15)."
        )
    probe = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(probe)
    except ValueError as exc:
        raise ProvenanceError(
            f"ts {value!r} is not an RFC 3339 timestamp (e.g. '2026-07-14T12:00:00Z')."
        ) from exc
    if parsed.tzinfo is None:
        raise ProvenanceError(
            f"ts {value!r} carries no UTC offset; RFC 3339 requires one "
            "(e.g. '2026-07-14T12:00:00Z')."
        )
    return text


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Versions:
    """The component versions in force when an event was written.

    With the snapshot and the configuration, these are the three things D15 needs for a
    byte-identical replay. ``model`` is present only when a model was involved; purely
    deterministic events omit it, and the schema forbids any other key.
    """

    core: str = __version__
    parser: str = PARSER_VERSION
    model: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "core", normalize_version(self.core, label="versions.core"))
        object.__setattr__(
            self, "parser", normalize_version(self.parser, label="versions.parser")
        )
        object.__setattr__(self, "model", str(self.model or "").strip())

    def to_json_dict(self) -> dict[str, str]:
        out = {"core": self.core, "parser": self.parser}
        if self.model:
            out["model"] = self.model
        return out

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any] | Versions | None) -> Versions:
        if isinstance(data, Versions):
            return data
        if data is None:
            return cls()
        unknown = set(data) - {"core", "parser", "model"}
        if unknown:
            raise ProvenanceError(
                f"versions carries unknown key(s) {sorted(unknown)}; the schema permits "
                "only core, parser, and (optionally) model."
            )
        return cls(
            core=str(data.get("core") or __version__),
            parser=str(data.get("parser") or PARSER_VERSION),
            model=str(data.get("model") or ""),
        )


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceEvent:
    """One record in the ledger. Immutable, and validated on construction."""

    run_id: str
    type: str
    ts: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_response_hashes: tuple[str, ...] = ()
    versions: Versions = field(default_factory=Versions)
    protocol_version: str = PROTOCOL_VERSION
    event_id: str = ""
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        run_id = str(self.run_id).strip()
        if not run_id:
            raise ProvenanceError("run_id is required: it groups every event of one run.")
        object.__setattr__(self, "run_id", run_id)

        if self.type not in EVENT_TYPES:
            raise ProvenanceError(
                f"Unknown event type {self.type!r}. The vocabulary is closed: "
                f"{', '.join(EVENT_TYPES)}."
            )

        object.__setattr__(self, "ts", normalize_ts(self.ts))
        object.__setattr__(
            self,
            "protocol_version",
            normalize_version(self.protocol_version, label="protocol_version"),
        )
        object.__setattr__(
            self,
            "schema_version",
            normalize_version(self.schema_version, label="schema_version"),
        )

        if not isinstance(self.payload, Mapping):
            raise ProvenanceError("payload must be a JSON object.")
        object.__setattr__(self, "payload", dict(self.payload))

        object.__setattr__(self, "versions", Versions.from_json_dict(self.versions))

        hashes = tuple(normalize_hash(h) for h in self.source_response_hashes)
        object.__setattr__(self, "source_response_hashes", hashes)

        event_id = str(self.event_id).strip()
        object.__setattr__(self, "event_id", event_id or self._derived_event_id())

    def _derived_event_id(self) -> str:
        """A content-addressed default id: the hash of everything else in the event.

        Deterministic on purpose. A UUID would make two replays of the same run produce
        different ledgers, which is exactly the non-determinism D15 rules out. Two events
        that are identical in every field ARE the same event, and appending the second
        raises :class:`DuplicateEventError`; a caller with a genuine repeat passes its own
        ``event_id``.
        """
        return content_hash(
            {
                "schema_version": self.schema_version,
                "run_id": self.run_id,
                "protocol_version": self.protocol_version,
                "ts": self.ts,
                "type": self.type,
                "payload": self.payload,
                "source_response_hashes": list(self.source_response_hashes),
                "versions": self.versions.to_json_dict(),
            }
        )

    # -- serialization -----------------------------------------------------

    def to_json_dict(self) -> dict[str, Any]:
        """The exact nine-field D19 record. No other top-level key is emitted."""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "protocol_version": self.protocol_version,
            "event_id": self.event_id,
            "ts": self.ts,
            "type": self.type,
            "payload": self.payload,
            "source_response_hashes": list(self.source_response_hashes),
            "versions": self.versions.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> ProvenanceEvent:
        missing = {
            "schema_version",
            "run_id",
            "protocol_version",
            "event_id",
            "ts",
            "type",
            "payload",
            "source_response_hashes",
            "versions",
        } - set(data)
        if missing:
            raise ProvenanceError(
                f"Event record is missing required field(s) {sorted(missing)}."
            )
        return cls(
            run_id=str(data["run_id"]),
            type=str(data["type"]),
            ts=str(data["ts"]),
            payload=dict(data["payload"] or {}),
            source_response_hashes=tuple(str(h) for h in data["source_response_hashes"] or ()),
            versions=Versions.from_json_dict(data["versions"]),
            protocol_version=str(data["protocol_version"]),
            event_id=str(data["event_id"]),
            schema_version=str(data["schema_version"]),
        )

    def canonical_json(self) -> str:
        """The canonical one-line serialization. One JSONL line, byte-stable."""
        return canonical_json(self.to_json_dict())


# ---------------------------------------------------------------------------
# Run context: the ergonomic front door for emitters
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunContext:
    """Binds ``run_id``, ``protocol_version``, and ``versions`` so emitters pass only the
    things that actually vary per event: the type, the payload, the snapshot hashes, and
    the caller's timestamp.

    ``search.py``, ``dedupe.py``, and anything else that emits events builds one of these
    per logical run.
    """

    run_id: str
    versions: Versions = field(default_factory=Versions)
    protocol_version: str = PROTOCOL_VERSION

    def event(
        self,
        type: str,
        payload: Mapping[str, Any],
        ts: str | datetime,
        *,
        source_response_hashes: Iterable[str] = (),
        event_id: str = "",
    ) -> ProvenanceEvent:
        return ProvenanceEvent(
            run_id=self.run_id,
            type=type,
            ts=normalize_ts(ts),
            payload=dict(payload),
            source_response_hashes=tuple(source_response_hashes),
            versions=self.versions,
            protocol_version=self.protocol_version,
            event_id=event_id,
        )

    def retrieval(
        self,
        ts: str | datetime,
        *,
        source: str,
        query: str,
        record_ids: Sequence[str] = (),
        record_count: int | None = None,
        source_response_hashes: Iterable[str] = (),
        extra: Mapping[str, Any] | None = None,
    ) -> ProvenanceEvent:
        """One source answered one query with N records. Feeds PRISMA "identified"."""
        payload: dict[str, Any] = {
            "source": source,
            "query": query,
            "record_count": int(record_count if record_count is not None else len(record_ids)),
        }
        if record_ids:
            payload["record_ids"] = [str(r) for r in record_ids]
        if extra:
            payload.update(dict(extra))
        return self.event(
            "retrieval", payload, ts, source_response_hashes=source_response_hashes
        )

    def dedup_decision(
        self,
        ts: str | datetime,
        *,
        winner: str,
        losers: Sequence[str],
        reason: str,
        similarity: float | None = None,
        source_response_hashes: Iterable[str] = (),
        extra: Mapping[str, Any] | None = None,
    ) -> ProvenanceEvent:
        """N records collapsed into one. Feeds PRISMA "duplicates removed"."""
        payload: dict[str, Any] = {
            "winner": str(winner),
            "losers": [str(loser) for loser in losers],
            "reason": reason,
        }
        if similarity is not None:
            payload["similarity"] = float(similarity)
        if extra:
            payload.update(dict(extra))
        return self.event(
            "dedup_decision", payload, ts, source_response_hashes=source_response_hashes
        )

    def record_lineage(
        self,
        ts: str | datetime,
        *,
        artifact_id: str,
        artifact_hash: str,
        inputs: Sequence[Mapping[str, Any]] = (),
        artifact_type: str = "record",
        source_response_hashes: Iterable[str] = (),
        extra: Mapping[str, Any] | None = None,
    ) -> ProvenanceEvent:
        """A derived artifact and the records and snapshots it came from.

        Read by :mod:`researcher_core.lineage` to answer "which snapshot produced this",
        the query the M3 compile gate needs for stale-evidence and drift detection.
        """
        payload: dict[str, Any] = {
            "artifact_id": str(artifact_id),
            "artifact_hash": str(artifact_hash),
            "artifact_type": artifact_type,
            "inputs": [dict(item) for item in inputs],
        }
        if extra:
            payload.update(dict(extra))
        return self.event(
            "record_lineage", payload, ts, source_response_hashes=source_response_hashes
        )


# ---------------------------------------------------------------------------
# PRISMA, derived
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrismaCounts:
    """PRISMA flow numbers DERIVED by aggregating events (D10). Never stored, never mutable.

    ``identified`` counts records as retrieved, duplicates included (that is what PRISMA
    means by "records identified from databases"). ``duplicates_removed`` counts the
    distinct records that dedup collapsed away, and ``deduplicated`` is the difference:
    "records after duplicates removed".

    ``screened``, ``included``, and ``excluded`` derive from ``screening_decision`` events,
    which M2 does not emit; they are zero until M4 emits them.
    """

    run_id: str = ""
    identified: int = 0
    identified_by_source: dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    deduplicated: int = 0
    screened: int = 0
    included: int = 0
    excluded: int = 0
    event_counts: dict[str, int] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "identified": self.identified,
            "identified_by_source": dict(sorted(self.identified_by_source.items())),
            "duplicates_removed": self.duplicates_removed,
            "deduplicated": self.deduplicated,
            "screened": self.screened,
            "included": self.included,
            "excluded": self.excluded,
            "event_counts": dict(sorted(self.event_counts.items())),
        }


def derive_prisma(events: Iterable[ProvenanceEvent], *, run_id: str = "") -> PrismaCounts:
    """Aggregate events into PRISMA counts. The only way counts are ever produced."""
    identified = 0
    by_source: dict[str, int] = {}
    removed_ids: set[str] = set()
    removed_countless = 0
    screened_ids: set[str] = set()
    included_ids: set[str] = set()
    excluded_ids: set[str] = set()
    event_counts: dict[str, int] = {}

    for event in events:
        event_counts[event.type] = event_counts.get(event.type, 0) + 1
        payload = event.payload

        if event.type == "retrieval":
            ids = payload.get("record_ids")
            if isinstance(ids, Sequence) and not isinstance(ids, (str, bytes)):
                count = len(ids)
            else:
                count = _as_count(payload.get("record_count"))
            identified += count
            source = str(payload.get("source") or "unknown")
            by_source[source] = by_source.get(source, 0) + count

        elif event.type == "dedup_decision":
            losers = payload.get("losers")
            if isinstance(losers, Sequence) and not isinstance(losers, (str, bytes)):
                removed_ids.update(str(loser) for loser in losers)
            else:
                removed_countless += _as_count(payload.get("removed_count"))

        elif event.type == "screening_decision":
            record_id = str(payload.get("record_id") or "")
            decision = str(payload.get("decision") or "").lower()
            if record_id:
                screened_ids.add(record_id)
                if decision in {"include", "included"}:
                    included_ids.add(record_id)
                elif decision in {"exclude", "excluded"}:
                    excluded_ids.add(record_id)

    duplicates_removed = len(removed_ids) + removed_countless
    return PrismaCounts(
        run_id=run_id,
        identified=identified,
        identified_by_source=by_source,
        duplicates_removed=duplicates_removed,
        deduplicated=max(identified - duplicates_removed, 0),
        screened=len(screened_ids),
        included=len(included_ids),
        excluded=len(excluded_ids),
        event_counts=event_counts,
    )


def _as_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(count, 0)


# ---------------------------------------------------------------------------
# JSONL export format (never the write path)
# ---------------------------------------------------------------------------


def parse_jsonl(text: str) -> list[ProvenanceEvent]:
    """Parse exported JSONL back into events. Blank lines are ignored."""
    events: list[ProvenanceEvent] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ProvenanceError(
                f"Line {number} of the JSONL export is not valid JSON: {exc}"
            ) from exc
        events.append(ProvenanceEvent.from_json_dict(data))
    return events


def load_jsonl(path: Path | str) -> list[ProvenanceEvent]:
    """Read a JSONL export from disk."""
    return parse_jsonl(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


def default_ledger_path() -> Path:
    """The ledger inside the platformdirs user data area (honors the cache-dir override)."""
    return user_cache_root() / "provenance.sqlite3"


# The event table, plus event_sources: one row per (event, snapshot) pair. That second
# table is redundant with the JSON column by design, because it turns "which events
# consumed this snapshot" into an indexed lookup instead of a scan, and lineage.py leans
# on it. It is written inside the same transaction as the event, so the two can never
# disagree.
#
# Kept as separate statements rather than one executescript, because executescript issues
# an implicit COMMIT and runs outside the transaction we open, which is exactly what makes
# schema creation race against a concurrent writer on a fresh database.
_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS events (
        seq                    INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id               TEXT NOT NULL UNIQUE,
        schema_version         TEXT NOT NULL,
        run_id                 TEXT NOT NULL,
        protocol_version       TEXT NOT NULL,
        ts                     TEXT NOT NULL,
        type                   TEXT NOT NULL,
        payload                TEXT NOT NULL,
        source_response_hashes TEXT NOT NULL,
        versions               TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS events_run_id ON events (run_id)",
    "CREATE INDEX IF NOT EXISTS events_type ON events (type)",
    """
    CREATE TABLE IF NOT EXISTS event_sources (
        event_id      TEXT NOT NULL,
        response_hash TEXT NOT NULL,
        PRIMARY KEY (event_id, response_hash)
    )
    """,
    "CREATE INDEX IF NOT EXISTS event_sources_hash ON event_sources (response_hash)",
)

#: How many times to retry the WAL pragma against a concurrently-initializing writer.
#: ``PRAGMA journal_mode`` is one of the few statements SQLite can fail with SQLITE_BUSY
#: without consulting the busy handler, so the busy timeout alone does not cover it.
_WAL_ATTEMPTS = 100

_SELECT = (
    "SELECT schema_version, run_id, protocol_version, event_id, ts, type, payload, "
    "source_response_hashes, versions FROM events"
)


def _enable_wal(conn: sqlite3.Connection) -> None:
    """Put the database in WAL mode, tolerating a concurrent writer doing the same.

    WAL is what makes two writers safe, and the mode is a persistent property of the file,
    so a race here is benign as long as we end up in WAL. What is NOT benign is letting the
    SQLITE_BUSY that a racing ``PRAGMA journal_mode`` can return escape as a bare
    "database is locked", which is the failure this function exists to prevent.
    """
    last: sqlite3.OperationalError | None = None
    for _ in range(_WAL_ATTEMPTS):
        try:
            row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        except sqlite3.OperationalError as exc:
            last = exc
            row = conn.execute("PRAGMA journal_mode").fetchone()
        if row and str(row[0]).strip().lower() == "wal":
            return
    raise ProvenanceError(
        f"Could not put the provenance ledger into WAL mode after {_WAL_ATTEMPTS} attempts "
        f"(last SQLite error: {last})."
    )


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create the tables inside one immediate transaction, so DDL waits its turn."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in _SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


class ProvenanceLedger:
    """An append-only event ledger backed by SQLite transactions.

    The API is deliberately incomplete: there is no ``update``, no ``delete``, no
    ``clear``, and no way to rewrite an event. Appending is the only mutation.

    Concurrency: the database runs in WAL mode with a busy timeout, and every append is a
    ``BEGIN IMMEDIATE`` transaction, so two writers (threads or processes) interleave
    safely and neither loses an event. That is asserted by the concurrent-write test, not
    merely hoped for.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_ledger_path()
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ProvenanceLedger({str(self.path)!r})"

    # -- connection --------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = self._conn
        if conn is not None:
            return conn
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.path),
            timeout=30.0,
            isolation_level=None,  # explicit BEGIN IMMEDIATE per append
            check_same_thread=False,
        )
        try:
            # busy_timeout FIRST: every lock wait below (including the schema DDL) then
            # honors it instead of failing instantly against a concurrent writer.
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA synchronous=FULL")
            _enable_wal(conn)
            _create_schema(conn)
        except BaseException:
            conn.close()
            raise
        self._conn = conn
        return conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self) -> ProvenanceLedger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- the one and only mutation -----------------------------------------

    def append(self, event: ProvenanceEvent) -> ProvenanceEvent:
        """Append one event inside a transaction. Returns the event as stored."""
        self.append_many([event])
        return event

    def append_many(self, events: Iterable[ProvenanceEvent]) -> list[ProvenanceEvent]:
        """Append events in ONE transaction: all of them land, or none of them do."""
        batch = list(events)
        if not batch:
            return []
        rows = [
            (
                event.event_id,
                event.schema_version,
                event.run_id,
                event.protocol_version,
                event.ts,
                event.type,
                canonical_json(event.payload),
                canonical_json(list(event.source_response_hashes)),
                canonical_json(event.versions.to_json_dict()),
            )
            for event in batch
        ]
        source_rows = [
            (event.event_id, _strip_prefix(h))
            for event in batch
            for h in event.source_response_hashes
        ]
        with self._lock:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.executemany(
                    "INSERT INTO events (event_id, schema_version, run_id, protocol_version, "
                    "ts, type, payload, source_response_hashes, versions) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                if source_rows:
                    conn.executemany(
                        "INSERT OR IGNORE INTO event_sources (event_id, response_hash) "
                        "VALUES (?, ?)",
                        source_rows,
                    )
                conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK")
                raise DuplicateEventError(_duplicate_id(batch, exc)) from exc
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        return batch

    # -- reads -------------------------------------------------------------

    def iter_events(
        self, *, run_id: str | None = None, type: str | None = None
    ) -> Iterator[ProvenanceEvent]:
        """Every matching event in append order (the ledger's ``seq``)."""
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        sql = _SELECT
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq"
        with self._lock:
            conn = self._connect()
            rows = conn.execute(sql, params).fetchall()
        for row in rows:
            yield _row_to_event(row)

    def events(
        self, *, run_id: str | None = None, type: str | None = None
    ) -> list[ProvenanceEvent]:
        return list(self.iter_events(run_id=run_id, type=type))

    def get(self, event_id: str) -> ProvenanceEvent | None:
        with self._lock:
            conn = self._connect()
            row = conn.execute(f"{_SELECT} WHERE event_id = ?", (event_id,)).fetchone()
        return None if row is None else _row_to_event(row)

    def count(self, *, run_id: str | None = None, type: str | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        sql = "SELECT COUNT(*) FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._lock:
            conn = self._connect()
            row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    def runs(self) -> list[str]:
        """Every run_id in the ledger, in first-append order."""
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                "SELECT run_id FROM events GROUP BY run_id ORDER BY MIN(seq)"
            ).fetchall()
        return [str(row[0]) for row in rows]

    def events_for_snapshot(self, response_hash: str) -> list[ProvenanceEvent]:
        """Every event that consumed the snapshot with this response hash."""
        key = _strip_prefix(response_hash)
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                f"{_SELECT} WHERE event_id IN "
                "(SELECT event_id FROM event_sources WHERE response_hash = ?) ORDER BY seq",
                (key,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def integrity_check(self) -> str:
        """SQLite's own verdict on the database file. ``"ok"`` when it is not corrupt."""
        with self._lock:
            conn = self._connect()
            row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "unknown"

    # -- derivations -------------------------------------------------------

    def prisma(self, run_id: str | None = None) -> PrismaCounts:
        """PRISMA counts DERIVED from the events (D10). Nothing is read from a stored count."""
        return derive_prisma(
            self.iter_events(run_id=run_id), run_id=run_id or ""
        )

    # -- export (never the write path) -------------------------------------

    def to_jsonl(self, *, run_id: str | None = None) -> str:
        """The ledger as JSONL text: one canonical JSON event per line, in append order."""
        return "".join(
            f"{event.canonical_json()}\n" for event in self.iter_events(run_id=run_id)
        )

    def export_jsonl(self, path: Path | str, *, run_id: str | None = None) -> Path:
        """Write the JSONL export. An export, not a write path: nothing reads it back in."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(self.to_jsonl(run_id=run_id))
        return target

    def import_jsonl(self, path: Path | str) -> list[ProvenanceEvent]:
        """Append a JSONL export into this ledger (the round-trip half of the export).

        This is still an append: existing events are never touched, and re-importing an
        export into the ledger it came from raises :class:`DuplicateEventError`.
        """
        return self.append_many(load_jsonl(path))


def _strip_prefix(value: str) -> str:
    text = str(value).strip()
    return text[7:] if text.startswith("sha256:") else text


def _duplicate_id(batch: Sequence[ProvenanceEvent], exc: sqlite3.IntegrityError) -> str:
    """Best-effort extraction of the offending event_id for the error message."""
    message = str(exc)
    for event in batch:
        if event.event_id in message:
            return event.event_id
    return batch[0].event_id if batch else message


def _row_to_event(row: Sequence[Any]) -> ProvenanceEvent:
    return ProvenanceEvent(
        schema_version=str(row[0]),
        run_id=str(row[1]),
        protocol_version=str(row[2]),
        event_id=str(row[3]),
        ts=str(row[4]),
        type=str(row[5]),
        payload=json.loads(row[6]),
        source_response_hashes=tuple(json.loads(row[7])),
        versions=Versions.from_json_dict(json.loads(row[8])),
    )
