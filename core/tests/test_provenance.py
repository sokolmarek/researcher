"""Tests for the hardened provenance ledger (D19).

Four properties are asserted here because the milestone rests on them:

* every event validates against ``core/schemas/provenance-event.schema.json``;
* the ledger is append-only, with no update or delete path in the API at all;
* two concurrent writers (threads AND separate processes) lose no events and corrupt
  nothing;
* PRISMA counts are DERIVED by aggregating events, so they cannot drift from them.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from researcher_core import PARSER_VERSION, __version__
from researcher_core.provenance import (
    EVENT_TYPES,
    PROVENANCE_SCHEMA_VERSION,
    DuplicateEventError,
    ProvenanceError,
    ProvenanceEvent,
    ProvenanceLedger,
    RunContext,
    Versions,
    derive_prisma,
    load_jsonl,
    normalize_ts,
    normalize_version,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "provenance-event.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

TS1 = "2026-07-14T12:00:00Z"
TS2 = "2026-07-14T12:00:05Z"
TS3 = "2026-07-14T12:00:09Z"

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def validate(event: ProvenanceEvent) -> dict:
    """Validate an event against the D19 schema and return its JSON form."""
    data = event.to_json_dict()
    VALIDATOR.validate(data)
    return data


@pytest.fixture()
def ledger(tmp_path: Path):
    instance = ProvenanceLedger(tmp_path / "provenance.sqlite3")
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture()
def run() -> RunContext:
    return RunContext(run_id="run-2026-07-14-0001")


# ---------------------------------------------------------------------------
# Event shape (D19)
# ---------------------------------------------------------------------------


def test_event_has_exactly_the_nine_D19_fields(run):
    event = run.retrieval(
        TS1, source="openalex", query="self-supervised ECG", record_ids=["w1", "w2"],
        source_response_hashes=[HASH_A],
    )
    data = validate(event)
    assert set(data) == {
        "schema_version",
        "run_id",
        "protocol_version",
        "event_id",
        "ts",
        "type",
        "payload",
        "source_response_hashes",
        "versions",
    }
    assert data["run_id"] == "run-2026-07-14-0001"
    assert data["schema_version"] == PROVENANCE_SCHEMA_VERSION
    assert data["source_response_hashes"] == [HASH_A]
    assert data["versions"] == {"core": __version__, "parser": normalize_version(PARSER_VERSION)}


def test_every_event_type_in_the_closed_vocabulary_validates(run):
    for event_type in EVENT_TYPES:
        event = run.event(event_type, {"note": "shape check"}, TS1)
        validate(event)


def test_unknown_event_type_is_rejected(run):
    with pytest.raises(ProvenanceError, match="vocabulary is closed"):
        run.event("hallucination", {}, TS1)


def test_versions_may_carry_a_model_and_nothing_else(run):
    event = run.event(
        "review", {"panel": "methods"}, TS1
    )
    assert "model" not in validate(event)["versions"]

    with_model = ProvenanceEvent(
        run_id="r", type="review", ts=TS1, payload={},
        versions=Versions(model="claude-opus-4-8"),
    )
    assert validate(with_model)["versions"]["model"] == "claude-opus-4-8"

    with pytest.raises(ProvenanceError, match="unknown key"):
        Versions.from_json_dict({"core": "0.1.0", "parser": "1.0", "temperature": "0"})


def test_package_version_constants_are_widened_to_schema_valid_version_strings():
    # The package pins PARSER_VERSION = "1"; the schema demands MAJOR.MINOR.
    assert normalize_version("1") == "1.0"
    assert normalize_version("0.1.0") == "0.1.0"
    with pytest.raises(ProvenanceError):
        normalize_version("banana")


def test_source_response_hashes_must_be_content_hashes(run):
    ok = run.event("retrieval", {}, TS1, source_response_hashes=[f"sha256:{HASH_A}", HASH_B])
    assert validate(ok)["source_response_hashes"] == [f"sha256:{HASH_A}", HASH_B]
    with pytest.raises(ProvenanceError, match="SHA-256"):
        run.event("retrieval", {}, TS1, source_response_hashes=["not-a-hash"])


# ---------------------------------------------------------------------------
# ts is caller-supplied (D15)
# ---------------------------------------------------------------------------


def test_ts_is_caller_supplied_and_returned_verbatim():
    assert normalize_ts("2026-07-14T12:00:00Z") == "2026-07-14T12:00:00Z"
    assert normalize_ts("2026-07-14T14:00:00+02:00") == "2026-07-14T14:00:00+02:00"
    with pytest.raises(ProvenanceError):
        normalize_ts("2026-07-14T12:00:00")  # no offset
    with pytest.raises(ProvenanceError):
        normalize_ts("")


def test_the_ledger_never_reads_the_clock():
    """A self-generated ts would make two replays of one run differ. D15 forbids it.

    Asserted over the parsed syntax tree, not the text, so the prose in the module (which
    talks about the clock calls it must not make) cannot fool the check either way.
    """
    source = (Path(__file__).resolve().parents[1] / "researcher_core" / "provenance.py").read_text(
        encoding="utf-8"
    )
    forbidden = {"time", "now", "utcnow", "today", "monotonic", "perf_counter", "uuid4"}
    called: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                called.add(func.attr)
            elif isinstance(func, ast.Name):
                called.add(func.id)
    assert not (called & forbidden), f"provenance.py must not call {sorted(called & forbidden)}"


def test_event_id_is_content_addressed_so_a_replay_reproduces_the_ledger(run):
    first = run.retrieval(TS1, source="openalex", query="q", record_ids=["w1"])
    replayed = RunContext(run_id=run.run_id).retrieval(
        TS1, source="openalex", query="q", record_ids=["w1"]
    )
    assert first.event_id == replayed.event_id
    later = run.retrieval(TS2, source="openalex", query="q", record_ids=["w1"])
    assert later.event_id != first.event_id


# ---------------------------------------------------------------------------
# Append-only
# ---------------------------------------------------------------------------


def test_the_ledger_api_has_no_update_and_no_delete_path(ledger):
    forbidden = {"update", "delete", "remove", "clear", "set", "purge", "drop", "truncate"}
    public = {name for name in dir(ledger) if not name.startswith("_")}
    assert not (public & forbidden)
    assert not [name for name in public if any(word in name for word in forbidden)]


def test_appending_the_same_event_twice_raises_instead_of_overwriting(ledger, run):
    event = run.retrieval(TS1, source="openalex", query="q", record_ids=["w1"])
    ledger.append(event)
    with pytest.raises(DuplicateEventError):
        ledger.append(event)
    assert ledger.count() == 1
    assert ledger.get(event.event_id).payload == event.payload


def test_a_failed_batch_lands_no_events_at_all(ledger, run):
    good = run.retrieval(TS1, source="openalex", query="q", record_ids=["w1"])
    ledger.append(good)
    batch = [
        run.retrieval(TS2, source="crossref", query="q", record_ids=["c1"]),
        good,  # duplicate: the whole transaction must roll back
    ]
    with pytest.raises(DuplicateEventError):
        ledger.append_many(batch)
    assert ledger.count() == 1


def test_round_trip_through_sqlite_preserves_the_event(ledger, run):
    event = run.record_lineage(
        TS1,
        artifact_id="10.7717/peerj.4375",
        artifact_hash=HASH_C,
        inputs=[{"id": "openalex:W1", "hash": HASH_A, "source": "openalex"}],
        source_response_hashes=[HASH_A, f"sha256:{HASH_B}"],
    )
    ledger.append(event)
    (stored,) = ledger.events()
    assert stored == event
    assert validate(stored) == validate(event)


def test_events_for_snapshot_joins_the_ledger_to_the_snapshot_store(ledger, run):
    a = run.retrieval(TS1, source="openalex", query="q", source_response_hashes=[HASH_A])
    b = run.retrieval(TS2, source="crossref", query="q", source_response_hashes=[HASH_B])
    ledger.append_many([a, b])
    assert [e.event_id for e in ledger.events_for_snapshot(HASH_A)] == [a.event_id]
    assert [e.event_id for e in ledger.events_for_snapshot(f"sha256:{HASH_B}")] == [b.event_id]
    assert ledger.events_for_snapshot(HASH_C) == []


# ---------------------------------------------------------------------------
# PRISMA, derived by aggregation (D10)
# ---------------------------------------------------------------------------


def _seed_prisma_run(ledger: ProvenanceLedger, run: RunContext) -> None:
    """Two retrieval events (5 records identified) and two dedup decisions (2 removed)."""
    ledger.append_many(
        [
            run.retrieval(
                TS1,
                source="openalex",
                query="self-supervised ECG",
                record_ids=["10.1/a", "10.1/b", "10.1/c"],
                source_response_hashes=[HASH_A],
            ),
            run.retrieval(
                TS2,
                source="crossref",
                query="self-supervised ECG",
                record_ids=["10.1/a", "10.1/b"],
                source_response_hashes=[HASH_B],
            ),
            run.dedup_decision(
                TS3,
                winner="10.1/a",
                losers=["crossref:10.1/a"],
                reason="doi_exact",
            ),
            run.dedup_decision(
                TS3,
                winner="10.1/b",
                losers=["crossref:10.1/b"],
                reason="title_similarity",
                similarity=0.97,
            ),
        ]
    )


def test_prisma_derives_identified_and_deduplicated_from_the_events(ledger, run):
    _seed_prisma_run(ledger, run)
    counts = ledger.prisma(run.run_id)
    assert counts.identified == 5
    assert counts.identified_by_source == {"openalex": 3, "crossref": 2}
    assert counts.duplicates_removed == 2
    assert counts.deduplicated == 3
    assert counts.event_counts == {"retrieval": 2, "dedup_decision": 2}
    assert counts.to_json_dict()["deduplicated"] == 3


def test_prisma_counts_track_the_events_and_cannot_drift_from_them(ledger, run):
    _seed_prisma_run(ledger, run)
    assert ledger.prisma(run.run_id).identified == 5
    ledger.append(
        run.retrieval(TS3, source="arxiv", query="self-supervised ECG", record_ids=["arxiv:1"])
    )
    counts = ledger.prisma(run.run_id)
    assert counts.identified == 6
    assert counts.deduplicated == 4


def test_prisma_is_scoped_by_run_id(ledger, run):
    _seed_prisma_run(ledger, run)
    other = RunContext(run_id="run-other")
    ledger.append(
        other.retrieval(TS1, source="openalex", query="other", record_ids=["x1", "x2"])
    )
    assert ledger.prisma(run.run_id).identified == 5
    assert ledger.prisma("run-other").identified == 2
    assert ledger.prisma().identified == 7  # every run
    assert ledger.runs() == [run.run_id, "run-other"]


def test_prisma_falls_back_to_counts_when_ids_are_absent(run):
    events = [
        run.retrieval(TS1, source="pubmed", query="q", record_count=12),
        run.event(
            "dedup_decision", {"winner": "a", "removed_count": 3, "reason": "doi_exact"}, TS2
        ),
    ]
    counts = derive_prisma(events)
    assert (counts.identified, counts.duplicates_removed, counts.deduplicated) == (12, 3, 9)


def test_prisma_derives_screening_counts_when_M4_events_are_present(run):
    events = [
        run.retrieval(TS1, source="openalex", query="q", record_ids=["a", "b", "c"]),
        run.event("screening_decision", {"record_id": "a", "decision": "include"}, TS2),
        run.event("screening_decision", {"record_id": "b", "decision": "exclude"}, TS2),
        run.event("screening_decision", {"record_id": "c", "decision": "exclude"}, TS3),
    ]
    counts = derive_prisma(events)
    assert (counts.screened, counts.included, counts.excluded) == (3, 1, 2)


# ---------------------------------------------------------------------------
# JSONL export (an export, never the write path)
# ---------------------------------------------------------------------------


def test_jsonl_export_round_trips(ledger, run, tmp_path):
    _seed_prisma_run(ledger, run)
    path = ledger.export_jsonl(tmp_path / "ledger.jsonl", run_id=run.run_id)

    reloaded = load_jsonl(path)
    assert reloaded == ledger.events(run_id=run.run_id)

    for event in reloaded:
        validate(event)

    # And the export re-imports into a fresh ledger with identical derived counts.
    with ProvenanceLedger(tmp_path / "second.sqlite3") as second:
        second.import_jsonl(path)
        assert second.events() == reloaded
        assert second.prisma(run.run_id).to_json_dict() == ledger.prisma(run.run_id).to_json_dict()


def test_jsonl_export_is_byte_stable(ledger, run, tmp_path):
    _seed_prisma_run(ledger, run)
    first = ledger.export_jsonl(tmp_path / "a.jsonl").read_bytes()
    second = ledger.export_jsonl(tmp_path / "b.jsonl").read_bytes()
    assert first == second
    assert first.count(b"\n") == 4
    assert b"\r\n" not in first


def test_reimporting_an_export_into_its_own_ledger_is_refused(ledger, run, tmp_path):
    _seed_prisma_run(ledger, run)
    path = ledger.export_jsonl(tmp_path / "ledger.jsonl")
    with pytest.raises(DuplicateEventError):
        ledger.import_jsonl(path)
    assert ledger.count() == 4


# ---------------------------------------------------------------------------
# Concurrent writers (required by M2.10)
# ---------------------------------------------------------------------------


def test_two_concurrent_thread_writers_lose_no_events_and_corrupt_nothing(tmp_path):
    path = tmp_path / "concurrent.sqlite3"
    per_writer = 60
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def writer(name: str) -> None:
        ledger = ProvenanceLedger(path)  # its own connection, like a separate process
        try:
            start.wait(timeout=30)
            for index in range(per_writer):
                ledger.append(
                    RunContext(run_id="run-concurrent").retrieval(
                        TS1,
                        source=name,
                        query=f"{name}-{index}",
                        record_ids=[f"{name}:{index}"],
                    )
                )
        except BaseException as exc:  # noqa: BLE001 - re-raised in the main thread
            errors.append(exc)
        finally:
            ledger.close()

    threads = [threading.Thread(target=writer, args=(name,)) for name in ("openalex", "crossref")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not errors, errors

    with ProvenanceLedger(path) as ledger:
        assert ledger.integrity_check() == "ok"
        events = ledger.events()
        assert len(events) == 2 * per_writer
        assert len({e.event_id for e in events}) == 2 * per_writer
        counts = ledger.prisma("run-concurrent")
        assert counts.identified == 2 * per_writer
        assert counts.identified_by_source == {"openalex": per_writer, "crossref": per_writer}


_WRITER_SCRIPT = textwrap.dedent(
    """
    import sys
    from researcher_core.provenance import ProvenanceLedger, RunContext

    path, name, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
    run = RunContext(run_id="run-processes")
    with ProvenanceLedger(path) as ledger:
        for index in range(count):
            ledger.append(
                run.retrieval(
                    "2026-07-14T12:00:00Z",
                    source=name,
                    query=f"{name}-{index}",
                    record_ids=[f"{name}:{index}"],
                )
            )
    """
)


def test_two_concurrent_process_writers_lose_no_events_and_corrupt_nothing(tmp_path):
    """The real hazard is cross-process locking on Windows, so spawn real processes."""
    script = tmp_path / "writer.py"
    script.write_text(_WRITER_SCRIPT, encoding="utf-8")
    path = str(tmp_path / "processes.sqlite3")
    per_writer = 40

    processes = [
        subprocess.Popen(
            [sys.executable, str(script), path, name, str(per_writer)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for name in ("openalex", "crossref")
    ]
    for process in processes:
        _, stderr = process.communicate(timeout=180)
        assert process.returncode == 0, stderr.decode("utf-8", "replace")

    with ProvenanceLedger(path) as ledger:
        assert ledger.integrity_check() == "ok"
        assert ledger.count() == 2 * per_writer
        counts = ledger.prisma("run-processes")
        assert counts.identified_by_source == {"openalex": per_writer, "crossref": per_writer}
