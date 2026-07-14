"""The connector contract.

Every source (OpenAlex, Crossref, DataCite, Semantic Scholar, arXiv, PubMed, Unpaywall,
OpenCitations) subclasses :class:`BaseConnector`. Two invariants are enforced here, in the
base class, rather than trusted to eight separate implementations:

1. **Every response routes through the snapshot layer.** Connectors call
   :meth:`BaseConnector.request_json`, never httpx directly. In replay mode that method
   reads the snapshot store and never touches the network; a missing snapshot raises
   :class:`~researcher_core.snapshots.SnapshotMissingError` loudly.

2. **A source outage is not a clean negative.** This is load-bearing for D9 axis (a): a
   downed index must NEVER be counted as evidence of fabrication. So:

   * A **clean negative** (the query succeeded, nothing matched) is an ordinary return
     value: an empty list from :meth:`search`, ``None`` from :meth:`get_by_id`,
     :meth:`resolve_doi`, and :meth:`get_oa_pdf`.
   * A **source error** (timeout, rate limit, 5xx, network failure, unparseable payload,
     missing required configuration) raises :class:`SourceError`. Callers map that to the
     ``source_error`` per-source outcome, which forces ``inconclusive`` and never
     ``unresolvable``.

   Never raise :class:`SourceError` to mean "not found", and never return an empty result
   to mean "the API fell over".
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import Enum
from types import TracebackType
from typing import Any, ClassVar

import httpx

from ..cache import DEFAULT_TTL_SECONDS, ResponseCache
from ..model import CSLRecord, OALocation
from ..snapshots import SnapshotMissingError, SnapshotMode, SnapshotSession

__all__ = [
    "BaseConnector",
    "ConnectorError",
    # Re-exported so connectors can import both error families from one place. Catching
    # SourceError must never catch SnapshotMissingError: they mean opposite things.
    "SnapshotMissingError",
    "SnapshotMode",
    "SnapshotSession",
    "SourceError",
    "SourceErrorKind",
    "UnsupportedOperation",
]

DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "researcher-core/0.1.0 (https://github.com/marek-sokol/researcher)"


class ConnectorError(Exception):
    """Base class for every connector-layer failure."""


class SourceErrorKind(str, Enum):
    """Why a source failed to give a clean answer."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    NETWORK = "network"
    BAD_RESPONSE = "bad_response"
    CONFIG = "config"


class SourceError(ConnectorError):
    """A source did not give a clean answer.

    Timeout, rate limit, 5xx, network failure, unparseable payload, or missing required
    configuration. This is emphatically NOT "no match found": a clean negative is an empty
    list or ``None``. Consumers translate a :class:`SourceError` into the ``source_error``
    per-source outcome, which per D9 forces an ``inconclusive`` reference-level verdict and
    can never produce a refusal-grade ``unresolvable``.
    """

    def __init__(
        self,
        source: str,
        message: str,
        *,
        kind: SourceErrorKind = SourceErrorKind.NETWORK,
        status_code: int | None = None,
        endpoint: str = "",
    ) -> None:
        self.source = source
        self.kind = kind
        self.status_code = status_code
        self.endpoint = endpoint
        self.message = message
        detail = f"[{source}:{kind.value}]"
        if status_code is not None:
            detail += f" HTTP {status_code}"
        super().__init__(f"{detail} {message}")

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind.value,
            "status_code": self.status_code,
            "endpoint": self.endpoint,
            "message": self.message,
        }


class UnsupportedOperation(ConnectorError):
    """The connector does not implement this operation at all (arXiv has no citation graph).

    Distinct from both a clean negative and a source error: nothing was asked of the API.
    Callers should skip the source for that operation rather than record an outcome. Use
    :meth:`BaseConnector.supports` to check before calling.
    """

    def __init__(self, source: str, operation: str) -> None:
        self.source = source
        self.operation = operation
        super().__init__(f"Connector {source!r} does not support {operation!r}.")


class BaseConnector(ABC):
    """Abstract contract for a literature source.

    Subclasses set :attr:`name`, :attr:`base_url`, and :attr:`capabilities`, then implement
    the operations they list. Transport, snapshotting, caching, throttling, and retries are
    handled here.
    """

    #: Registry key. Must be unique and stable: skills pass it to ``--sources``.
    name: ClassVar[str] = ""
    #: API root, with no trailing slash.
    base_url: ClassVar[str] = ""
    #: Which of the six operations this source actually implements.
    capabilities: ClassVar[frozenset[str]] = frozenset()
    #: Minimum seconds between two requests to this source. 0 disables throttling.
    rate_limit_interval: ClassVar[float] = 0.0
    #: Cache TTL for this source, overriding the 7-day default.
    cache_ttl: ClassVar[int] = DEFAULT_TTL_SECONDS
    #: Retries on 429 / 5xx before giving up and raising SourceError.
    max_retries: ClassVar[int] = 2

    ALL_OPERATIONS: ClassVar[tuple[str, ...]] = (
        "search",
        "get_by_id",
        "resolve_doi",
        "get_citations",
        "get_references",
        "get_oa_pdf",
    )

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        snapshots: SnapshotSession | None = None,
        cache: ResponseCache | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if not self.name:
            raise ConnectorError(f"{type(self).__name__} must set a class-level `name`.")
        self.timeout = timeout
        self.user_agent = user_agent
        self.extra_headers = dict(headers or {})
        if snapshots is None:
            snapshots = SnapshotSession.from_env(cache=cache)
        elif cache is not None and snapshots.cache is None:
            snapshots.cache = cache
        self.snapshots = snapshots
        self._client = client
        self._owns_client = client is None
        self._throttle_lock = asyncio.Lock()
        self._last_request_at = 0.0

    # -- lifecycle ---------------------------------------------------------

    @property
    def client(self) -> httpx.AsyncClient:
        """The shared async HTTP client, created lazily so replay never opens one."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self.default_headers(),
            )
            self._owns_client = True
        return self._client

    def default_headers(self) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        headers.update(self.extra_headers)
        return headers

    async def aclose(self) -> None:
        """Close the HTTP client when this connector owns it."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    async def __aenter__(self) -> BaseConnector:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # -- capabilities ------------------------------------------------------

    @classmethod
    def supports(cls, operation: str) -> bool:
        """True when this connector implements ``operation``."""
        return operation in cls.capabilities

    # -- transport ---------------------------------------------------------

    async def request_json(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
    ) -> Any:
        """Fetch and parse one response, routed through the snapshot layer.

        This is the ONLY network entry point a connector may use. Behavior by session mode:

        * ``replay``: return the recorded body. No HTTP client is created, no request is
          made. A missing snapshot raises :class:`SnapshotMissingError`, which is never
          converted into a :class:`SourceError`.
        * ``live``: consult the TTL cache, then call the API, then cache the body.
        * ``record``: call the API (bypassing the cache read) and write the snapshot.

        ``endpoint`` is the snapshot and cache key component, so it must be stable and
        parameter-free (for example ``"works"``, not ``"works?search=x"``). Anything that
        varies belongs in ``params``.

        Raises:
            SourceError: timeout, rate limit, 5xx, network failure, or unparseable payload.
            SnapshotMissingError: replay mode with no snapshot for this request.
        """
        request_params = _clean_params(params)

        async def fetch() -> Any:
            return await self._http_json(
                endpoint, request_params, method=method, headers=headers, url=url
            )

        return await self.snapshots.afetch(self.name, endpoint, request_params, fetch)

    async def _http_json(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
    ) -> Any:
        """The live call. Retries 429 and 5xx with backoff, then raises SourceError."""
        target = url or self.build_url(endpoint)
        attempt = 0
        while True:
            await self._throttle()
            try:
                response = await self.client.request(
                    method,
                    target,
                    params=dict(params) or None,
                    headers=dict(headers) if headers else None,
                )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    attempt += 1
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise SourceError(
                    self.name,
                    f"Request to {target} timed out after {self.timeout}s.",
                    kind=SourceErrorKind.TIMEOUT,
                    endpoint=endpoint,
                ) from exc
            except httpx.HTTPError as exc:
                if attempt < self.max_retries:
                    attempt += 1
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise SourceError(
                    self.name,
                    f"Network failure calling {target}: {exc}",
                    kind=SourceErrorKind.NETWORK,
                    endpoint=endpoint,
                ) from exc

            status = response.status_code
            if status == 429 or status >= 500:
                if attempt < self.max_retries:
                    attempt += 1
                    await asyncio.sleep(self._retry_after(response, attempt))
                    continue
                kind = (
                    SourceErrorKind.RATE_LIMIT
                    if status == 429
                    else SourceErrorKind.SERVER_ERROR
                )
                raise SourceError(
                    self.name,
                    f"{target} returned HTTP {status}.",
                    kind=kind,
                    status_code=status,
                    endpoint=endpoint,
                )
            return self.parse_response(response, endpoint)

    def parse_response(self, response: httpx.Response, endpoint: str) -> Any:
        """Turn an HTTP response into a snapshot-able body.

        The default parses JSON, and treats 404 and 410 as clean negatives by returning
        ``None`` (the caller decides what "no match" means for that operation). Override
        for XML or Atom sources (arXiv, PubMed): return a JSON-serializable structure, since
        the returned body is exactly what gets snapshotted and hashed.
        """
        if response.status_code in (404, 410):
            return None
        if response.status_code >= 400:
            raise SourceError(
                self.name,
                f"{response.request.url} returned HTTP {response.status_code}.",
                kind=SourceErrorKind.BAD_RESPONSE,
                status_code=response.status_code,
                endpoint=endpoint,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(
                self.name,
                f"{response.request.url} returned a body that is not valid JSON: {exc}",
                kind=SourceErrorKind.BAD_RESPONSE,
                status_code=response.status_code,
                endpoint=endpoint,
            ) from exc

    def build_url(self, endpoint: str) -> str:
        """Join :attr:`base_url` and ``endpoint``. Absolute endpoints pass through."""
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        if not self.base_url:
            raise ConnectorError(f"Connector {self.name!r} has no base_url set.")
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    async def _throttle(self) -> None:
        if self.rate_limit_interval <= 0:
            return
        async with self._throttle_lock:
            wait = self.rate_limit_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    def _backoff(self, attempt: int) -> float:
        return min(8.0, 0.5 * (2 ** (attempt - 1)))

    def _retry_after(self, response: httpx.Response, attempt: int) -> float:
        raw = response.headers.get("Retry-After", "")
        try:
            return min(30.0, float(raw))
        except (TypeError, ValueError):
            return self._backoff(attempt)

    # -- the contract ------------------------------------------------------

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        since: int | None = None,
    ) -> list[CSLRecord]:
        """Free-text search. Returns at most ``limit`` records, best match first.

        An empty list is a clean negative. A dead API raises :class:`SourceError`.
        ``since`` filters to works published in that year or later.
        """

    @abstractmethod
    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        """Fetch one record by this source's native identifier (or a DOI it recognizes).

        ``None`` is a clean negative: the lookup succeeded and nothing matched.
        """

    @abstractmethod
    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        """Fetch one record by DOI. ``None`` is a clean negative."""

    async def get_citations(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Works that cite ``identifier`` (forward edges). Empty list is a clean negative."""
        raise UnsupportedOperation(self.name, "get_citations")

    async def get_references(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        """Works that ``identifier`` cites (backward edges). Empty list is a clean negative."""
        raise UnsupportedOperation(self.name, "get_references")

    async def get_oa_pdf(self, doi: str) -> OALocation | None:
        """Resolve an open-access location for a DOI. ``None`` means no OA copy was found."""
        raise UnsupportedOperation(self.name, "get_oa_pdf")

    # -- parsing -----------------------------------------------------------

    def to_record(self, raw: Mapping[str, Any]) -> CSLRecord:
        """Normalize one raw API item into a :class:`CSLRecord`. Implemented per source."""
        raise NotImplementedError(
            f"Connector {self.name!r} must implement to_record() to normalize its payloads."
        )


def _clean_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Drop None-valued params so an optional filter never changes the snapshot key."""
    return {k: v for k, v in dict(params or {}).items() if v is not None}
