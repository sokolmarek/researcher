"""Shared test fixtures.

Two invariants this file enforces for every test in the suite:

1. Tests never touch the user's real cache directory or real snapshot store. Both are
   redirected into tmp_path via the environment variables the kernel reads.
2. Tests never go to the network. The default snapshot mode is ``replay``, so any code
   path that tries to reach an API fails loudly with SnapshotMissingError instead of
   quietly hitting the internet. Tests that exercise live-shaped behavior opt into
   ``record`` or ``live`` mode explicitly, with a stub fetcher.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from researcher_core.cache import ResponseCache
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore

_ENV_VARS = (
    "RESEARCHER_CORE_CACHE_DIR",
    "RESEARCHER_CORE_CACHE_TTL",
    "RESEARCHER_CORE_NO_CACHE",
    "RESEARCHER_CORE_SNAPSHOT_DIR",
    "RESEARCHER_CORE_SNAPSHOT_MODE",
)


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point every kernel path at tmp_path and force offline replay by default."""
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RESEARCHER_CORE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_MODE", SnapshotMode.REPLAY.value)
    yield


@pytest.fixture()
def cache(tmp_path: Path) -> Iterator[ResponseCache]:
    """A fresh, isolated SQLite response cache."""
    instance = ResponseCache(tmp_path / "cache" / "responses.sqlite3")
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture()
def store(tmp_path: Path) -> SnapshotStore:
    """A fresh, empty snapshot store rooted in tmp_path."""
    return SnapshotStore(tmp_path / "snapshots")


@pytest.fixture()
def replay_session(store: SnapshotStore) -> SnapshotSession:
    """A session in replay mode over the empty tmp store."""
    return SnapshotSession(store, SnapshotMode.REPLAY)


@pytest.fixture()
def record_session(store: SnapshotStore) -> SnapshotSession:
    """A session in record mode with a pinned timestamp, so writes are byte-stable."""
    return SnapshotSession(store, SnapshotMode.RECORD, retrieved_at="2026-07-14T12:00:00Z")


@pytest.fixture()
def sample_body() -> dict:
    """A response body shaped like an OpenAlex ``works`` page, with nesting and unicode."""
    return {
        "meta": {"count": 2, "page": 1},
        "results": [
            {
                "id": "https://openalex.org/W2741809807",
                "doi": "https://doi.org/10.7717/peerj.4375",
                "title": "The state of OA",
                "publication_year": 2018,
                "authorships": [{"author": {"display_name": "Heather Piwowar"}}],
                "is_retracted": False,
            },
            {
                "id": "https://openalex.org/W1234567890",
                "doi": "https://doi.org/10.1000/xyz",
                "title": "Ubiquitous naive Bayes",
                "publication_year": 2020,
                "authorships": [{"author": {"display_name": "Jose Ramon Nunez"}}],
                "is_retracted": False,
            },
        ],
    }
