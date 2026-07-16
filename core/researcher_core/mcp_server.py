"""The thin stable-core MCP server (M5.9, D13).

This module exposes exactly five stable-core operations over the Model Context Protocol so
the kernel is usable outside Claude Code: from any MCP client, from OpenAI Codex, from a
plain stdio harness. Every tool is a THIN RE-EXPORT of a function that already lives in the
kernel. There is no new retrieval, verification, or extraction logic here; the server moves
with core versioning precisely because it adds none of its own behavior.

The five stable tools, and the single core function each one wraps:

* ``search_papers``       -> :func:`researcher_core.search.search_sync`
* ``get_paper``           -> per-source ``resolve_doi`` / ``get_by_id`` (the CLI ``get`` path)
* ``verify_citations``    -> :func:`researcher_core.verify.verify_claims`
* ``export_bibliography`` -> :func:`researcher_core.bib.emit_bib` (plus the optional
  ``export`` emitters for RIS and JATS when that sibling module is installed)
* ``download_oa``         -> :func:`researcher_core.fulltext.extract`

Optional dependency, guarded on purpose
---------------------------------------

``fastmcp`` is an OPTIONAL extra (``pip install -e "core[mcp]"``). This module MUST import
cleanly without it: the tool callables below are plain functions that never touch fastmcp,
so the whole kernel test suite, the CLI, and every other consumer keep working when the
extra is absent. Only :func:`build_server` and :func:`main` need fastmcp, and both fail with
a one-line install hint (never a traceback) when it is missing, mirroring how
:mod:`researcher_core.fulltext` handles the ``[fulltext]`` extra.

Two boundary layers this server inherits rather than reimplements:

* **Offline (M5.1).** Passing ``offline=True`` (or starting ``researcher-mcp --offline``,
  which sets the ``RESEARCHER_OFFLINE`` variable) builds sessions through
  :func:`researcher_core.config.build_session`, the same selector the CLI uses. An offline
  session answers exclusively from snapshots and the response cache; a miss raises the typed
  offline-miss error and the network fetcher is never invoked. Nothing here opens a second
  network door.
* **Sanitization (M5.2).** Every tool result is passed through
  :func:`researcher_core.sanitize.sanitize_json_strings` before it leaves this process, so
  fetched titles, abstracts, and passages cannot smuggle control characters or prompt-shaped
  text into an MCP client. The one deliberate exception is ``export_bibliography``'s
  ``content`` field: an exported bibliography is a data artifact whose bytes must stay
  lossless (D4), so the envelope around it is sanitized and the document itself is not.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .bib import BibError, emit_bib, record_to_entry, records_from_bib  # noqa: F401
from .config import OFFLINE_ENV, build_session
from .fulltext import MISSING_EXTRA_MESSAGE, MissingExtraError, extract
from .model import CSLRecord, is_valid_doi, normalize_doi
from .sanitize import sanitize_json_strings
from .search import DEFAULT_SEARCH_SOURCES, search_sync
from .snapshots import SnapshotSession
from .verify import DEFAULT_SOURCES as VERIFY_DEFAULT_SOURCES
from .verify import ReferenceClaim, verify_claims

__all__ = [
    "MISSING_FASTMCP_MESSAGE",
    "STABLE_TOOLS",
    "build_server",
    "download_oa",
    "export_bibliography",
    "fastmcp_available",
    "get_paper",
    "main",
    "search_papers",
    "verify_citations",
]

#: The stable subset, in registration order. This tuple IS the contract: the server exposes
#: these names and only these names, so a client can rely on the surface moving with core
#: versioning rather than growing ad hoc tools.
STABLE_TOOLS: tuple[str, ...] = (
    "search_papers",
    "get_paper",
    "verify_citations",
    "export_bibliography",
    "download_oa",
)

#: Formats the exporter can always produce with only the base kernel installed. RIS and JATS
#: come from the optional ``export`` sibling module and are added when it is importable.
ALWAYS_AVAILABLE_FORMATS: tuple[str, ...] = ("bibtex", "csl-json")

MISSING_FASTMCP_MESSAGE = (
    "The MCP server needs FastMCP, which ships in the optional [mcp] extra.\n"
    "Install it with one of:\n"
    "  uv sync --project core --extra mcp\n"
    '  pip install -e "core[mcp]"\n'
    "Every other kernel command, and the CLI, work without it."
)


# ---------------------------------------------------------------------------
# Defensive boundary-layer hooks (built by sibling M5 modules)
# ---------------------------------------------------------------------------


def _sanitize(payload: Any, *, preserve: tuple[str, ...] = ()) -> Any:
    """Pass ``payload`` through the M5.2 sanitizer before it leaves the process.

    Every string value is run through :func:`sanitize_json_strings`, so a fetched title,
    abstract, or passage carrying control characters or prompt-shaped text reaches the MCP
    client as inert text. ``preserve`` names top-level dict keys whose values pass through
    verbatim; ``export_bibliography`` uses it for the exported document, a data artifact
    whose bytes must stay lossless (D4) and would be mangled by tag stripping.
    """
    if preserve and isinstance(payload, dict):
        return {
            key: (value if key in preserve else sanitize_json_strings(value))
            for key, value in payload.items()
        }
    return sanitize_json_strings(payload)


def _resolve_session(
    session: SnapshotSession | None, offline: bool
) -> SnapshotSession:
    """Return the snapshot session a tool should use.

    An explicitly injected session (every test does this, and so may an embedding caller)
    wins untouched. Otherwise the session comes from :func:`researcher_core.config.build_session`,
    the same selector the CLI uses: ``offline=True`` yields an offline session whose misses
    are typed and whose network fetchers are never invoked, and ``offline=False`` leaves the
    decision to the ``RESEARCHER_OFFLINE`` variable, so a server started with ``--offline``
    (which sets that variable) keeps every tool offline without re-plumbing the flag.
    """
    if session is not None:
        return session
    return build_session(offline=True if offline else None)


def _apply_offline() -> None:
    """Turn offline mode on for this process.

    :func:`researcher_core.config.is_offline` reads the ``RESEARCHER_OFFLINE`` variable
    whenever a caller does not pass an explicit flag, so setting it here makes every
    subsequent :func:`_resolve_session` build an offline session. The flag is inherited
    through the shared M5.1 layer, never reimplemented; this server opens no second
    network path of its own.
    """
    os.environ[OFFLINE_ENV] = "1"


# ---------------------------------------------------------------------------
# Tool 1: search_papers
# ---------------------------------------------------------------------------


def search_papers(
    query: str,
    *,
    sources: Sequence[str] | None = None,
    limit: int = 25,
    since: int | None = None,
    offline: bool = False,
    session: SnapshotSession | None = None,
    connectors: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Fan-out search across scholarly indexes. Thin wrapper over ``search.search_sync``.

    ``connectors`` (a sequence of already-bound connectors) is a passthrough for callers and
    tests that inject replayed sources; ordinary use names ``sources`` and lets the kernel
    build them. The return shape is ``SearchResult.to_json_dict()``, sanitized.
    """
    if int(limit) < 1:
        raise ValueError("limit must be at least 1")
    resolved = _resolve_session(session, offline)
    kwargs: dict[str, Any] = {"limit": int(limit), "since": since}
    if connectors is not None:
        kwargs["connectors"] = list(connectors)
    else:
        kwargs["sources"] = list(sources) if sources else None
        kwargs["session"] = resolved
    result = search_sync(query, **kwargs)
    return _sanitize(result.to_json_dict())


# ---------------------------------------------------------------------------
# Tool 2: get_paper
# ---------------------------------------------------------------------------


async def _get_by_id(
    identifier: str,
    sources: Sequence[str],
    session: SnapshotSession | None,
    connectors: Sequence[Any] | None,
) -> tuple[CSLRecord | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve one identifier across sources, isolating each source's failure.

    This is the ``get`` operation the CLI already implements: try ``resolve_doi`` when the
    identifier is a DOI and the source supports it, else ``get_by_id``. It calls only the
    connector methods that already exist; the loop adds no retrieval logic of its own. A
    missing snapshot is re-raised loudly (never demoted to a warning), matching the rest of
    the kernel.
    """
    from .connectors import create_connector
    from .connectors.base import SourceError
    from .dedupe import dedupe
    from .snapshots import SnapshotMissingError

    owned: list[Any] = []
    if connectors is not None:
        pool = list(connectors)
    else:
        names = list(sources) if sources else list(DEFAULT_SEARCH_SOURCES)
        pool = [create_connector(name, snapshots=session) for name in names]
        owned = pool

    doi = normalize_doi(identifier)
    records: list[CSLRecord] = []
    outcomes: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        for connector in pool:
            try:
                if is_valid_doi(doi) and connector.supports("resolve_doi"):
                    record = await connector.resolve_doi(doi)
                elif connector.supports("get_by_id"):
                    record = await connector.get_by_id(identifier)
                else:
                    outcomes.append({"source": connector.name, "status": "unsupported"})
                    continue
            except SnapshotMissingError:
                raise
            except SourceError as exc:
                warning = {
                    "source": connector.name,
                    "operation": "get",
                    "kind": exc.kind.value,
                    "message": exc.message,
                    "status_code": exc.status_code,
                }
                warnings.append(warning)
                outcomes.append(
                    {"source": connector.name, "status": "error", "warning": warning}
                )
                continue
            outcomes.append(
                {
                    "source": connector.name,
                    "status": "ok",
                    "record_count": 1 if record is not None else 0,
                }
            )
            if record is not None:
                records.append(record)
    finally:
        for connector in owned:
            await connector.aclose()

    merged = dedupe(records)
    best = merged.records[0] if merged.records else None
    return best, outcomes, warnings


def get_paper(
    identifier: str,
    *,
    sources: Sequence[str] | None = None,
    offline: bool = False,
    session: SnapshotSession | None = None,
    connectors: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Resolve one paper by DOI or source id. Thin wrapper over the CLI ``get`` path.

    Returns ``{identifier, found, record, sources, warnings}``, where ``record`` is CSL-JSON
    or ``null`` when no source knew the identifier. A clean negative is a real answer, not an
    error, so ``found`` is ``False`` rather than a raised exception.
    """
    resolved = _resolve_session(session, offline)
    record, outcomes, warnings = asyncio.run(
        _get_by_id(identifier, sources or (), resolved, connectors)
    )
    return _sanitize(
        {
            "identifier": identifier,
            "found": record is not None,
            "record": record.to_csl_json() if record is not None else None,
            "sources": outcomes,
            "warnings": warnings,
        }
    )


# ---------------------------------------------------------------------------
# Tool 3: verify_citations
# ---------------------------------------------------------------------------


def _claim_from_reference(reference: Any) -> ReferenceClaim:
    """One :class:`ReferenceClaim` from a loose reference: a string, or a field mapping.

    A bare string is read as a DOI when it looks like one, else as a title. A mapping carries
    named fields (``title``, ``doi``, ``year``, ``authors``, ...) straight onto the claim.
    """
    if isinstance(reference, ReferenceClaim):
        return reference
    if isinstance(reference, str):
        text = reference.strip()
        if is_valid_doi(text):
            return ReferenceClaim(doi=text)
        return ReferenceClaim(title=text)
    if isinstance(reference, Mapping):
        allowed = {
            "key",
            "title",
            "doi",
            "arxiv_id",
            "year",
            "authors",
            "container_title",
            "entry_type",
            "raw",
        }
        fields = {k: v for k, v in reference.items() if k in allowed}
        return ReferenceClaim(**fields)
    raise ValueError(
        "each reference must be a DOI/title string or a field mapping, "
        f"not {type(reference).__name__}"
    )


def verify_citations(
    *,
    bibtex: str | None = None,
    references: Sequence[Any] | None = None,
    sources: Sequence[str] | None = None,
    check_status: bool = True,
    check_accessibility: bool = True,
    offline: bool = False,
    session: SnapshotSession | None = None,
) -> dict[str, Any]:
    """Verify citations on the four axes. Thin wrapper over ``verify.verify_claims``.

    Accepts a BibTeX document (``bibtex``) and/or a list of loose ``references`` (DOI or title
    strings, or field mappings). At least one must be non-empty. The result is the verify
    report ``verify_claims`` already produces, sanitized.
    """
    claims: list[ReferenceClaim] = []
    if bibtex and bibtex.strip():
        try:
            records = records_from_bib(bibtex)
        except BibError as exc:
            raise ValueError(f"cannot parse BibTeX: {exc}") from exc
        claims.extend(ReferenceClaim.from_record(record) for record in records)
    for reference in references or ():
        claims.append(_claim_from_reference(reference))
    if not claims:
        raise ValueError("verify_citations needs a bibtex document or a references list")

    resolved = _resolve_session(session, offline)
    report = verify_claims(
        claims,
        sources=list(sources) if sources else VERIFY_DEFAULT_SOURCES,
        snapshots=resolved,
        check_status=check_status,
        check_accessibility=check_accessibility,
        input_kind="bib" if bibtex else "references",
    )
    return _sanitize(report)


# ---------------------------------------------------------------------------
# Tool 4: export_bibliography
# ---------------------------------------------------------------------------


def _records_for_export(
    records: Sequence[Any] | None, bibtex: str | None
) -> list[CSLRecord]:
    """Collect :class:`CSLRecord` objects from CSL-JSON items and/or a BibTeX document."""
    collected: list[CSLRecord] = []
    for item in records or ():
        if isinstance(item, CSLRecord):
            collected.append(item)
        elif isinstance(item, Mapping):
            collected.append(CSLRecord.from_csl_json(item))
        else:
            raise ValueError(
                "each record must be CSL-JSON (a mapping) or a CSLRecord, "
                f"not {type(item).__name__}"
            )
    if bibtex and bibtex.strip():
        try:
            collected.extend(records_from_bib(bibtex))
        except BibError as exc:
            raise ValueError(f"cannot parse BibTeX: {exc}") from exc
    return collected


def _export_emitter(fmt: str) -> Callable[[Sequence[CSLRecord]], str] | None:
    """The optional ``export`` sibling's emitter for ``fmt`` (RIS, JATS), or ``None``.

    Imported defensively: RIS and JATS live in the ``export`` module a sibling M5.4 task
    builds. Without it, those formats are simply reported as unavailable rather than crashing
    the tool, and BibTeX plus CSL-JSON keep working from the base kernel.
    """
    import importlib

    try:
        export = importlib.import_module("researcher_core.export")
    except ImportError:
        return None
    name = {"ris": "to_ris", "jats": "to_jats_reflist"}.get(fmt)
    if name is None:
        return None
    fn = getattr(export, name, None)
    return fn if callable(fn) else None  # type: ignore[return-value]


def export_bibliography(
    *,
    records: Sequence[Any] | None = None,
    bibtex: str | None = None,
    format: str = "bibtex",
) -> dict[str, Any]:
    """Emit a bibliography in a requested format. Thin wrapper over the kernel emitters.

    ``bibtex`` and ``csl-json`` are always available from the base kernel. ``ris`` and
    ``jats`` come from the optional ``export`` module; when it is not installed the tool
    returns a structured ``error`` naming the missing capability rather than raising. Input
    is CSL-JSON ``records`` and/or a ``bibtex`` document (CSL-JSON is canonical, D4).
    """
    fmt = str(format).strip().lower()
    collected = _records_for_export(records, bibtex)

    if fmt in ("bibtex", "bib"):
        content = emit_bib(collected)
    elif fmt in ("csl-json", "csl", "json"):
        import json

        content = json.dumps([r.to_csl_json() for r in collected], ensure_ascii=False)
    else:
        emitter = _export_emitter(fmt)
        if emitter is None:
            return _sanitize(
                {
                    "format": fmt,
                    "error": "format-unavailable",
                    "message": (
                        f"format {fmt!r} is not available; "
                        f"always-available formats are {', '.join(ALWAYS_AVAILABLE_FORMATS)}. "
                        "RIS and JATS need the optional export module."
                    ),
                    "record_count": len(collected),
                }
            )
        content = emitter(collected)

    # The envelope is sanitized; the document itself is not. An exported bibliography is a
    # data artifact whose bytes must stay lossless (D4): tag stripping would gut JATS XML
    # and whitespace folding would reflow BibTeX, which is fabricating a different file.
    return _sanitize(
        {"format": fmt, "content": content, "record_count": len(collected)},
        preserve=("content",),
    )


# ---------------------------------------------------------------------------
# Tool 5: download_oa
# ---------------------------------------------------------------------------


def download_oa(
    identifier: str,
    *,
    offline: bool = False,
    session: SnapshotSession | None = None,
    connectors: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve and extract an open-access copy. Thin wrapper over ``fulltext.extract``.

    Returns the extracted document (text, sections, and the axis (d) accessibility verdict),
    sanitized. A PDF whose extraction needs the missing ``[fulltext]`` extra is reported as a
    structured ``error`` carrying the install message, never a raised ``MissingExtraError``,
    so an MCP client sees a clean result. This module NEVER fabricates text: a paywalled work
    comes back ``abstract-only`` with no segments, exactly as the kernel guarantees.
    """
    resolved = _resolve_session(session, offline)
    try:
        document = asyncio.run(
            extract(identifier, snapshots=resolved, connectors=connectors)
        )
    except MissingExtraError as exc:
        return _sanitize(
            {
                "identifier": identifier,
                "error": "missing-extra",
                "message": str(exc) or MISSING_EXTRA_MESSAGE,
            }
        )
    return _sanitize(document.to_json_dict())


# ---------------------------------------------------------------------------
# The FastMCP server (optional extra)
# ---------------------------------------------------------------------------


def _load_fastmcp() -> Any:
    """Return the ``FastMCP`` class from whichever provider is installed, or ``None``.

    The ``[mcp]`` extra pins ``fastmcp``; the official MCP SDK ships the same class under
    ``mcp.server.fastmcp`` and is accepted as a fallback. Either way the surface used here is
    the tiny common one: construct with a name, decorate tools, ``run()``.
    """
    try:
        from fastmcp import FastMCP  # type: ignore[import-not-found]

        return FastMCP
    except ImportError:
        pass
    try:
        # The assignment ignore covers environments where fastmcp AND the official SDK are
        # both installed: the two FastMCP classes are distinct types to mypy.
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found,assignment]

        return FastMCP
    except ImportError:
        return None


def fastmcp_available() -> bool:
    """True when a FastMCP provider is importable in this environment."""
    return _load_fastmcp() is not None


def build_server(*, offline: bool = False, name: str = "researcher-core") -> Any:
    """Construct the FastMCP server registering the five stable tools.

    Requires the ``[mcp]`` extra. Raises :class:`MissingExtraError` with the install hint
    when FastMCP is absent, so callers get one actionable line rather than an ``ImportError``.
    Each registered tool is an async wrapper that runs its plain sync callable in a worker
    thread, so the synchronous kernel entry points (which drive their own event loop) never
    collide with the server's running loop.
    """
    fastmcp = _load_fastmcp()
    if fastmcp is None:
        raise MissingExtraError(MISSING_FASTMCP_MESSAGE)

    import functools

    import anyio

    if offline:
        _apply_offline()

    server = fastmcp(name)

    async def _run(fn: Callable[..., Any], /, **kwargs: Any) -> Any:
        return await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))

    @server.tool()
    async def search_papers_tool(  # type: ignore[no-untyped-def]
        query: str,
        sources: list[str] | None = None,
        limit: int = 25,
        since: int | None = None,
    ) -> dict[str, Any]:
        """Search scholarly indexes and return deduplicated, ranked records."""
        return await _run(
            search_papers,
            query=query,
            sources=sources,
            limit=limit,
            since=since,
            offline=offline,
        )

    @server.tool()
    async def get_paper_tool(  # type: ignore[no-untyped-def]
        identifier: str, sources: list[str] | None = None
    ) -> dict[str, Any]:
        """Resolve one paper by DOI or source identifier."""
        return await _run(
            get_paper, identifier=identifier, sources=sources, offline=offline
        )

    @server.tool()
    async def verify_citations_tool(  # type: ignore[no-untyped-def]
        bibtex: str | None = None,
        references: list[Any] | None = None,
        sources: list[str] | None = None,
        check_status: bool = True,
        check_accessibility: bool = True,
    ) -> dict[str, Any]:
        """Verify citations on the four axes: identity, status, faithfulness, accessibility."""
        return await _run(
            verify_citations,
            bibtex=bibtex,
            references=references,
            sources=sources,
            check_status=check_status,
            check_accessibility=check_accessibility,
            offline=offline,
        )

    @server.tool()
    async def export_bibliography_tool(  # type: ignore[no-untyped-def]
        records: list[Any] | None = None,
        bibtex: str | None = None,
        format: str = "bibtex",
    ) -> dict[str, Any]:
        """Emit a bibliography as BibTeX, CSL-JSON, RIS, or JATS."""
        return await _run(
            export_bibliography, records=records, bibtex=bibtex, format=format
        )

    @server.tool()
    async def download_oa_tool(identifier: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Resolve and extract an open-access full text, with the accessibility verdict."""
        return await _run(download_oa, identifier=identifier, offline=offline)

    return server


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point for ``researcher-mcp``.

    Runs the stdio MCP server. When the ``[mcp]`` extra is not installed, it prints the
    install hint to stderr and exits 1, never a traceback, mirroring how the CLI reports a
    missing ``[fulltext]`` extra.
    """
    parser = argparse.ArgumentParser(
        prog="researcher-mcp",
        description="Thin stable-core MCP server: search, get, verify, export, download-oa.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="answer only from snapshots and cache; never touch the network (M5.1).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not fastmcp_available():
        print(MISSING_FASTMCP_MESSAGE, file=sys.stderr)
        return 1

    server = build_server(offline=args.offline)
    server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via the console entry
    raise SystemExit(main())
