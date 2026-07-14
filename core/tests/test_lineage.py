"""Tests for source-dependency lineage.

The question under test: given a derived record, which snapshots produced it? That is the
query the M3 compile gate runs for stale-evidence and drift detection, so it is exercised
here end to end: real snapshots in a real snapshot store, real ``record_lineage`` events in
a real SQLite ledger, resolved back to the snapshot records themselves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from researcher_core.lineage import LineageIndex, strip_hash_prefix
from researcher_core.model import CSLRecord
from researcher_core.provenance import ProvenanceLedger, RunContext
from researcher_core.snapshots import SnapshotStore

TS1 = "2026-07-14T12:00:00Z"
TS2 = "2026-07-14T12:00:05Z"
TS3 = "2026-07-14T12:00:09Z"

RUN = "run-lineage-0001"

OPENALEX_BODY = {
    "results": [
        {
            "id": "https://openalex.org/W2741809807",
            "doi": "https://doi.org/10.7717/peerj.4375",
            "title": "The state of OA",
            "publication_year": 2018,
        }
    ]
}

CROSSREF_BODY = {
    "message": {
        "DOI": "10.7717/peerj.4375",
        "title": ["The State of OA"],
        "issued": {"date-parts": [[2018, 2, 13]]},
    }
}


@pytest.fixture()
def ledger(tmp_path: Path):
    instance = ProvenanceLedger(tmp_path / "provenance.sqlite3")
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture()
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "snapshots")


@pytest.fixture()
def run() -> RunContext:
    return RunContext(run_id=RUN)


@pytest.fixture()
def merged_record() -> CSLRecord:
    """The derived artifact: one deduplicated record merged from two sources."""
    return CSLRecord(
        DOI="10.7717/peerj.4375",
        title="The state of OA",
        author=["Heather Piwowar"],
        issued=2018,
        source="openalex",
    )


def _seed(
    ledger: ProvenanceLedger, store: SnapshotStore, run: RunContext, record: CSLRecord
) -> tuple[str, str]:
    """Record two snapshots, then the retrieval and record_lineage events over them."""
    openalex = store.record(
        "openalex", "works", {"filter": "doi:10.7717/peerj.4375"}, OPENALEX_BODY,
        retrieved_at=TS1,
    )
    crossref = store.record(
        "crossref", "works/10.7717/peerj.4375", {}, CROSSREF_BODY, retrieved_at=TS1
    )
    ledger.append_many(
        [
            run.retrieval(
                TS1,
                source="openalex",
                query="doi:10.7717/peerj.4375",
                record_ids=["openalex:W2741809807"],
                source_response_hashes=[openalex.response_hash],
            ),
            run.retrieval(
                TS2,
                source="crossref",
                query="doi:10.7717/peerj.4375",
                record_ids=["crossref:10.7717/peerj.4375"],
                source_response_hashes=[crossref.response_hash],
            ),
            run.record_lineage(
                TS3,
                artifact_id=record.id,
                artifact_hash=record.content_hash(),
                inputs=[
                    {
                        "id": "openalex:W2741809807",
                        "hash": openalex.response_hash,
                        "source": "openalex",
                    },
                    {
                        "id": "crossref:10.7717/peerj.4375",
                        "hash": crossref.response_hash,
                        "source": "crossref",
                    },
                ],
                source_response_hashes=[openalex.response_hash, crossref.response_hash],
            ),
        ]
    )
    return openalex.response_hash, crossref.response_hash


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_lineage_resolves_a_derived_record_back_to_its_source_snapshots(
    ledger, store, run, merged_record
):
    openalex_hash, crossref_hash = _seed(ledger, store, run, merged_record)

    index = LineageIndex.from_ledger(ledger, run_id=RUN)
    result = index.resolve(merged_record.id)

    assert result.known is True
    assert result.artifact_id == "10.7717/peerj.4375"
    assert result.artifact_hash == merged_record.content_hash()
    assert result.artifact_type == "record"
    assert set(result.snapshot_hashes) == {openalex_hash, crossref_hash}
    assert result.upstream_ids == ("crossref:10.7717/peerj.4375", "openalex:W2741809807")

    snapshots = index.resolve_snapshots(merged_record.id, store)
    assert [s.source for s in snapshots] == ["crossref", "openalex"]
    assert {s.response_hash for s in snapshots} == {openalex_hash, crossref_hash}
    # The snapshots come back as the recorded bodies themselves, not just hashes.
    openalex_snapshot = next(s for s in snapshots if s.source == "openalex")
    assert openalex_snapshot.response_body == OPENALEX_BODY

    assert result.to_json_dict()["known"] is True


def test_an_unrecorded_artifact_resolves_to_known_false_rather_than_raising(ledger, run):
    index = LineageIndex.from_ledger(ledger)
    result = index.resolve("10.9999/never-derived")
    assert result.known is False
    assert result.snapshot_hashes == ()
    assert index.artifacts() == []


def test_lineage_is_transitive_through_intermediate_artifacts(ledger, store, run, merged_record):
    openalex_hash, crossref_hash = _seed(ledger, store, run, merged_record)
    table = store.record("openalex", "works", {"filter": "cites:W2741809807"}, {"results": []},
                         retrieved_at=TS1)
    ledger.append(
        run.record_lineage(
            TS3,
            artifact_id="table:1",
            artifact_hash="d" * 64,
            artifact_type="table",
            inputs=[{"id": merged_record.id, "hash": merged_record.content_hash()}],
            source_response_hashes=[table.response_hash],
        )
    )

    index = LineageIndex.from_ledger(ledger)
    result = index.resolve("table:1")
    assert set(result.snapshot_hashes) == {openalex_hash, crossref_hash, table.response_hash}
    assert merged_record.id in result.upstream_ids
    assert result.artifact_type == "table"


def test_a_lineage_cycle_terminates(ledger, run):
    ledger.append_many(
        [
            run.record_lineage(
                TS1, artifact_id="a", artifact_hash="a" * 64,
                inputs=[{"id": "b"}], source_response_hashes=["1" * 64],
            ),
            run.record_lineage(
                TS2, artifact_id="b", artifact_hash="b" * 64,
                inputs=[{"id": "a"}], source_response_hashes=["2" * 64],
            ),
        ]
    )
    index = LineageIndex.from_ledger(ledger)
    result = index.resolve("a")
    assert set(result.snapshot_hashes) == {"1" * 64, "2" * 64}
    assert set(result.upstream_ids) == {"a", "b"}


def test_dependents_names_every_artifact_built_on_a_snapshot(
    ledger, store, run, merged_record
):
    openalex_hash, _ = _seed(ledger, store, run, merged_record)
    ledger.append(
        run.record_lineage(
            TS3,
            artifact_id="figure:1",
            artifact_hash="e" * 64,
            artifact_type="figure",
            inputs=[{"id": merged_record.id}],
        )
    )
    index = LineageIndex.from_ledger(ledger)
    assert index.dependents(openalex_hash) == ["10.7717/peerj.4375", "figure:1"]
    assert index.dependents(f"sha256:{openalex_hash}") == ["10.7717/peerj.4375", "figure:1"]
    assert index.dependents("f" * 64) == []


# ---------------------------------------------------------------------------
# Stale evidence (the M3 compile-gate query)
# ---------------------------------------------------------------------------


def test_a_record_whose_snapshots_are_current_is_not_stale(ledger, store, run, merged_record):
    _seed(ledger, store, run, merged_record)
    index = LineageIndex.from_ledger(ledger)
    report = index.stale(merged_record.id, store)
    assert report.is_stale is False
    assert len(report.present_hashes) == 2
    assert report.missing_hashes == ()


def test_a_re_recorded_source_makes_the_derived_record_stale(
    ledger, store, run, merged_record
):
    openalex_hash, crossref_hash = _seed(ledger, store, run, merged_record)

    # The source moved: the same request now returns a corrected title, so re-recording it
    # replaces the snapshot bytes and the response hash changes.
    drifted = dict(OPENALEX_BODY)
    drifted["results"] = [dict(OPENALEX_BODY["results"][0], title="The State of OA (corrected)")]
    new = store.record("openalex", "works", {"filter": "doi:10.7717/peerj.4375"}, drifted,
                       retrieved_at=TS3)
    assert new.response_hash != openalex_hash

    index = LineageIndex.from_ledger(ledger)
    report = index.stale(merged_record.id, store)
    assert report.is_stale is True
    assert report.missing_hashes == (openalex_hash,)
    assert report.present_hashes == (crossref_hash,)
    assert report.to_json_dict()["is_stale"] is True


def test_stale_on_an_unknown_artifact_reports_unknown_not_stale(ledger, store, run):
    index = LineageIndex.from_ledger(ledger)
    report = index.stale("10.9999/never-derived", store)
    assert report.known is False
    assert report.is_stale is False


# ---------------------------------------------------------------------------
# Details
# ---------------------------------------------------------------------------


def test_hash_prefixes_are_normalized_on_the_join(ledger, store, run, merged_record):
    openalex_hash, crossref_hash = _seed(ledger, store, run, merged_record)
    ledger.append(
        run.record_lineage(
            TS3,
            artifact_id="prefixed",
            artifact_hash="f" * 64,
            source_response_hashes=[f"sha256:{openalex_hash}"],
        )
    )
    index = LineageIndex.from_ledger(ledger)
    assert index.resolve("prefixed").snapshot_hashes == (openalex_hash,)
    assert index.resolve_snapshots("prefixed", store)[0].response_hash == openalex_hash
    assert strip_hash_prefix(f"sha256:{crossref_hash}") == crossref_hash


def test_the_index_can_be_rebuilt_from_a_jsonl_export(ledger, store, run, merged_record, tmp_path):
    openalex_hash, crossref_hash = _seed(ledger, store, run, merged_record)
    path = ledger.export_jsonl(tmp_path / "ledger.jsonl")

    from researcher_core.provenance import load_jsonl

    index = LineageIndex.from_events(load_jsonl(path))
    assert set(index.resolve(merged_record.id).snapshot_hashes) == {openalex_hash, crossref_hash}
