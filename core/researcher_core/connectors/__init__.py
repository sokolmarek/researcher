"""Connector registry: name -> connector class.

``search.py`` and the CLI fan out by name (``--sources openalex,crossref,arxiv``), so the
registry is the single place that maps a user-facing source name onto an implementation.

A connector module registers itself with the :func:`register` decorator::

    from .base import BaseConnector
    from . import register

    @register
    class OpenAlexConnector(BaseConnector):
        name = "openalex"
        ...

Registration is also inferred: if a builtin module ships a :class:`BaseConnector` subclass
whose ``name`` matches but forgot the decorator, :func:`get_connector_class` still finds it.
Builtin modules are imported lazily, so the package imports cleanly while connectors are
still being written.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterator
from typing import Any

from .base import (
    BaseConnector,
    ConnectorError,
    SourceError,
    SourceErrorKind,
    UnsupportedOperation,
)

__all__ = [
    "BUILTIN_CONNECTORS",
    "BaseConnector",
    "ConnectorError",
    "SourceError",
    "SourceErrorKind",
    "UnknownConnectorError",
    "UnsupportedOperation",
    "available_connectors",
    "create_connector",
    "get_connector_class",
    "iter_connector_classes",
    "register",
    "registered_connectors",
]

#: Every connector name the kernel knows about, mapped to the module that defines it.
#: A name listed here that has no module yet simply does not appear in
#: :func:`available_connectors` until its module lands.
BUILTIN_CONNECTORS: dict[str, str] = {
    "openalex": "researcher_core.connectors.openalex",
    "crossref": "researcher_core.connectors.crossref",
    "datacite": "researcher_core.connectors.datacite",
    "semantic_scholar": "researcher_core.connectors.semantic_scholar",
    "arxiv": "researcher_core.connectors.arxiv",
    "pubmed": "researcher_core.connectors.pubmed",
    "unpaywall": "researcher_core.connectors.unpaywall",
    "opencitations": "researcher_core.connectors.opencitations",
}

_REGISTRY: dict[str, type[BaseConnector]] = {}


class UnknownConnectorError(ConnectorError, KeyError):
    """No connector is registered under this name."""

    def __init__(self, name: str, known: list[str]) -> None:
        self.name = name
        self.known = known
        listed = ", ".join(known) if known else "(none registered)"
        ConnectorError.__init__(self, f"Unknown connector {name!r}. Available: {listed}")

    def __str__(self) -> str:
        listed = ", ".join(self.known) if self.known else "(none registered)"
        return f"Unknown connector {self.name!r}. Available: {listed}"


def register(cls: type[BaseConnector]) -> type[BaseConnector]:
    """Class decorator that registers a connector under its ``name``."""
    name = getattr(cls, "name", "")
    if not name:
        raise ConnectorError(f"{cls.__name__} must set a class-level `name` before registering.")
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not cls:
        raise ConnectorError(
            f"Connector name {name!r} is already registered to {existing.__name__}."
        )
    _REGISTRY[name] = cls
    return cls


def _load(name: str) -> None:
    """Import the builtin module for ``name``, if there is one and it is not loaded yet."""
    if name in _REGISTRY:
        return
    module_path = BUILTIN_CONNECTORS.get(name)
    if module_path is None:
        return
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        return
    if name in _REGISTRY:
        return
    # The module exists but did not use @register. Find its connector class anyway, so a
    # forgotten decorator degrades to a working connector rather than a missing source.
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, BaseConnector) and obj is not BaseConnector:
            if getattr(obj, "name", "") == name:
                _REGISTRY[name] = obj
                return


def get_connector_class(name: str) -> type[BaseConnector]:
    """The connector class registered under ``name``.

    Raises :class:`UnknownConnectorError` when the name is unknown or its module is absent.
    """
    key = str(name).strip().lower()
    if key not in _REGISTRY:
        _load(key)
    try:
        return _REGISTRY[key]
    except KeyError:
        raise UnknownConnectorError(key, available_connectors()) from None


def create_connector(name: str, **kwargs: Any) -> BaseConnector:
    """Instantiate the connector registered under ``name``, passing ``kwargs`` through."""
    return get_connector_class(name)(**kwargs)


def available_connectors() -> list[str]:
    """Every connector name that can actually be instantiated right now, sorted."""
    for name in BUILTIN_CONNECTORS:
        _load(name)
    return sorted(_REGISTRY)


def registered_connectors() -> dict[str, type[BaseConnector]]:
    """A copy of the registry as it stands, without importing anything further."""
    return dict(_REGISTRY)


def iter_connector_classes() -> Iterator[type[BaseConnector]]:
    """Every available connector class, in name order."""
    for name in available_connectors():
        yield _REGISTRY[name]
