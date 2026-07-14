"""Tests for the snapshot layer: record, replay, diff, and the loud-failure guarantee.

The property the whole determinism claim rests on is asserted here:
:func:`test_replay_of_a_missing_snapshot_fails_loudly_and_never_calls_the_fetcher`. If that
test is ever weakened, offline runs stop being offline and the eval numbers stop meaning
anything.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx

from researcher_core.cache import ResponseCache
from researcher_core.connectors.base import BaseConnector, SourceError, SourceErrorKind
from researcher_core.model import CSLRecord
from researcher_core.snapshots import (
    Snapshot,
    SnapshotError,
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
    canonicalize,
    diff_bodies,
    request_key,
    response_hash,
)

PARAMS = {"search": "self-supervised ECG", "per-page": 25}


# ---------------------------------------------------------------------------
# Hashing and addressing
# ---------------------------------------------------------------------------


def test_response_hash_is_canonical_and_order_independent(sample_body):
    reordered = {"results": list(sample_body["results"]), "meta": dict(sample_body["meta"])}
    assert response_hash(sample_body) == response_hash(reordered)
    assert len(response_hash(sample_body)) == 64


def test_response_hash_changes_when_the_body_changes(sample_body):
    mutated = json.loads(json.dumps(sample_body))
    mutated["results"][0]["title"] = "The state of OA (revised)"
    assert response_hash(mutated) != response_hash(sample_body)


def test_canonicalize_is_deterministic():
    assert canonicalize({"b": 1, "a": 2}) == canonicalize({"a": 2, "b": 1}) == '{"a":2,"b":1}'


def test_request_key_is_param_order_independent_but_source_sensitive():
    left = request_key("openalex", "works", {"search": "ecg", "per-page": 25})
    right = request_key("openalex", "works", {"per-page": 25, "search": "ecg"})
    assert left == right
    assert request_key("crossref", "works", {"search": "ecg", "per-page": 25}) != left
    assert len(left) == 64


# ---------------------------------------------------------------------------
# Record and replay
# ---------------------------------------------------------------------------


def test_record_then_replay_round_trips_the_body(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body)

    assert store.has("openalex", "works", PARAMS)
    assert store.replay("openalex", "works", PARAMS) == sample_body


def test_record_writes_a_content_addressed_file(store: SnapshotStore, sample_body):
    snapshot = store.record("openalex", "works", PARAMS, sample_body)
    path = store.path_for("openalex", "works", PARAMS)

    assert path.is_file()
    assert path.parent.name == "openalex"
    assert path.stem == request_key("openalex", "works", PARAMS)
    assert snapshot.response_hash == response_hash(sample_body)


def test_snapshot_record_carries_the_five_required_fields(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body, retrieved_at="2026-07-14T12:00:00Z")
    path = store.path_for("openalex", "works", PARAMS)
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert set(raw) >= {
        "source",
        "request_params",
        "response_body",
        "response_hash",
        "retrieved_at",
    }
    assert raw["source"] == "openalex"
    assert raw["request_params"] == PARAMS
    assert raw["response_body"] == sample_body
    assert raw["response_hash"] == response_hash(sample_body)
    assert raw["retrieved_at"] == "2026-07-14T12:00:00Z"


def test_replay_round_trip_is_byte_identical(store: SnapshotStore, sample_body):
    """The D15 round-trip: record, load, re-serialize, and get the same bytes back."""
    store.record("openalex", "works", PARAMS, sample_body, retrieved_at="2026-07-14T12:00:00Z")
    path = store.path_for("openalex", "works", PARAMS)
    first_bytes = path.read_bytes()

    loaded = store.load("openalex", "works", PARAMS)
    assert loaded.serialize().encode("utf-8") == first_bytes

    # Re-recording the same body at the same timestamp reproduces the file exactly, so a
    # snapshot refresh that changes nothing produces an empty diff in git.
    store.record("openalex", "works", PARAMS, sample_body, retrieved_at="2026-07-14T12:00:00Z")
    assert path.read_bytes() == first_bytes


def test_written_snapshots_use_lf_line_endings(store: SnapshotStore, sample_body):
    # Windows-first (D5): a CRLF write would make every snapshot file churn in git and
    # would break byte-identical comparison across platforms.
    store.record("openalex", "works", PARAMS, sample_body)
    raw = store.path_for("openalex", "works", PARAMS).read_bytes()
    assert b"\r\n" not in raw


def test_replay_of_a_missing_snapshot_fails_loudly_and_never_calls_the_fetcher(
    store: SnapshotStore,
):
    """The load-bearing property: replay NEVER silently falls through to a live call."""
    calls: list[str] = []

    def fetcher():
        calls.append("live")
        return {"never": "reached"}

    session = SnapshotSession(store, SnapshotMode.REPLAY)

    with pytest.raises(SnapshotMissingError) as excinfo:
        session.fetch("openalex", "works", PARAMS, fetcher)

    assert calls == []
    message = str(excinfo.value)
    assert "openalex" in message
    assert "works" in message
    assert "--record" in message
    assert excinfo.value.path == store.path_for("openalex", "works", PARAMS)


def test_async_replay_of_a_missing_snapshot_also_fails_loudly(store: SnapshotStore):
    calls: list[str] = []

    async def fetcher():
        calls.append("live")
        return {"never": "reached"}

    session = SnapshotSession(store, SnapshotMode.REPLAY)

    with pytest.raises(SnapshotMissingError):
        asyncio.run(session.afetch("openalex", "works", PARAMS, fetcher))

    assert calls == []


def test_missing_snapshot_error_is_not_a_source_error(store: SnapshotStore):
    """A missing snapshot is a defect in the snapshot set, not a source outage.

    Per-source error isolation catches SourceError. If SnapshotMissingError were a subclass,
    a missing snapshot would be silently downgraded to a source_error outcome and the
    offline suite would go quietly green while testing nothing.
    """
    from researcher_core.connectors.base import SourceError

    error = SnapshotMissingError("openalex", "works", PARAMS, store.path_for("openalex", "w", {}))
    assert not isinstance(error, SourceError)


def test_replay_of_a_wrong_param_set_is_a_miss(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body)

    with pytest.raises(SnapshotMissingError):
        store.replay("openalex", "works", {"search": "something else"})


# ---------------------------------------------------------------------------
# Session modes
# ---------------------------------------------------------------------------


def test_record_mode_calls_the_fetcher_and_writes_the_snapshot(
    record_session: SnapshotSession, sample_body
):
    calls: list[str] = []

    def fetcher():
        calls.append("live")
        return sample_body

    body = record_session.fetch("openalex", "works", PARAMS, fetcher)

    assert body == sample_body
    assert calls == ["live"]
    assert record_session.store.has("openalex", "works", PARAMS)
    assert record_session.store.replay("openalex", "works", PARAMS) == sample_body


def test_record_mode_then_replay_mode_is_a_closed_loop(store: SnapshotStore, sample_body):
    recorder = SnapshotSession(store, SnapshotMode.RECORD)
    recorder.fetch("openalex", "works", PARAMS, lambda: sample_body)

    def must_not_run():
        raise AssertionError("replay mode called the fetcher")

    replayer = SnapshotSession(store, SnapshotMode.REPLAY)
    assert replayer.fetch("openalex", "works", PARAMS, must_not_run) == sample_body


def test_live_mode_calls_the_fetcher_and_writes_no_snapshot(
    store: SnapshotStore, sample_body
):
    session = SnapshotSession(store, SnapshotMode.LIVE)

    assert session.fetch("openalex", "works", PARAMS, lambda: sample_body) == sample_body
    assert not store.has("openalex", "works", PARAMS)
    assert store.count() == 0


def test_live_mode_consults_the_cache(store: SnapshotStore, cache: ResponseCache, sample_body):
    session = SnapshotSession(store, SnapshotMode.LIVE, cache=cache)
    calls: list[str] = []

    def fetcher():
        calls.append("live")
        return sample_body

    assert session.fetch("openalex", "works", PARAMS, fetcher) == sample_body
    assert session.fetch("openalex", "works", PARAMS, fetcher) == sample_body
    assert calls == ["live"]  # the second call was served from the cache


def test_record_mode_bypasses_the_cache_read(
    store: SnapshotStore, cache: ResponseCache, sample_body
):
    # --record means "go and see what the API says now", so a warm cache must not shortcut
    # it. Otherwise a refresh would re-record the stale body it already had.
    cache.set("openalex", "works", PARAMS, {"stale": True})
    session = SnapshotSession(store, SnapshotMode.RECORD, cache=cache)

    body = session.fetch("openalex", "works", PARAMS, lambda: sample_body)

    assert body == sample_body
    assert store.replay("openalex", "works", PARAMS) == sample_body
    assert cache.get("openalex", "works", PARAMS) == sample_body


def test_replay_mode_ignores_the_cache_entirely(
    store: SnapshotStore, cache: ResponseCache, sample_body
):
    # A warm runtime cache must never satisfy an eval replay: the runtime cache never feeds
    # evals, and a snapshot miss stays a miss.
    cache.set("openalex", "works", PARAMS, sample_body)
    session = SnapshotSession(store, SnapshotMode.REPLAY, cache=cache)

    with pytest.raises(SnapshotMissingError):
        session.fetch("openalex", "works", PARAMS, lambda: sample_body)


def test_async_record_and_replay(store: SnapshotStore, sample_body):
    async def fetcher():
        return sample_body

    recorder = SnapshotSession(store, SnapshotMode.RECORD)
    assert asyncio.run(recorder.afetch("openalex", "works", PARAMS, fetcher)) == sample_body

    replayer = SnapshotSession(store, SnapshotMode.REPLAY)
    assert asyncio.run(replayer.afetch("openalex", "works", PARAMS, fetcher)) == sample_body


def test_session_from_env_reads_mode_and_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_MODE", "record")
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(tmp_path / "snaps"))

    session = SnapshotSession.from_env()

    assert session.mode is SnapshotMode.RECORD
    assert session.is_recording
    assert session.store.root == tmp_path / "snaps"


def test_snapshot_mode_parse_rejects_nonsense():
    assert SnapshotMode.parse(None) is SnapshotMode.LIVE
    assert SnapshotMode.parse("REPLAY") is SnapshotMode.REPLAY
    assert SnapshotMode.parse(SnapshotMode.RECORD) is SnapshotMode.RECORD

    with pytest.raises(SnapshotError):
        SnapshotMode.parse("sometimes")


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------


def test_a_tampered_snapshot_body_is_detected(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body)
    path = store.path_for("openalex", "works", PARAMS)

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["response_body"]["results"][0]["title"] = "Silently edited"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SnapshotError, match="integrity failure"):
        store.load("openalex", "works", PARAMS)


def test_a_snapshot_missing_a_required_field_is_rejected(store: SnapshotStore, tmp_path: Path):
    path = store.path_for_key("openalex", "a" * 64)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": "openalex"}), encoding="utf-8")

    with pytest.raises(SnapshotError, match="missing required field"):
        store.load_path(path)


def test_written_snapshot_validates_against_the_schema(store: SnapshotStore, sample_body):
    """A snapshot file on disk validates against core/schemas/snapshot.schema.json.

    jsonschema is a dev dependency, so this check lives in the test suite and never in the
    runtime import path.
    """
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "snapshot.schema.json"
    if not schema_path.is_file():
        pytest.skip("snapshot.schema.json is not present yet")

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    store.record("openalex", "works", PARAMS, sample_body)
    written = json.loads(store.path_for("openalex", "works", PARAMS).read_text(encoding="utf-8"))

    jsonschema.validate(instance=written, schema=schema)


def test_snapshot_json_round_trip(sample_body):
    snapshot = Snapshot.create(
        "openalex", "works", PARAMS, sample_body, retrieved_at="2026-01-01T00:00:00Z"
    )
    restored = Snapshot.from_json_dict(snapshot.to_json_dict())

    assert restored == snapshot
    restored.verify()


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------


def test_iter_snapshots_and_sources(store: SnapshotStore, sample_body):
    store.record("openalex", "works", {"search": "a"}, sample_body)
    store.record("openalex", "works", {"search": "b"}, sample_body)
    store.record("crossref", "works", {"query": "a"}, {"message": {}})

    assert store.sources() == ["crossref", "openalex"]
    assert store.count() == 3
    assert store.count("openalex") == 2
    assert {s.source for s in store.iter_snapshots()} == {"openalex", "crossref"}


def test_delete_removes_a_snapshot(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body)

    assert store.delete("openalex", "works", PARAMS) is True
    assert store.delete("openalex", "works", PARAMS) is False
    assert not store.has("openalex", "works", PARAMS)


def test_empty_store_enumerates_cleanly(store: SnapshotStore):
    assert store.sources() == []
    assert store.count() == 0
    assert list(store.iter_snapshots()) == []


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def test_diff_reports_no_fields_when_nothing_drifted(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body)

    report = store.diff("openalex", "works", PARAMS, sample_body)

    assert report.changed is False
    assert report.fields == []
    assert report.stored_hash == report.live_hash


def test_diff_reports_changed_added_and_removed_fields(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body)

    live = json.loads(json.dumps(sample_body))
    live["results"][0]["title"] = "The state of OA (revised)"
    live["results"][0]["is_retracted"] = True
    live["results"][1].pop("doi")
    live["meta"]["next_cursor"] = "abc"

    report = store.diff("openalex", "works", PARAMS, live)

    assert report.changed is True
    by_path = {f.path: f for f in report.fields}

    assert by_path["results[0].title"].kind == "changed"
    assert by_path["results[0].title"].stored == "The state of OA"
    assert by_path["results[0].title"].live == "The state of OA (revised)"

    assert by_path["results[0].is_retracted"].kind == "changed"
    assert by_path["results[0].is_retracted"].live is True

    assert by_path["results[1].doi"].kind == "removed"
    assert by_path["results[1].doi"].stored == "https://doi.org/10.1000/xyz"

    assert by_path["meta.next_cursor"].kind == "added"
    assert by_path["meta.next_cursor"].live == "abc"

    payload = report.to_json_dict()
    assert payload["changed"] is True
    assert payload["source"] == "openalex"
    assert len(payload["fields"]) == 4


def test_diff_reports_a_vanished_record(store: SnapshotStore, sample_body):
    store.record("openalex", "works", PARAMS, sample_body)

    live = json.loads(json.dumps(sample_body))
    live["results"].pop()
    live["meta"]["count"] = 1

    report = store.diff("openalex", "works", PARAMS, live)
    kinds = {(f.path, f.kind) for f in report.fields}

    assert ("results[1]", "removed") in kinds
    assert ("meta.count", "changed") in kinds


def test_diff_bodies_on_scalars_and_type_changes():
    assert diff_bodies(1, 1) == []
    changed = diff_bodies({"n": 1}, {"n": "1"})
    assert len(changed) == 1
    assert changed[0].kind == "changed"
    assert changed[0].path == "n"


def test_diff_of_a_missing_snapshot_fails_loudly(store: SnapshotStore):
    with pytest.raises(SnapshotMissingError):
        store.diff("openalex", "works", PARAMS, {"live": True})


# ---------------------------------------------------------------------------
# BaseConnector routing: the snapshot layer is baked into the base class, so a
# connector cannot forget to use it. These tests assert that from the outside.
# ---------------------------------------------------------------------------

BASE_URL = "https://api.example.test"


class ProbeConnector(BaseConnector):
    """A minimal connector over a mocked HTTP endpoint."""

    name = "probe"
    base_url = BASE_URL
    capabilities = frozenset({"search", "get_by_id", "resolve_doi"})

    async def search(self, query: str, *, limit: int = 25, since: int | None = None):
        body = await self.request_json("works", {"q": query, "limit": limit})
        items = (body or {}).get("results", [])
        return [CSLRecord(title=i["title"], DOI=i.get("doi", "")) for i in items]

    async def get_by_id(self, identifier: str):
        body = await self.request_json(f"works/{identifier}", {})
        return None if body is None else CSLRecord(title=body["title"])

    async def resolve_doi(self, doi: str):
        return await self.get_by_id(doi)


PROBE_BODY = {"results": [{"title": "Self-supervised ECG", "doi": "10.1/ecg"}]}


def test_connector_in_record_mode_calls_the_api_and_writes_a_snapshot(store: SnapshotStore):
    session = SnapshotSession(store, SnapshotMode.RECORD, retrieved_at="2026-07-14T12:00:00Z")

    with respx.mock:
        route = respx.get(f"{BASE_URL}/works").mock(
            return_value=httpx.Response(200, json=PROBE_BODY)
        )
        records = asyncio.run(_run(ProbeConnector(snapshots=session), "ecg"))

    assert route.call_count == 1
    assert [r.title for r in records] == ["Self-supervised ECG"]
    assert store.has("probe", "works", {"q": "ecg", "limit": 25})


def test_connector_in_replay_mode_makes_no_http_call_at_all(store: SnapshotStore):
    store.record("probe", "works", {"q": "ecg", "limit": 25}, PROBE_BODY)
    session = SnapshotSession(store, SnapshotMode.REPLAY)

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{BASE_URL}/works").mock(
            return_value=httpx.Response(500, json={"boom": True})
        )
        records = asyncio.run(_run(ProbeConnector(snapshots=session), "ecg"))

    # The mocked route would have returned a 500. It was never reached: replay reads the
    # snapshot store and nothing else.
    assert route.call_count == 0
    assert [r.title for r in records] == ["Self-supervised ECG"]


def test_connector_in_replay_mode_fails_loudly_on_an_unrecorded_query(store: SnapshotStore):
    session = SnapshotSession(store, SnapshotMode.REPLAY)

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{BASE_URL}/works").mock(
            return_value=httpx.Response(200, json=PROBE_BODY)
        )
        with pytest.raises(SnapshotMissingError):
            asyncio.run(_run(ProbeConnector(snapshots=session), "never recorded"))

    assert route.call_count == 0


def test_connector_record_then_replay_is_byte_identical(store: SnapshotStore):
    session = SnapshotSession(store, SnapshotMode.RECORD, retrieved_at="2026-07-14T12:00:00Z")
    with respx.mock:
        respx.get(f"{BASE_URL}/works").mock(return_value=httpx.Response(200, json=PROBE_BODY))
        first = asyncio.run(_run(ProbeConnector(snapshots=session), "ecg"))

    replayer = SnapshotSession(store, SnapshotMode.REPLAY)
    second = asyncio.run(_run(ProbeConnector(snapshots=replayer), "ecg"))
    third = asyncio.run(_run(ProbeConnector(snapshots=replayer), "ecg"))

    # D15: identical snapshot, configuration, and parser version give byte-identical output.
    serialized = [
        json.dumps([r.to_csl_json() for r in rs], sort_keys=True)
        for rs in (first, second, third)
    ]
    assert serialized[0] == serialized[1] == serialized[2]


def test_connector_404_is_a_clean_negative_not_a_source_error(store: SnapshotStore):
    session = SnapshotSession(store, SnapshotMode.LIVE)

    with respx.mock:
        respx.get(f"{BASE_URL}/works/10.1/missing").mock(return_value=httpx.Response(404))
        connector = ProbeConnector(snapshots=session)
        result = asyncio.run(_close_after(connector, connector.get_by_id("10.1/missing")))

    # A clean negative is None. It is emphatically NOT a SourceError, because per D9 a clean
    # negative can support `unresolvable` while a source error can only force `inconclusive`.
    assert result is None


def test_connector_server_error_raises_source_error(store: SnapshotStore):
    session = SnapshotSession(store, SnapshotMode.LIVE)

    class NoRetry(ProbeConnector):
        max_retries = 0

    with respx.mock:
        respx.get(f"{BASE_URL}/works").mock(return_value=httpx.Response(503))
        connector = NoRetry(snapshots=session)
        with pytest.raises(SourceError) as excinfo:
            asyncio.run(_close_after(connector, connector.search("ecg")))

    assert excinfo.value.kind is SourceErrorKind.SERVER_ERROR
    assert excinfo.value.status_code == 503
    assert excinfo.value.source == "probe"


def test_connector_timeout_raises_source_error(store: SnapshotStore):
    session = SnapshotSession(store, SnapshotMode.LIVE)

    class NoRetry(ProbeConnector):
        max_retries = 0

    with respx.mock:
        respx.get(f"{BASE_URL}/works").mock(side_effect=httpx.ConnectTimeout("too slow"))
        connector = NoRetry(snapshots=session)
        with pytest.raises(SourceError) as excinfo:
            asyncio.run(_close_after(connector, connector.search("ecg")))

    assert excinfo.value.kind is SourceErrorKind.TIMEOUT


async def _run(connector: BaseConnector, query: str):
    async with connector:
        return await connector.search(query)


async def _close_after(connector: BaseConnector, coro):
    async with connector:
        return await coro
