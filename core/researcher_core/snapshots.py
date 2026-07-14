"""Content-addressed snapshot record / replay / diff (D15).

This is the layer the determinism claim rests on. "Deterministic" means replayable given
(1) a source snapshot, (2) a configuration, and (3) a parser version: identical inputs
under those three produce byte-identical output. Live indexes cannot return identical
records forever, so determinism is never claimed for live calls.

Record shape (the five fields D15 specifies, plus additive bookkeeping so a snapshot file
is self-describing)::

    {
      "source":         "openalex",
      "request_params": {"search": "self-supervised ECG", "per-page": 25},
      "response_body":  {...},                  # the raw parsed JSON the API returned
      "response_hash":  "<sha256 of the canonicalized response_body>",
      "retrieved_at":   "2026-07-14T12:00:00Z",
      # additive, optional for consumers:
      "endpoint":       "works",
      "request_key":    "<sha256 of (source, endpoint, canonicalized params)>",
      "schema_version": "1.0"
    }

Written records validate against ``core/schemas/snapshot.schema.json``.

Two stores, one purpose each:

* **Eval store** (:meth:`SnapshotStore.eval_store`): ``core/tests/snapshots/``, in the repo,
  organized per connector. The ONLY thing offline tests and benchmark runs read.
* **Runtime store** (:meth:`SnapshotStore.runtime_store`): the platformdirs user cache dir.
  Written by ``--record`` during ordinary use. It NEVER feeds evals.

Three modes (:class:`SnapshotMode`):

* ``LIVE``    - ordinary use: call the API, consult the TTL cache, write no snapshots.
* ``RECORD``  - ``--record``: call the API (bypassing the cache read), write the snapshot.
* ``REPLAY``  - tests and eval runners: read snapshots only. A MISSING SNAPSHOT RAISES
  :class:`SnapshotMissingError`. It never, under any circumstance, falls through to a live
  call. That property is what makes the offline suite meaningful, so it is enforced here in
  one place rather than trusted to each connector.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .cache import ResponseCache, user_cache_root
from .model import canonical_json, sha256_hex

__all__ = [
    "SNAPSHOT_SCHEMA_VERSION",
    "FieldDiff",
    "Snapshot",
    "SnapshotDiff",
    "SnapshotError",
    "SnapshotMissingError",
    "SnapshotMode",
    "SnapshotSession",
    "SnapshotStore",
    "canonicalize",
    "diff_bodies",
    "request_key",
    "response_hash",
    "utc_now",
]

#: Version of the snapshot record shape itself. A version string, not an integer, so it
#: validates against ``core/schemas/snapshot.schema.json``. Bump the minor for additive
#: fields, the major for anything that invalidates stored snapshots.
SNAPSHOT_SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SnapshotError(RuntimeError):
    """Base class for snapshot-store failures."""


class SnapshotMissingError(SnapshotError):
    """Replay was asked for a snapshot that does not exist.

    This is deliberately loud and deliberately NOT a
    :class:`researcher_core.connectors.base.SourceError`: it is a defect in the snapshot
    set, not a source outage, and it must never be swallowed by per-source error isolation
    or degraded into a ``source_error`` outcome. Fix the snapshot set, or re-record.
    """

    def __init__(self, source: str, endpoint: str, params: Mapping[str, Any], path: Path) -> None:
        self.source = source
        self.endpoint = endpoint
        self.params = dict(params)
        self.path = path
        super().__init__(
            f"No snapshot for source={source!r} endpoint={endpoint!r} "
            f"params={canonical_json(dict(params))} (expected at {path}). "
            "Replay mode never falls through to a live call. Re-record this request "
            "with --record, or fix the request parameters."
        )


# ---------------------------------------------------------------------------
# Canonicalization and hashing
# ---------------------------------------------------------------------------


def canonicalize(body: Any) -> str:
    """The single canonical serialization of a response body: sorted keys, fixed separators."""
    return canonical_json(body)


def response_hash(body: Any) -> str:
    """SHA-256 hex digest of the canonicalized response body. Content-addresses a snapshot."""
    return sha256_hex(canonicalize(body))


def request_key(source: str, endpoint: str, params: Mapping[str, Any] | None = None) -> str:
    """SHA-256 hex digest of ``(source, endpoint, canonicalized params)``. Addresses a request."""
    payload = {"source": source, "endpoint": endpoint, "params": dict(params or {})}
    return sha256_hex(canonical_json(payload))


def utc_now() -> str:
    """Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Mode
# ---------------------------------------------------------------------------


class SnapshotMode(str, Enum):
    """How a session resolves a request."""

    LIVE = "live"
    RECORD = "record"
    REPLAY = "replay"

    @classmethod
    def parse(
        cls,
        value: str | SnapshotMode | None,
        default: SnapshotMode | None = None,
    ) -> SnapshotMode:
        """Coerce a mode name into a :class:`SnapshotMode`. Unknown names raise."""
        if isinstance(value, cls):
            return value
        if value is None or str(value).strip() == "":
            return default or cls.LIVE
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            valid = ", ".join(m.value for m in cls)
            raise SnapshotError(f"Unknown snapshot mode {value!r}. Valid modes: {valid}") from exc


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    """One recorded API response, content-addressed by :attr:`response_hash`."""

    source: str
    request_params: dict[str, Any]
    response_body: Any
    response_hash: str
    retrieved_at: str
    endpoint: str = ""
    request_key: str = ""
    schema_version: str = SNAPSHOT_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        response_body: Any,
        *,
        retrieved_at: str | None = None,
    ) -> Snapshot:
        """Build a snapshot, computing both hashes from the body and the request."""
        request_params = dict(params or {})
        return cls(
            source=source,
            request_params=request_params,
            response_body=response_body,
            response_hash=response_hash(response_body),
            retrieved_at=retrieved_at or utc_now(),
            endpoint=endpoint,
            request_key=request_key(source, endpoint, request_params),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "endpoint": self.endpoint,
            "request_key": self.request_key,
            "request_params": self.request_params,
            "response_hash": self.response_hash,
            "retrieved_at": self.retrieved_at,
            "response_body": self.response_body,
        }

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> Snapshot:
        try:
            return cls(
                source=str(data["source"]),
                request_params=dict(data.get("request_params") or {}),
                response_body=data["response_body"],
                response_hash=str(data["response_hash"]),
                retrieved_at=str(data["retrieved_at"]),
                endpoint=str(data.get("endpoint") or ""),
                request_key=str(data.get("request_key") or ""),
                schema_version=str(data.get("schema_version") or SNAPSHOT_SCHEMA_VERSION),
            )
        except KeyError as exc:
            raise SnapshotError(
                f"Snapshot record is missing required field {exc.args[0]!r}"
            ) from exc

    def verify(self) -> None:
        """Raise :class:`SnapshotError` when the stored hash does not match the stored body."""
        actual = response_hash(self.response_body)
        if actual != self.response_hash:
            raise SnapshotError(
                f"Snapshot integrity failure for source={self.source!r} "
                f"endpoint={self.endpoint!r}: stored response_hash={self.response_hash} "
                f"but the body hashes to {actual}."
            )

    def serialize(self) -> str:
        """The on-disk text of this snapshot. Deterministic and LF-terminated."""
        return json.dumps(
            self.to_json_dict(),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldDiff:
    """One field-level difference between a stored body and a live-shaped body."""

    path: str  # dotted / indexed path, e.g. "results[0].title"
    kind: str  # "changed" | "added" | "removed"
    stored: Any = None
    live: Any = None

    def to_json_dict(self) -> dict[str, Any]:
        return {"path": self.path, "kind": self.kind, "stored": self.stored, "live": self.live}


@dataclass(frozen=True)
class SnapshotDiff:
    """The drift report between a stored snapshot and a live-shaped response."""

    source: str
    endpoint: str
    request_key: str
    stored_hash: str
    live_hash: str
    fields: list[FieldDiff] = field(default_factory=list)
    stored_retrieved_at: str = ""

    @property
    def changed(self) -> bool:
        return self.stored_hash != self.live_hash

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "endpoint": self.endpoint,
            "request_key": self.request_key,
            "stored_hash": self.stored_hash,
            "live_hash": self.live_hash,
            "stored_retrieved_at": self.stored_retrieved_at,
            "changed": self.changed,
            "fields": [f.to_json_dict() for f in self.fields],
        }


def _join(path: str, part: str) -> str:
    if not path:
        return part
    return path + part if part.startswith("[") else f"{path}.{part}"


def diff_bodies(stored: Any, live: Any, *, path: str = "") -> list[FieldDiff]:
    """Field-level diff of two response bodies. Order-sensitive for lists, by design.

    A reordered result list IS drift for a retrieval index, so it is reported rather than
    smoothed over.
    """
    out: list[FieldDiff] = []
    if isinstance(stored, Mapping) and isinstance(live, Mapping):
        for key in sorted(set(stored) | set(live), key=str):
            in_stored = key in stored
            in_live = key in live
            child = _join(path, str(key))
            if in_stored and not in_live:
                out.append(FieldDiff(path=child, kind="removed", stored=stored[key]))
            elif in_live and not in_stored:
                out.append(FieldDiff(path=child, kind="added", live=live[key]))
            else:
                out.extend(diff_bodies(stored[key], live[key], path=child))
        return out

    if _is_list(stored) and _is_list(live):
        for index in range(max(len(stored), len(live))):
            child = _join(path, f"[{index}]")
            if index >= len(live):
                out.append(FieldDiff(path=child, kind="removed", stored=stored[index]))
            elif index >= len(stored):
                out.append(FieldDiff(path=child, kind="added", live=live[index]))
            else:
                out.extend(diff_bodies(stored[index], live[index], path=child))
        return out

    if stored != live or type(stored) is not type(live):
        out.append(FieldDiff(path=path or "$", kind="changed", stored=stored, live=live))
    return out


def _is_list(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def _eval_snapshot_root() -> Path:
    """``core/tests/snapshots`` relative to this file, unless overridden by env."""
    override = os.environ.get("RESEARCHER_CORE_SNAPSHOT_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "tests" / "snapshots"


class SnapshotStore:
    """A directory of content-addressed snapshot files, one subdirectory per source.

    Layout::

        <root>/<source>/<request_key>.json

    ``request_key`` is a SHA-256 hex digest, so every filename is 64 safe ASCII characters:
    no path-length or illegal-character problems on Windows (D5).
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"SnapshotStore({str(self.root)!r})"

    # -- construction ------------------------------------------------------

    @classmethod
    def eval_store(cls, root: Path | str | None = None) -> SnapshotStore:
        """The in-repo eval store (``core/tests/snapshots``). The only store tests read."""
        return cls(Path(root) if root is not None else _eval_snapshot_root())

    @classmethod
    def runtime_store(cls, root: Path | str | None = None) -> SnapshotStore:
        """The runtime store in the platformdirs user cache dir. Never feeds evals."""
        return cls(Path(root) if root is not None else user_cache_root() / "snapshots")

    # -- addressing --------------------------------------------------------

    def path_for(
        self, source: str, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> Path:
        """Where the snapshot for this request lives (whether or not it exists)."""
        return self.path_for_key(source, request_key(source, endpoint, params))

    def path_for_key(self, source: str, key: str) -> Path:
        return self.root / source / f"{key}.json"

    def has(self, source: str, endpoint: str, params: Mapping[str, Any] | None = None) -> bool:
        return self.path_for(source, endpoint, params).is_file()

    # -- reads -------------------------------------------------------------

    def load(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        *,
        verify: bool = True,
    ) -> Snapshot:
        """Load one snapshot.

        Raises :class:`SnapshotMissingError` when it is absent. There is no fallback path,
        by design.
        """
        path = self.path_for(source, endpoint, params)
        if not path.is_file():
            raise SnapshotMissingError(source, endpoint, dict(params or {}), path)
        snapshot = self.load_path(path, verify=verify)
        return snapshot

    def load_path(self, path: Path | str, *, verify: bool = True) -> Snapshot:
        """Load a snapshot from an explicit file path."""
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SnapshotError(f"Cannot read snapshot at {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SnapshotError(f"Snapshot at {path} is not valid JSON: {exc}") from exc
        snapshot = Snapshot.from_json_dict(raw)
        if verify:
            snapshot.verify()
        return snapshot

    def replay(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        *,
        verify: bool = True,
    ) -> Any:
        """The recorded response body for this request. Loud on a miss, never live."""
        return self.load(source, endpoint, params, verify=verify).response_body

    def sources(self) -> list[str]:
        """Every source that has at least one snapshot in this store."""
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def iter_snapshots(self, source: str | None = None) -> Iterator[Snapshot]:
        """Every snapshot in the store, in a stable order, optionally filtered by source."""
        for name in [source] if source else self.sources():
            directory = self.root / name
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                yield self.load_path(path, verify=False)

    def count(self, source: str | None = None) -> int:
        return sum(1 for _ in self.iter_snapshots(source))

    # -- writes ------------------------------------------------------------

    def record(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        response_body: Any,
        *,
        retrieved_at: str | None = None,
    ) -> Snapshot:
        """Write a snapshot for this request, replacing any existing one. Returns it."""
        snapshot = Snapshot.create(
            source, endpoint, params, response_body, retrieved_at=retrieved_at
        )
        self.write(snapshot)
        return snapshot

    def write(self, snapshot: Snapshot) -> Path:
        """Atomically write ``snapshot`` to its content-addressed path."""
        key = snapshot.request_key or request_key(
            snapshot.source, snapshot.endpoint, snapshot.request_params
        )
        path = self.path_for_key(snapshot.source, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = snapshot.serialize()
        # Write to a temp file in the same directory, then os.replace: atomic on Windows
        # and POSIX alike, so a crash mid-write never leaves a half-snapshot behind.
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=str(path.parent),
            prefix=".tmp-",
            suffix=".json",
            delete=False,
        )
        try:
            with handle as fh:
                fh.write(text)
            os.replace(handle.name, path)
        except BaseException:
            Path(handle.name).unlink(missing_ok=True)
            raise
        return path

    def delete(
        self, source: str, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> bool:
        path = self.path_for(source, endpoint, params)
        if path.is_file():
            path.unlink()
            return True
        return False

    # -- diff --------------------------------------------------------------

    def diff(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        live_body: Any,
    ) -> SnapshotDiff:
        """Field-level drift between the stored snapshot for a request and a live body."""
        stored = self.load(source, endpoint, params, verify=False)
        return diff_snapshot(stored, live_body)


def diff_snapshot(stored: Snapshot, live_body: Any) -> SnapshotDiff:
    """Field-level drift between a loaded snapshot and a live-shaped response body."""
    return SnapshotDiff(
        source=stored.source,
        endpoint=stored.endpoint,
        request_key=stored.request_key
        or request_key(stored.source, stored.endpoint, stored.request_params),
        stored_hash=stored.response_hash,
        live_hash=response_hash(live_body),
        fields=diff_bodies(stored.response_body, live_body),
        stored_retrieved_at=stored.retrieved_at,
    )


# ---------------------------------------------------------------------------
# Session: the thing connectors actually call
# ---------------------------------------------------------------------------


class SnapshotSession:
    """Binds a store, a mode, and an optional cache into one request resolver.

    :class:`researcher_core.connectors.base.BaseConnector` routes EVERY response through
    :meth:`afetch`, so snapshot awareness is a property of the base class rather than
    something each connector has to remember.
    """

    def __init__(
        self,
        store: SnapshotStore | None = None,
        mode: SnapshotMode | str = SnapshotMode.LIVE,
        *,
        cache: ResponseCache | None = None,
        retrieved_at: str | None = None,
    ) -> None:
        self.mode = SnapshotMode.parse(mode)
        if store is None:
            store = (
                SnapshotStore.eval_store()
                if self.mode is SnapshotMode.REPLAY
                else SnapshotStore.runtime_store()
            )
        self.store = store
        self.cache = cache
        # When set, every snapshot recorded by this session carries this timestamp, which
        # is what makes a re-record byte-identical (D15: ts is caller-supplied).
        self.retrieved_at = retrieved_at

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"SnapshotSession(mode={self.mode.value!r}, store={self.store!r})"

    @classmethod
    def from_env(cls, *, cache: ResponseCache | None = None) -> SnapshotSession:
        """Build a session from ``RESEARCHER_CORE_SNAPSHOT_MODE`` / ``..._SNAPSHOT_DIR``.

        Tests and eval runners set the mode to ``replay``; ``--record`` sets it to
        ``record``; ordinary use leaves it at ``live``.
        """
        mode = SnapshotMode.parse(os.environ.get("RESEARCHER_CORE_SNAPSHOT_MODE"))
        override = os.environ.get("RESEARCHER_CORE_SNAPSHOT_DIR")
        store = SnapshotStore(override) if override else None
        return cls(store, mode, cache=cache or ResponseCache.from_env())

    @property
    def is_replay(self) -> bool:
        return self.mode is SnapshotMode.REPLAY

    @property
    def is_recording(self) -> bool:
        return self.mode is SnapshotMode.RECORD

    # -- resolution --------------------------------------------------------

    def replay(
        self, source: str, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> Any:
        """Read from the snapshot store. Raises :class:`SnapshotMissingError` on a miss."""
        return self.store.replay(source, endpoint, params)

    def record(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        response_body: Any,
    ) -> Snapshot:
        return self.store.record(
            source, endpoint, params, response_body, retrieved_at=self.retrieved_at
        )

    def fetch(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        fetcher: Callable[[], Any],
    ) -> Any:
        """Synchronous resolution of one request under the session mode.

        REPLAY never calls ``fetcher``. That is the invariant; nothing below it is allowed
        to reach the network.
        """
        if self.mode is SnapshotMode.REPLAY:
            return self.replay(source, endpoint, params)

        if self.mode is SnapshotMode.LIVE and self.cache is not None:
            hit = self.cache.get(source, endpoint, params)
            if hit is not None:
                return hit

        body = fetcher()

        if self.mode is SnapshotMode.RECORD:
            self.record(source, endpoint, params, body)
        if self.cache is not None:
            self.cache.set(source, endpoint, params, body)
        return body

    async def afetch(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        fetcher: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Async resolution of one request under the session mode.

        REPLAY never awaits ``fetcher``, so no coroutine that could touch the network is
        ever created in replay mode.
        """
        if self.mode is SnapshotMode.REPLAY:
            return self.replay(source, endpoint, params)

        if self.mode is SnapshotMode.LIVE and self.cache is not None:
            hit = self.cache.get(source, endpoint, params)
            if hit is not None:
                return hit

        body = await fetcher()

        if self.mode is SnapshotMode.RECORD:
            self.record(source, endpoint, params, body)
        if self.cache is not None:
            self.cache.set(source, endpoint, params, body)
        return body
