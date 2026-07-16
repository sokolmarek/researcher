"""Tests for protocol locking and amendment (M4.1).

The acceptance criteria this file pins down:

* editing the protocol after a lock WITHOUT an amendment is detected as a hash mismatch;
* an amendment produces a new ``protocol_version`` that is visible on later events;
* the amendment trail lists the locked original plus each amendment, as a chain;
* nothing here reads the clock: ``ts`` is caller-supplied and a replay is byte-identical
  (D15), and the version is DERIVED from event counts, never a stored counter (D10).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from researcher_core.protocol import (
    PROTOCOL_EVENT_TYPES,
    Protocol,
    ProtocolError,
    ProtocolStep,
    amend_protocol,
    amendment_trail,
    check_protocol,
    current_protocol_hash,
    current_protocol_version,
    is_locked,
    lock_protocol,
    next_protocol_version,
    protocol_content_hash,
    run_context,
)
from researcher_core.provenance import ProvenanceLedger, RunContext, derive_prisma

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "provenance-event.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

RUN = "sr-2026-07-16-0001"
TS1 = "2026-07-16T09:00:00Z"
TS2 = "2026-07-16T10:30:00Z"
TS3 = "2026-07-16T14:00:00Z"


def make_protocol(question: str = "Does X improve Y in adults?") -> Protocol:
    return Protocol(
        question=question,
        eligibility={"population": "adults", "intervention": "X", "outcome": "Y"},
        strategies={
            "openalex": "title.search:X AND Y",
            "pubmed": "(X[tiab]) AND (Y[tiab])",
        },
        synthesis="Random-effects meta-analysis of the primary outcome.",
    )


@pytest.fixture()
def ledger(tmp_path: Path):
    instance = ProvenanceLedger(tmp_path / "provenance.sqlite3")
    try:
        yield instance
    finally:
        instance.close()


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------


def test_lock_emits_a_schema_valid_protocol_locked_event(ledger):
    event = lock_protocol(make_protocol(), ledger, RUN, TS1)
    VALIDATOR.validate(event.to_json_dict())
    assert event.type == "protocol_locked"
    assert event.protocol_version == "1.0"
    assert event.payload["content_hash"] == protocol_content_hash(make_protocol())
    assert event.ts == TS1
    assert is_locked(ledger, RUN)


def test_lock_binds_the_run_and_check_matches_the_untouched_protocol(ledger):
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    result = check_protocol(make_protocol(), ledger, RUN)
    assert result.matches is True
    assert result.expected_hash == result.actual_hash
    assert result.expected_hash == current_protocol_hash(ledger, RUN)


def test_locking_twice_is_refused(ledger):
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    with pytest.raises(ProtocolError, match="already has a locked protocol"):
        lock_protocol(make_protocol("A different question"), ledger, RUN, TS2)


def test_a_caller_supplied_version_that_disagrees_is_rejected(ledger):
    with pytest.raises(ProtocolError, match="does not match the derived next version"):
        lock_protocol(make_protocol(), ledger, RUN, TS1, protocol_version="7")


# ---------------------------------------------------------------------------
# Tamper detection (the headline acceptance criterion)
# ---------------------------------------------------------------------------


def test_editing_after_lock_without_amendment_is_detected(ledger):
    lock_protocol(make_protocol(), ledger, RUN, TS1)

    # The protocol file is edited on disk, but no amendment was recorded.
    edited = make_protocol("Does X improve Y in adults AND children?")
    result = check_protocol(edited, ledger, RUN)

    assert result.matches is False
    assert result.actual_hash == protocol_content_hash(edited)
    assert result.expected_hash == protocol_content_hash(make_protocol())
    assert result.expected_hash != result.actual_hash


def test_check_before_any_lock_reports_no_expected_hash(ledger):
    result = check_protocol(make_protocol(), ledger, RUN)
    assert result.matches is False
    assert result.expected_hash == ""
    assert result.actual_hash == protocol_content_hash(make_protocol())
    assert not is_locked(ledger, RUN)


def test_content_hash_is_insensitive_to_mapping_key_order(ledger):
    lock_protocol({"a": 1, "b": 2}, ledger, RUN, TS1)
    # Same content, keys supplied in the other order, must still match.
    assert check_protocol({"b": 2, "a": 1}, ledger, RUN).matches is True


# ---------------------------------------------------------------------------
# Amendment
# ---------------------------------------------------------------------------


def test_amend_requires_an_existing_lock(ledger):
    with pytest.raises(ProtocolError, match="no locked protocol to amend"):
        amend_protocol(
            make_protocol(),
            ledger,
            RUN,
            TS2,
            summary="widen population",
            rationale="new evidence",
        )


def test_amend_requires_summary_and_rationale(ledger):
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    amended = make_protocol("Does X improve Y in adults AND children?")
    with pytest.raises(ProtocolError, match="what changed"):
        amend_protocol(amended, ledger, RUN, TS2, summary="  ", rationale="new evidence")
    with pytest.raises(ProtocolError, match="why it changed"):
        amend_protocol(amended, ledger, RUN, TS2, summary="widen population", rationale="")


def test_amendment_bumps_version_and_new_content_matches(ledger):
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    amended = make_protocol("Does X improve Y in adults AND children?")

    event = amend_protocol(
        amended,
        ledger,
        RUN,
        TS2,
        summary="Broadened the population to include children.",
        rationale="A new trial in paediatric patients met eligibility.",
    )
    VALIDATOR.validate(event.to_json_dict())

    assert event.type == "amendment"
    assert event.protocol_version == "2.0"
    assert event.payload["previous_hash"] == protocol_content_hash(make_protocol())
    assert event.payload["previous_version"] == "1.0"

    # The in-force hash is now the amended content, and the original no longer matches.
    assert current_protocol_version(ledger, RUN) == "2.0"
    assert check_protocol(amended, ledger, RUN).matches is True
    assert check_protocol(make_protocol(), ledger, RUN).matches is False


def test_new_version_is_visible_on_later_events(ledger):
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    amend_protocol(
        make_protocol("v2 question"),
        ledger,
        RUN,
        TS2,
        summary="reword question",
        rationale="clarity",
    )

    # A screening decision emitted through the protocol-bound context carries version 2.
    ctx = run_context(ledger, RUN)
    assert isinstance(ctx, RunContext)
    decision = ctx.event(
        "screening_decision",
        {"record_id": "W123", "stage": "title-abstract", "decision": "include"},
        TS3,
    )
    ledger.append(decision)

    stored = ledger.events(run_id=RUN, type="screening_decision")[0]
    assert stored.protocol_version == "2.0"


def test_version_before_lock_is_the_default_and_context_reflects_it(ledger):
    # Before a lock, the bound version is the ledger default "1.0", but nothing is locked.
    assert current_protocol_version(ledger, RUN) == "1.0"
    assert next_protocol_version(ledger, RUN) == "1.0"
    assert run_context(ledger, RUN).protocol_version == "1.0"
    assert not is_locked(ledger, RUN)


# ---------------------------------------------------------------------------
# The amendment trail
# ---------------------------------------------------------------------------


def test_trail_lists_locked_original_plus_each_amendment(ledger):
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    amend_protocol(
        make_protocol("v2"),
        ledger,
        RUN,
        TS2,
        summary="first change",
        rationale="reason one",
    )
    amend_protocol(
        make_protocol("v3"),
        ledger,
        RUN,
        TS3,
        summary="second change",
        rationale="reason two",
    )

    trail = amendment_trail(ledger, RUN)
    assert [step.kind for step in trail] == ["lock", "amendment", "amendment"]
    assert [step.version for step in trail] == ["1.0", "2.0", "3.0"]
    assert [step.ts for step in trail] == [TS1, TS2, TS3]

    lock_step, first, second = trail
    assert isinstance(lock_step, ProtocolStep)
    assert lock_step.content_hash == protocol_content_hash(make_protocol())
    assert lock_step.summary == "Protocol locked"

    # The trail is a chain: each amendment points at its predecessor's hash.
    assert first.previous_hash == lock_step.content_hash
    assert second.previous_hash == first.content_hash
    assert second.summary == "second change"
    assert second.rationale == "reason two"

    # Every step round-trips to JSON for the report layer.
    assert trail[0].to_json_dict()["kind"] == "lock"


def test_next_version_tracks_the_event_count(ledger):
    assert next_protocol_version(ledger, RUN) == "1.0"
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    assert next_protocol_version(ledger, RUN) == "2.0"
    amend_protocol(
        make_protocol("v2"),
        ledger,
        RUN,
        TS2,
        summary="s",
        rationale="r",
    )
    assert next_protocol_version(ledger, RUN) == "3.0"


def test_protocol_events_do_not_pollute_prisma_counts(ledger):
    # Locking and amending are lifecycle events, not retrieval or screening; the derived
    # PRISMA numbers stay zero until real search and screening events arrive.
    lock_protocol(make_protocol(), ledger, RUN, TS1)
    amend_protocol(
        make_protocol("v2"), ledger, RUN, TS2, summary="s", rationale="r"
    )
    counts = derive_prisma(ledger.events(run_id=RUN), run_id=RUN)
    assert counts.identified == 0
    assert counts.screened == 0
    assert counts.event_counts.get("protocol_locked") == 1
    assert counts.event_counts.get("amendment") == 1


# ---------------------------------------------------------------------------
# Determinism (D15)
# ---------------------------------------------------------------------------


def test_lock_is_replay_deterministic(tmp_path):
    # Two independent runs with the same inputs produce byte-identical events. The event id
    # is content-addressed, so a self-generated timestamp or a UUID would break this.
    events = []
    for name in ("a.sqlite3", "b.sqlite3"):
        led = ProvenanceLedger(tmp_path / name)
        try:
            events.append(lock_protocol(make_protocol(), led, RUN, TS1).canonical_json())
        finally:
            led.close()
    assert events[0] == events[1]


def test_protocol_event_types_are_both_in_the_ledger_vocabulary(ledger):
    from researcher_core.provenance import EVENT_TYPES

    assert set(PROTOCOL_EVENT_TYPES) <= set(EVENT_TYPES)
