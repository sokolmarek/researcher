"""SQLite response cache for live API calls.

Scope, stated plainly so it is never confused with the snapshot store:

* This cache exists to keep the kernel polite to public APIs during ordinary live use.
  It is a performance and rate-limit concern, and it lives in the user cache directory
  (platformdirs, Windows-safe per D5).
* It NEVER feeds evals. Offline tests and benchmark runs read the snapshot store under
  ``core/tests/snapshots/`` and nothing else (see :mod:`researcher_core.snapshots`).

Keyed by ``(source, endpoint, canonicalized params)``. TTL is per source with a 7-day
default. Passing ``enabled=False`` (the ``--no-cache`` override) turns every read into a
miss and every write into a no-op, without any caller-side branching.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from platformdirs import user_cache_dir

from .model import canonical_json, sha256_hex

__all__ = [
    "DEFAULT_TTL_SECONDS",
    "CacheEntry",
    "ResponseCache",
    "cache_key",
    "default_cache_path",
]

DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

APP_NAME = "researcher-core"
APP_AUTHOR = "researcher"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key        TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    endpoint   TEXT NOT NULL,
    params     TEXT NOT NULL,
    body       TEXT NOT NULL,
    stored_at  REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS responses_expires_at ON responses (expires_at);
CREATE INDEX IF NOT EXISTS responses_source ON responses (source);
"""


def user_cache_root() -> Path:
    """The researcher_core cache root. Honors ``RESEARCHER_CORE_CACHE_DIR``."""
    override = os.environ.get("RESEARCHER_CORE_CACHE_DIR")
    if override:
        return Path(override)
    return Path(user_cache_dir(APP_NAME, APP_AUTHOR))


def default_cache_path() -> Path:
    """Path of the SQLite response cache inside the platformdirs user cache dir."""
    return user_cache_root() / "responses.sqlite3"


def cache_key(source: str, endpoint: str, params: Mapping[str, Any] | None = None) -> str:
    """The cache key for one request: SHA-256 over ``(source, endpoint, params)``.

    Params are canonicalized (sorted keys, fixed separators), so two calls that pass the
    same params in a different order hit the same cache row.
    """
    payload = {
        "source": source,
        "endpoint": endpoint,
        "params": dict(params or {}),
    }
    return sha256_hex(canonical_json(payload))


@dataclass(frozen=True)
class CacheEntry:
    """One cached response body plus its bookkeeping."""

    key: str
    source: str
    endpoint: str
    params: dict[str, Any]
    body: Any
    stored_at: float
    expires_at: float

    def is_expired(self, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


class ResponseCache:
    """A TTL'd SQLite cache of raw API response bodies.

    Thread-safe: one connection guarded by a lock, opened with ``check_same_thread=False``
    so a thread-pool or an asyncio executor may share one instance. WAL mode and a busy
    timeout keep concurrent processes from tripping over each other on Windows.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        enabled: bool = True,
        default_ttl: int = DEFAULT_TTL_SECONDS,
        ttl_by_source: Mapping[str, int] | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_cache_path()
        self.enabled = enabled
        self.default_ttl = int(default_ttl)
        self.ttl_by_source: dict[str, int] = dict(ttl_by_source or {})
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    # -- construction ------------------------------------------------------

    @classmethod
    def from_env(cls, **kwargs: Any) -> ResponseCache:
        """Build a cache from the environment.

        ``RESEARCHER_CORE_NO_CACHE=1`` disables it; ``RESEARCHER_CORE_CACHE_DIR``
        relocates it; ``RESEARCHER_CORE_CACHE_TTL`` (seconds) overrides the default TTL.
        """
        enabled = os.environ.get("RESEARCHER_CORE_NO_CACHE", "").strip().lower() not in {
            "1",
            "true",
            "yes",
        }
        ttl_raw = os.environ.get("RESEARCHER_CORE_CACHE_TTL", "").strip()
        ttl = int(ttl_raw) if ttl_raw.isdigit() else DEFAULT_TTL_SECONDS
        kwargs.setdefault("enabled", enabled)
        kwargs.setdefault("default_ttl", ttl)
        return cls(**kwargs)

    @classmethod
    def disabled(cls) -> ResponseCache:
        """A cache that never stores and never hits. The ``--no-cache`` object."""
        return cls(path=default_cache_path(), enabled=False)

    # -- connection --------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = self._conn
        if conn is not None:
            return conn
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.path),
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(_SCHEMA)
        self._conn = conn
        return conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self) -> ResponseCache:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- TTL ---------------------------------------------------------------

    def ttl_for(self, source: str) -> int:
        """TTL in seconds for ``source``: the per-source override, else the default."""
        return int(self.ttl_by_source.get(source, self.default_ttl))

    # -- reads -------------------------------------------------------------

    def get_entry(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        *,
        now: float | None = None,
    ) -> CacheEntry | None:
        """The live cache entry for a request, or None on a miss or an expired row."""
        if not self.enabled:
            return None
        key = cache_key(source, endpoint, params)
        moment = time.time() if now is None else now
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT key, source, endpoint, params, body, stored_at, expires_at "
                "FROM responses WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            if moment >= float(row[6]):
                conn.execute("DELETE FROM responses WHERE key = ?", (key,))
                return None
        return CacheEntry(
            key=str(row[0]),
            source=str(row[1]),
            endpoint=str(row[2]),
            params=json.loads(row[3]),
            body=json.loads(row[4]),
            stored_at=float(row[5]),
            expires_at=float(row[6]),
        )

    def get(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        *,
        now: float | None = None,
    ) -> Any | None:
        """The cached response body, or None on a miss. Bodies are never stored as null."""
        entry = self.get_entry(source, endpoint, params, now=now)
        return None if entry is None else entry.body

    # -- writes ------------------------------------------------------------

    def set(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        body: Any,
        *,
        ttl: int | None = None,
        now: float | None = None,
    ) -> None:
        """Store a response body. A no-op when the cache is disabled or ``body`` is None."""
        if not self.enabled or body is None:
            return
        key = cache_key(source, endpoint, params)
        moment = time.time() if now is None else now
        lifetime = self.ttl_for(source) if ttl is None else int(ttl)
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO responses "
                "(key, source, endpoint, params, body, stored_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "body = excluded.body, stored_at = excluded.stored_at, "
                "expires_at = excluded.expires_at",
                (
                    key,
                    source,
                    endpoint,
                    canonical_json(dict(params or {})),
                    canonical_json(body),
                    moment,
                    moment + lifetime,
                ),
            )

    def delete(
        self, source: str, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> bool:
        """Drop one cached response. True when a row was removed."""
        if not self.enabled:
            return False
        key = cache_key(source, endpoint, params)
        with self._lock:
            conn = self._connect()
            cursor = conn.execute("DELETE FROM responses WHERE key = ?", (key,))
            return cursor.rowcount > 0

    def purge_expired(self, *, now: float | None = None) -> int:
        """Delete every expired row. Returns the number deleted."""
        if not self.enabled:
            return 0
        moment = time.time() if now is None else now
        with self._lock:
            conn = self._connect()
            cursor = conn.execute("DELETE FROM responses WHERE expires_at <= ?", (moment,))
            return int(cursor.rowcount)

    def clear(self, source: str | None = None) -> int:
        """Delete every row, or every row for one source. Returns the number deleted."""
        if not self.enabled:
            return 0
        with self._lock:
            conn = self._connect()
            if source is None:
                cursor = conn.execute("DELETE FROM responses")
            else:
                cursor = conn.execute("DELETE FROM responses WHERE source = ?", (source,))
            return int(cursor.rowcount)

    def count(self) -> int:
        """Number of rows currently stored, expired or not."""
        if not self.enabled:
            return 0
        with self._lock:
            conn = self._connect()
            row = conn.execute("SELECT COUNT(*) FROM responses").fetchone()
            return int(row[0]) if row else 0
