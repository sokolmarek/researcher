"""Offline / private mode (M5.1).

Every test here is offline by construction: no test opens a socket, and several assert that the
fetcher an offline session is handed is never called. A snapshot store under ``tmp_path`` stands in
for the eval store, so nothing touches the real cache dir or the in-repo snapshots.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from researcher_core.cache import ResponseCache
from researcher_core.config import (
    OFFLINE_ENV,
    Config,
    OfflineMiss,
    OfflineMissError,
    OfflineSession,
    build_session,
    is_offline,
)
from researcher_core.snapshots import (
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)

SOURCE = "openalex"
ENDPOINT = "works"
PARAMS = {"search": "self-supervised ECG", "per-page": 5}
BODY = {"results": [{"id": "W1", "title": "A real recorded response"}]}


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "snapshots")


@pytest.fixture
def recorded_store(store: SnapshotStore) -> SnapshotStore:
    store.record(SOURCE, ENDPOINT, PARAMS, BODY, retrieved_at="2026-07-14T12:00:00Z")
    return store


def _boom_sync() -> object:
    raise AssertionError("offline mode called the live fetcher")


async def _boom_async() -> object:
    raise AssertionError("offline mode awaited the live fetcher")


# ---------------------------------------------------------------------------
# is_offline
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "  On  "])
def test_is_offline_true_values(value: str) -> None:
    assert is_offline(env={OFFLINE_ENV: value}) is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_is_offline_false_values(value: str) -> None:
    assert is_offline(env={OFFLINE_ENV: value}) is False


def test_is_offline_absent_env_is_false() -> None:
    assert is_offline(env={}) is False


def test_is_offline_explicit_flag_wins_both_ways() -> None:
    # Explicit True forces on even with the env off, and explicit False forces off even with it on.
    assert is_offline(True, env={OFFLINE_ENV: "0"}) is True
    assert is_offline(False, env={OFFLINE_ENV: "1"}) is False


def test_is_offline_reads_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OFFLINE_ENV, "1")
    assert is_offline() is True
    monkeypatch.delenv(OFFLINE_ENV, raising=False)
    assert is_offline() is False


# ---------------------------------------------------------------------------
# OfflineSession over a present snapshot: it replays, never goes live
# ---------------------------------------------------------------------------


def test_offline_session_replays_present_snapshot(recorded_store: SnapshotStore) -> None:
    session = OfflineSession(recorded_store)
    assert session.mode is SnapshotMode.REPLAY
    assert session.resolve(SOURCE, ENDPOINT, PARAMS) == BODY
    assert session.replay(SOURCE, ENDPOINT, PARAMS) == BODY


def test_offline_fetch_returns_body_without_calling_fetcher(recorded_store: SnapshotStore) -> None:
    session = OfflineSession(recorded_store)
    assert session.fetch(SOURCE, ENDPOINT, PARAMS, _boom_sync) == BODY


def test_offline_afetch_returns_body_without_awaiting_fetcher(
    recorded_store: SnapshotStore,
) -> None:
    session = OfflineSession(recorded_store)
    body = asyncio.run(session.afetch(SOURCE, ENDPOINT, PARAMS, _boom_async))
    assert body == BODY


# ---------------------------------------------------------------------------
# A miss: typed OfflineMiss, no live call, no unhandled raise
# ---------------------------------------------------------------------------


def test_miss_resolve_returns_typed_offline_miss(store: SnapshotStore) -> None:
    session = OfflineSession(store)
    miss = session.resolve(SOURCE, ENDPOINT, PARAMS)
    assert isinstance(miss, OfflineMiss)
    assert miss.outcome == "offline-miss"
    assert miss.source == SOURCE
    assert miss.endpoint == ENDPOINT
    assert miss.params == PARAMS
    payload = miss.to_json_dict()
    assert payload["outcome"] == "offline-miss"
    assert payload["source"] == SOURCE
    assert "network" in payload["message"].lower()


def test_miss_fetch_raises_typed_error_and_never_calls_fetcher(store: SnapshotStore) -> None:
    session = OfflineSession(store)
    with pytest.raises(OfflineMissError) as excinfo:
        session.fetch(SOURCE, ENDPOINT, PARAMS, _boom_sync)
    # The typed error carries the same typed payload, and is a SnapshotMissingError so existing
    # re-raise handling still routes it rather than degrading it into a source error.
    assert isinstance(excinfo.value, SnapshotMissingError)
    assert excinfo.value.miss.outcome == "offline-miss"
    assert excinfo.value.source == SOURCE


def test_miss_afetch_raises_typed_error_and_never_awaits_fetcher(store: SnapshotStore) -> None:
    session = OfflineSession(store)
    with pytest.raises(OfflineMissError):
        asyncio.run(session.afetch(SOURCE, ENDPOINT, PARAMS, _boom_async))


# ---------------------------------------------------------------------------
# Cache fallback: offline reads the response cache when the snapshot store misses
# ---------------------------------------------------------------------------


def test_offline_falls_back_to_cache_on_snapshot_miss(
    store: SnapshotStore, tmp_path: Path
) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite3")
    cached_body = {"results": [{"id": "W2", "title": "Answered from the cache"}]}
    cache.set(SOURCE, ENDPOINT, PARAMS, cached_body)
    try:
        session = OfflineSession(store, cache=cache)
        assert session.resolve(SOURCE, ENDPOINT, PARAMS) == cached_body
        # And the fetch path returns it too, still without a live call.
        assert session.fetch(SOURCE, ENDPOINT, PARAMS, _boom_sync) == cached_body
    finally:
        cache.close()


def test_offline_miss_when_both_snapshot_and_cache_are_empty(
    store: SnapshotStore, tmp_path: Path
) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite3")
    try:
        session = OfflineSession(store, cache=cache)
        assert isinstance(session.resolve(SOURCE, ENDPOINT, PARAMS), OfflineMiss)
    finally:
        cache.close()


# ---------------------------------------------------------------------------
# OfflineMiss.from_missing
# ---------------------------------------------------------------------------


def test_offline_miss_from_missing_carries_request_identity(store: SnapshotStore) -> None:
    path = store.path_for(SOURCE, ENDPOINT, PARAMS)
    err = SnapshotMissingError(SOURCE, ENDPOINT, PARAMS, path)
    miss = OfflineMiss.from_missing(err)
    assert miss.source == SOURCE
    assert miss.endpoint == ENDPOINT
    assert miss.params == PARAMS
    assert miss.path == str(path)
    assert miss.outcome == "offline-miss"


# ---------------------------------------------------------------------------
# build_session: the helper the CLI's build_session calls
# ---------------------------------------------------------------------------


def test_build_session_offline_flag_returns_offline_session(
    store: SnapshotStore, tmp_path: Path
) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite3")
    try:
        session = build_session(offline=True, store=store, cache=cache)
        assert isinstance(session, OfflineSession)
        assert session.mode is SnapshotMode.REPLAY
        assert isinstance(session.resolve(SOURCE, ENDPOINT, PARAMS), OfflineMiss)
    finally:
        cache.close()


def test_build_session_offline_env_returns_offline_session(
    store: SnapshotStore, tmp_path: Path
) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite3")
    try:
        session = build_session(store=store, cache=cache, env={OFFLINE_ENV: "1"})
        assert isinstance(session, OfflineSession)
    finally:
        cache.close()


def test_build_session_offline_ignores_record(store: SnapshotStore, tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite3")
    try:
        # record has no meaning offline (it needs a live call); the session is still REPLAY.
        session = build_session(offline=True, record=True, store=store, cache=cache)
        assert isinstance(session, OfflineSession)
        assert session.mode is SnapshotMode.REPLAY
    finally:
        cache.close()


def _clear_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(OFFLINE_ENV, raising=False)
    monkeypatch.delenv("RESEARCHER_CORE_SNAPSHOT_MODE", raising=False)
    monkeypatch.delenv("RESEARCHER_CORE_SNAPSHOT_DIR", raising=False)
    monkeypatch.setenv("RESEARCHER_CORE_CACHE_DIR", str(tmp_path / "cache"))


def test_build_session_non_offline_is_plain_live_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_env(monkeypatch, tmp_path)
    session = build_session()
    assert type(session) is SnapshotSession
    assert not isinstance(session, OfflineSession)
    assert session.mode is SnapshotMode.LIVE


def test_build_session_record_flag_selects_record_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_env(monkeypatch, tmp_path)
    session = build_session(record=True)
    assert not isinstance(session, OfflineSession)
    assert session.mode is SnapshotMode.RECORD


def test_build_session_honors_snapshot_dir_override_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, recorded_store: SnapshotStore
) -> None:
    # An eval/benchmark run points the kernel at a snapshot set; offline must replay from it.
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(recorded_store.root))
    monkeypatch.setenv("RESEARCHER_CORE_CACHE_DIR", str(tmp_path / "cache"))
    session = build_session(offline=True)
    assert isinstance(session, OfflineSession)
    assert session.resolve(SOURCE, ENDPOINT, PARAMS) == BODY


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_from_env_resolves_offline_and_builds_session(
    store: SnapshotStore, tmp_path: Path
) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite3")
    try:
        config = Config.from_env(offline=True, store=store, cache=cache)
        assert config.is_offline() is True
        session = config.build_session()
        assert isinstance(session, OfflineSession)
        assert isinstance(session.resolve(SOURCE, ENDPOINT, PARAMS), OfflineMiss)
    finally:
        cache.close()


def test_config_non_offline_builds_plain_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_env(monkeypatch, tmp_path)
    config = Config.from_env(env={})
    assert config.is_offline() is False
    session = config.build_session()
    assert not isinstance(session, OfflineSession)
