"""Protocol locking and amendment for the systematic-review vertical (M4.1).

A systematic review is only defensible if its protocol (the question, the eligibility
profile, the per-database search strategies, and the planned synthesis) is fixed BEFORE
screening starts, and every later deviation is recorded rather than silently edited. This
module records that discipline on the append-only D19 ledger:

* :func:`lock_protocol` hashes the protocol document with :func:`content_hash` and emits a
  ``protocol_locked`` event carrying the content hash. From that point the run is bound to
  the hash via the D19 ``protocol_version`` field on every subsequent event.
* :func:`amend_protocol` never edits. A deviation emits an ``amendment`` event that records
  what changed, why, and when (via the caller-supplied ``ts``), carries the hash of the new
  protocol content, and bumps ``protocol_version``. The ledger therefore preserves the
  locked original plus the full amendment trail (PRISMA 2020 item 24b).
* :func:`check_protocol` detects tampering: given the current protocol file content and the
  ledger, it reports whether the content still matches the locked (or latest-amended) hash.
  Editing the file after a lock without an amendment shows up as a hash mismatch.

``protocol_version`` is a monotonic version DERIVED from the count of ``protocol_locked``
plus ``amendment`` events in the run (D10: derived, never a stored mutable counter). The
lock is version 1, and each amendment is the next integer. It is written into the D19
``protocol_version`` field, whose schema (``versionString``) requires ``MAJOR.MINOR`` form,
so the stored values are ``"1.0"``, ``"2.0"``, ... (the ledger's own normalizer widens a
bare integer, and this module works in that same normalized space so every comparison
agrees).

Determinism (D15): nothing here reads the clock. ``ts`` is caller-supplied and passed
straight through to the ledger, so a replay of the same run reproduces byte-identical
events. All hashing goes through the one canonicalization routine in :mod:`.model`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NamedTuple

from . import PROTOCOL_VERSION
from .model import content_hash
from .provenance import (
    ProvenanceError,
    ProvenanceEvent,
    ProvenanceLedger,
    RunContext,
    Versions,
    normalize_ts,
    normalize_version,
)

__all__ = [
    "PROTOCOL_EVENT_TYPES",
    "Protocol",
    "ProtocolCheck",
    "ProtocolError",
    "ProtocolStep",
    "amend_protocol",
    "amendment_trail",
    "check_protocol",
    "current_protocol_hash",
    "current_protocol_version",
    "is_locked",
    "lock_protocol",
    "next_protocol_version",
    "protocol_content_hash",
    "run_context",
]

#: The two protocol-lifecycle event types this module reads and writes. Both already exist
#: in the closed ledger vocabulary (see :data:`researcher_core.provenance.EVENT_TYPES`).
PROTOCOL_EVENT_TYPES: tuple[str, ...] = ("protocol_locked", "amendment")


class ProtocolError(ProvenanceError):
    """A protocol lock or amendment operation was rejected.

    Subclasses :class:`~researcher_core.provenance.ProvenanceError` so a caller that already
    catches ledger errors catches these too.
    """


# ---------------------------------------------------------------------------
# The protocol document
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Protocol:
    """A convenience shape for the protocol document.

    The lock and amendment functions accept ANY JSON-serializable content (a mapping, a
    string, or an object exposing ``to_json_dict``); this dataclass is offered so callers
    that want structure get the four PRISMA 2020 item-7 elements named. It is never
    required: the hash is taken over whatever content the caller supplies.
    """

    question: str = ""
    eligibility: Mapping[str, Any] = field(default_factory=dict)
    strategies: Mapping[str, Any] = field(default_factory=dict)
    synthesis: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "question": self.question,
            "eligibility": dict(self.eligibility),
            "strategies": dict(self.strategies),
            "synthesis": self.synthesis,
        }
        if self.extra:
            out["extra"] = dict(self.extra)
        return out


def _as_content(content: Any) -> Any:
    """Normalize supplied protocol content into a JSON-serializable value for hashing.

    A :class:`Protocol` (or anything exposing ``to_json_dict``) is expanded; a mapping is
    copied; everything else (a string, say) passes through. :func:`content_hash` then
    canonicalizes it, so key insertion order never affects the hash.
    """
    to_json = getattr(content, "to_json_dict", None)
    if callable(to_json):
        return to_json()
    if isinstance(content, Mapping):
        return dict(content)
    return content


def protocol_content_hash(content: Any) -> str:
    """The content hash the ledger binds to: :func:`content_hash` of the normalized content."""
    return content_hash(_as_content(content))


# ---------------------------------------------------------------------------
# Reading the protocol lifecycle out of the ledger
# ---------------------------------------------------------------------------


def _protocol_events(ledger: ProvenanceLedger, run_id: str) -> list[ProvenanceEvent]:
    """Every ``protocol_locked`` / ``amendment`` event for the run, in append order."""
    return [
        event
        for event in ledger.events(run_id=run_id)
        if event.type in PROTOCOL_EVENT_TYPES
    ]


def _version_of(event: ProvenanceEvent) -> str:
    """The protocol version an event carries (payload copy, falling back to the D19 field)."""
    return str(event.payload.get("protocol_version") or event.protocol_version)


def _derive_version(count: int) -> str:
    """The monotonic version for the ``count``-th lifecycle event, in D19 normalized form.

    The lock is the first event, so it is version 1 (stored ``"1.0"``). :func:`normalize_version`
    widens the bare integer to the ``MAJOR.MINOR`` shape the D19 schema requires.
    """
    return normalize_version(str(count))


def is_locked(ledger: ProvenanceLedger, run_id: str) -> bool:
    """True once the run has a ``protocol_locked`` event. The screening precondition."""
    return any(event.type == "protocol_locked" for event in _protocol_events(ledger, run_id))


def next_protocol_version(ledger: ProvenanceLedger, run_id: str) -> str:
    """The monotonic version the next lock or amendment will carry.

    DERIVED (D10) from the count of protocol-lifecycle events: ``"1.0"`` for the lock on a
    fresh run, then ``"2.0"``, ``"3.0"``, ... for each amendment. Never a stored counter.
    """
    return _derive_version(len(_protocol_events(ledger, run_id)) + 1)


def current_protocol_version(ledger: ProvenanceLedger, run_id: str) -> str:
    """The version later events should bind to: the latest lock or amendment.

    Before any lock this is the ledger's normalized default (``"1.0"``, from
    :data:`PROTOCOL_VERSION`), so an unlocked run and a freshly locked run agree; use
    :func:`is_locked` to tell the two apart.
    """
    events = _protocol_events(ledger, run_id)
    return _version_of(events[-1]) if events else normalize_version(PROTOCOL_VERSION)


def current_protocol_hash(ledger: ProvenanceLedger, run_id: str) -> str:
    """The content hash currently in force (latest amendment, else the lock, else ``""``)."""
    events = _protocol_events(ledger, run_id)
    if not events:
        return ""
    return str(events[-1].payload.get("content_hash") or "")


def run_context(
    ledger: ProvenanceLedger,
    run_id: str,
    *,
    versions: Versions | None = None,
) -> RunContext:
    """A :class:`RunContext` bound to the run's CURRENT protocol version.

    Emitters (screening decisions, retrievals, adjudications) built from this context stamp
    the in-force ``protocol_version`` automatically, which is what makes an amendment
    "visible on later events".
    """
    return RunContext(
        run_id=run_id,
        versions=versions or Versions(),
        protocol_version=current_protocol_version(ledger, run_id),
    )


# ---------------------------------------------------------------------------
# Locking and amending
# ---------------------------------------------------------------------------


def _reconcile_version(provided: str | None, derived: str) -> str:
    """Return the derived monotonic version, rejecting a caller override that disagrees.

    ``protocol_version`` is authoritative-by-derivation, so the parameter exists only as an
    optional assertion. Passing a value that does not match the derived next version is a
    bug in the caller (it would break the monotonic chain), so it raises rather than being
    silently honored.
    """
    if provided is None:
        return derived
    if normalize_version(provided) != derived:
        raise ProtocolError(
            f"protocol_version {provided!r} does not match the derived next version "
            f"{derived!r}. The version is derived from the count of protocol_locked plus "
            "amendment events (D10); pass None to let it be derived."
        )
    return derived


def lock_protocol(
    content: Any,
    ledger: ProvenanceLedger,
    run_id: str,
    ts: str | datetime,
    *,
    protocol_version: str | None = None,
    versions: Versions | None = None,
    source_response_hashes: Iterable[str] = (),
) -> ProvenanceEvent:
    """Hash the protocol and emit the ``protocol_locked`` event that binds the run.

    Locking is a one-time act: a run that already holds a lock raises :class:`ProtocolError`
    (deviations are amendments, not re-locks). The emitted event carries the content hash and
    the derived version ``"1"``, and is returned so the caller can read back its ``event_id``.
    """
    existing = _protocol_events(ledger, run_id)
    if any(event.type == "protocol_locked" for event in existing):
        locked_version = next(
            _version_of(event) for event in existing if event.type == "protocol_locked"
        )
        raise ProtocolError(
            f"Run {run_id!r} already has a locked protocol (version {locked_version}). "
            "Deviations are recorded as amendments, never re-locks: call amend_protocol."
        )
    version = _reconcile_version(protocol_version, _derive_version(len(existing) + 1))
    normalized = _as_content(content)
    chash = content_hash(normalized)
    payload: dict[str, Any] = {
        "content_hash": chash,
        "protocol_version": version,
        "content": normalized,
    }
    event = ProvenanceEvent(
        run_id=run_id,
        type="protocol_locked",
        ts=normalize_ts(ts),
        payload=payload,
        source_response_hashes=tuple(source_response_hashes),
        versions=versions or Versions(),
        protocol_version=version,
    )
    ledger.append(event)
    return event


def amend_protocol(
    content: Any,
    ledger: ProvenanceLedger,
    run_id: str,
    ts: str | datetime,
    *,
    summary: str,
    rationale: str,
    protocol_version: str | None = None,
    versions: Versions | None = None,
    source_response_hashes: Iterable[str] = (),
) -> ProvenanceEvent:
    """Record a deviation as an ``amendment`` event and bump ``protocol_version``.

    ``content`` is the COMPLETE amended protocol, so its hash becomes the new in-force hash
    that :func:`check_protocol` compares against. ``summary`` (what changed) and ``rationale``
    (why) are required, because an unexplained amendment is exactly the silent edit this
    system exists to prevent. Requires an existing lock; the amendment records the hash and
    version it supersedes so the trail is a chain.
    """
    existing = _protocol_events(ledger, run_id)
    if not any(event.type == "protocol_locked" for event in existing):
        raise ProtocolError(
            f"Run {run_id!r} has no locked protocol to amend. Call lock_protocol first: "
            "screening cannot start, and nothing can be amended, before a lock exists."
        )
    if not str(summary).strip():
        raise ProtocolError("An amendment must state what changed (summary is required).")
    if not str(rationale).strip():
        raise ProtocolError("An amendment must state why it changed (rationale is required).")

    previous = existing[-1]
    version = _reconcile_version(protocol_version, _derive_version(len(existing) + 1))
    normalized = _as_content(content)
    chash = content_hash(normalized)
    payload: dict[str, Any] = {
        "content_hash": chash,
        "protocol_version": version,
        "summary": str(summary),
        "rationale": str(rationale),
        "previous_hash": str(previous.payload.get("content_hash") or ""),
        "previous_version": _version_of(previous),
        "content": normalized,
    }
    event = ProvenanceEvent(
        run_id=run_id,
        type="amendment",
        ts=normalize_ts(ts),
        payload=payload,
        source_response_hashes=tuple(source_response_hashes),
        versions=versions or Versions(),
        protocol_version=version,
    )
    ledger.append(event)
    return event


# ---------------------------------------------------------------------------
# Tamper detection and the amendment trail
# ---------------------------------------------------------------------------


class ProtocolCheck(NamedTuple):
    """The result of :func:`check_protocol`. A plain 3-tuple: ``(matches, expected, actual)``.

    ``matches`` is False (with ``expected_hash == ""``) when nothing is locked yet, so a
    caller can distinguish "unlocked" from "locked but tampered" by inspecting
    ``expected_hash``.
    """

    matches: bool
    expected_hash: str
    actual_hash: str


def check_protocol(
    content: Any,
    ledger: ProvenanceLedger,
    run_id: str,
) -> ProtocolCheck:
    """Does the current protocol content still match the locked (or latest-amended) hash?

    Returns ``(matches, expected_hash, actual_hash)``. ``actual_hash`` is the hash of the
    content passed in; ``expected_hash`` is the in-force hash from the ledger. Editing the
    protocol file after a lock without recording an amendment makes the two differ, and that
    mismatch is the detection this function provides.
    """
    actual = protocol_content_hash(content)
    expected = current_protocol_hash(ledger, run_id)
    return ProtocolCheck(
        matches=bool(expected) and expected == actual,
        expected_hash=expected,
        actual_hash=actual,
    )


@dataclass(frozen=True)
class ProtocolStep:
    """One entry in the amendment trail: the locked original or a later amendment."""

    version: str
    kind: str  # "lock" | "amendment"
    content_hash: str
    ts: str
    event_id: str
    summary: str = ""
    rationale: str = ""
    previous_hash: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "kind": self.kind,
            "content_hash": self.content_hash,
            "ts": self.ts,
            "event_id": self.event_id,
            "summary": self.summary,
            "rationale": self.rationale,
            "previous_hash": self.previous_hash,
        }


def amendment_trail(ledger: ProvenanceLedger, run_id: str) -> list[ProtocolStep]:
    """The locked original plus every amendment, in order.

    This is what the systematic-review report lists under PRISMA 2020 item 24b (protocol and
    amendments). The first entry is always the lock; each following entry is an amendment
    that supersedes the one before it.
    """
    steps: list[ProtocolStep] = []
    for event in _protocol_events(ledger, run_id):
        is_lock = event.type == "protocol_locked"
        steps.append(
            ProtocolStep(
                version=_version_of(event),
                kind="lock" if is_lock else "amendment",
                content_hash=str(event.payload.get("content_hash") or ""),
                ts=event.ts,
                event_id=event.event_id,
                summary=str(
                    event.payload.get("summary")
                    or ("Protocol locked" if is_lock else "")
                ),
                rationale=str(event.payload.get("rationale") or ""),
                previous_hash=str(event.payload.get("previous_hash") or ""),
            )
        )
    return steps
