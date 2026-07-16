"""Offline / private mode (M5.1).

The rule this module enforces, stated once: with ``--offline`` set (or ``RESEARCHER_OFFLINE=1``
in the environment), every network-touching command answers EXCLUSIVELY from the snapshot store
and the response cache. A miss is a typed :class:`OfflineMiss`, never a silent fallthrough to a
live HTTP call. That is the whole promise of the flag, so it is enforced here in one place rather
than trusted to each connector.

How it reuses the existing layers (no second cache is built):

* The snapshot store (:mod:`researcher_core.snapshots`) is the deterministic replay source. Offline
  mode runs a session in :class:`~researcher_core.snapshots.SnapshotMode.REPLAY`, so the fetcher is
  never called and no socket is ever opened.
* The response cache (:mod:`researcher_core.cache`) is the polite live-use cache. Offline mode reads
  it as a fallback when the snapshot store has no record, so a request answered live earlier in the
  session still resolves with the network down.
* When BOTH miss, the answer is an :class:`OfflineMiss`: a typed value the CLI and connectors
  surface as a clean ``offline-miss`` outcome. It is not a crash, and it is not a live call.

The seam a normal :class:`~researcher_core.snapshots.SnapshotSession` in REPLAY mode raises
:class:`~researcher_core.snapshots.SnapshotMissingError` on a miss, which is correct for evals (a
missing gold snapshot must fail loud) but wrong for a user who deliberately went offline. The
:class:`OfflineSession` here converts that loud failure into the typed result:
:meth:`OfflineSession.resolve` RETURNS an :class:`OfflineMiss`, while the fetch/replay path raises
:class:`OfflineMissError` (a subclass of ``SnapshotMissingError``, so existing per-source isolation
and re-raise handling still route it correctly), carrying the same typed payload on ``.miss``.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from .cache import ResponseCache
from .snapshots import (
    SnapshotError,
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)

__all__ = [
    "OFFLINE_ENV",
    "Config",
    "OfflineMiss",
    "OfflineMissError",
    "OfflineSession",
    "build_session",
    "is_offline",
]

#: The environment variable that turns offline mode on. Any of ``1``, ``true``, ``yes``, ``on``
#: (case-insensitive) enables it; anything else, including an unset variable, leaves it off.
OFFLINE_ENV = "RESEARCHER_OFFLINE"

_TRUTHY = frozenset({"1", "true", "yes", "on"})

#: The store-directory override honored by the snapshot layer. Offline mode reads it too, so an
#: eval or benchmark run that points the kernel at a specific snapshot set keeps working with the
#: network down.
_SNAPSHOT_DIR_ENV = "RESEARCHER_CORE_SNAPSHOT_DIR"


def is_offline(offline: bool | None = None, *, env: Mapping[str, str] | None = None) -> bool:
    """Whether offline mode is in force.

    An explicit ``offline`` argument (from a ``--offline`` flag) wins outright, in either
    direction: ``offline=True`` forces it on and ``offline=False`` forces it off, regardless of the
    environment. Only when ``offline`` is ``None`` does the ``RESEARCHER_OFFLINE`` variable decide.
    """
    if offline is not None:
        return bool(offline)
    environ = os.environ if env is None else env
    return environ.get(OFFLINE_ENV, "").strip().lower() in _TRUTHY


# ---------------------------------------------------------------------------
# The typed miss
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OfflineMiss:
    """A request that offline mode could not answer from a snapshot or the cache.

    This is a value, not a failure: it is the honest answer "no local record, and I did not go to
    the network to get one". The CLI and connectors surface it as an ``offline-miss`` outcome.
    """

    source: str
    endpoint: str
    params: dict[str, Any]
    path: str
    message: str

    #: The stable outcome tag, so a consumer branches on a constant rather than a message string.
    outcome: ClassVar[str] = "offline-miss"

    @classmethod
    def from_missing(cls, err: SnapshotMissingError) -> OfflineMiss:
        """Build the typed miss from the loud snapshot-missing error, reframed for offline mode."""
        params = dict(err.params)
        return cls(
            source=err.source,
            endpoint=err.endpoint,
            params=params,
            path=str(err.path),
            message=(
                f"Offline mode: no snapshot or cached response for source={err.source!r} "
                f"endpoint={err.endpoint!r}. Nothing was fetched over the network. Record it "
                "online with --record, or drop --offline to allow a live call."
            ),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "source": self.source,
            "endpoint": self.endpoint,
            "params": dict(self.params),
            "path": self.path,
            "message": self.message,
        }


class OfflineMissError(SnapshotMissingError):
    """Raised on the fetch/replay path when offline mode cannot answer a request.

    It subclasses :class:`~researcher_core.snapshots.SnapshotMissingError` on purpose: any existing
    handler that already re-raises a missing snapshot (per-source isolation never swallows it) keeps
    forwarding this too, so an offline miss can never be degraded into a source error. What it adds
    is :attr:`miss`, the typed :class:`OfflineMiss` a caller surfaces as a clean result.
    """

    def __init__(self, miss: OfflineMiss) -> None:
        self.miss = miss
        # Set the same attributes SnapshotMissingError exposes, but carry the offline-framed
        # message instead of the eval-framed one.
        self.source = miss.source
        self.endpoint = miss.endpoint
        self.params = dict(miss.params)
        self.path = Path(miss.path)
        SnapshotError.__init__(self, miss.message)


# ---------------------------------------------------------------------------
# The offline session
# ---------------------------------------------------------------------------


class OfflineSession(SnapshotSession):
    """A snapshot session pinned to REPLAY that answers a miss with a typed result.

    Every resolution goes through :meth:`_offline_lookup`: the snapshot store first, the response
    cache second, and an :class:`OfflineMiss` when both come up empty. The fetcher passed to
    :meth:`fetch` / :meth:`afetch` is NEVER called or awaited, so no coroutine that could reach the
    network is ever created.
    """

    def __init__(
        self,
        store: SnapshotStore | None = None,
        *,
        cache: ResponseCache | None = None,
        retrieved_at: str | None = None,
    ) -> None:
        super().__init__(store, SnapshotMode.REPLAY, cache=cache, retrieved_at=retrieved_at)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"OfflineSession(store={self.store!r}, cache={'yes' if self.cache else 'no'})"

    # -- resolution --------------------------------------------------------

    def _offline_lookup(
        self, source: str, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> Any | OfflineMiss:
        """The one lookup path: snapshot store, then cache, then a typed miss. Never live."""
        try:
            return self.store.replay(source, endpoint, params)
        except SnapshotMissingError as err:
            missing = err
        if self.cache is not None:
            hit = self.cache.get(source, endpoint, params)
            if hit is not None:
                return hit
        return OfflineMiss.from_missing(missing)

    def resolve(
        self, source: str, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> Any | OfflineMiss:
        """Resolve one request, returning the body or a typed :class:`OfflineMiss`. Never raises."""
        return self._offline_lookup(source, endpoint, params)

    def replay(
        self, source: str, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> Any:
        """Read from the local layers. Raises :class:`OfflineMissError` (typed) on a miss."""
        body = self._offline_lookup(source, endpoint, params)
        if isinstance(body, OfflineMiss):
            raise OfflineMissError(body)
        return body

    def fetch(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        fetcher: Callable[[], Any],
    ) -> Any:
        """Offline resolution. ``fetcher`` is never called; a miss raises the typed error."""
        return self.replay(source, endpoint, params)

    async def afetch(
        self,
        source: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        fetcher: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Async offline resolution. ``fetcher`` is never awaited; a miss raises the typed error."""
        return self.replay(source, endpoint, params)


# ---------------------------------------------------------------------------
# Session selection: the helper the CLI's build_session calls
# ---------------------------------------------------------------------------


def build_session(
    *,
    offline: bool | None = None,
    record: bool = False,
    store: SnapshotStore | None = None,
    cache: ResponseCache | None = None,
    retrieved_at: str | None = None,
    env: Mapping[str, str] | None = None,
) -> SnapshotSession:
    """Select the snapshot session for one invocation.

    Offline (``offline=True`` or ``RESEARCHER_OFFLINE=1``): an :class:`OfflineSession` in REPLAY
    that answers a miss with a typed :class:`OfflineMiss` instead of raising an unhandled error or
    going live. ``record`` is ignored offline, because recording requires a live call.

    Otherwise the normal resolution: mode from ``RESEARCHER_CORE_SNAPSHOT_MODE`` (``live`` unless a
    test or eval runner set ``replay``), with ``record`` overriding to RECORD. This mirrors the
    behavior the CLI had before offline mode existed, so a non-offline invocation is unchanged.
    """
    environ = os.environ if env is None else env

    if is_offline(offline, env=environ):
        offline_store = store if store is not None else _default_offline_store(environ)
        offline_cache = cache if cache is not None else ResponseCache.from_env()
        return OfflineSession(offline_store, cache=offline_cache, retrieved_at=retrieved_at)

    session = (
        SnapshotSession.from_env(cache=cache)
        if cache is not None
        else SnapshotSession.from_env()
    )
    if record:
        session.mode = SnapshotMode.RECORD
    if store is not None:
        session.store = store
    if retrieved_at is not None:
        session.retrieved_at = retrieved_at
    return session


def _default_offline_store(environ: Mapping[str, str]) -> SnapshotStore:
    """The store an offline session reads when the caller names none.

    The ``RESEARCHER_CORE_SNAPSHOT_DIR`` override wins, so an eval or benchmark run stays pointed at
    its snapshot set with the network down. Otherwise it is the runtime store in the user cache dir,
    where the user's own ``--record`` snapshots live. It is deliberately NOT the in-repo eval store:
    a user running offline replays their own recordings, not the test fixtures.
    """
    override = environ.get(_SNAPSHOT_DIR_ENV)
    return SnapshotStore(override) if override else SnapshotStore.runtime_store()


# ---------------------------------------------------------------------------
# Config: a small home for the offline decision and session construction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """The resolved runtime configuration for one invocation.

    Holds the offline decision (already resolved against the flag and the environment) plus the
    optional overrides a caller may inject, and knows how to build the matching session.
    """

    offline: bool = False
    record: bool = False
    store: SnapshotStore | None = None
    cache: ResponseCache | None = None
    retrieved_at: str | None = None
    env: Mapping[str, str] | None = field(default=None)

    @classmethod
    def from_env(
        cls,
        *,
        offline: bool | None = None,
        record: bool = False,
        store: SnapshotStore | None = None,
        cache: ResponseCache | None = None,
        retrieved_at: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> Config:
        """Resolve the offline decision against the flag and the environment, then freeze it."""
        return cls(
            offline=is_offline(offline, env=env),
            record=record,
            store=store,
            cache=cache,
            retrieved_at=retrieved_at,
            env=env,
        )

    def is_offline(self) -> bool:
        return self.offline

    def build_session(self) -> SnapshotSession:
        """Build the session this configuration calls for. Offline yields an OfflineSession."""
        return build_session(
            offline=self.offline,
            record=self.record,
            store=self.store,
            cache=self.cache,
            retrieved_at=self.retrieved_at,
            env=self.env,
        )
