"""The command-line interface: how skills talk to the kernel (M2.11).

Skills never import this package. They shell out to it::

    uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<query>" --json

so every capability the kernel has must be reachable from here, and everything reachable from
here must be honest about what it did. Three rules hold across every command:

1. **Two output modes, one truth.** ``--json`` emits the machine shape, which is validated
   against ``core/schemas/*.json`` in ``tests/test_cli.py``. Without it the same data renders
   as a compact human table. The table is a projection of the JSON, never a second source of
   facts, so a human and a script never read different answers off the same run.

2. **Determinism is a mode, not a hope (D15).** ``--record`` makes live calls and writes
   snapshots. ``RESEARCHER_CORE_SNAPSHOT_MODE=replay`` reads snapshots and never opens a
   socket: a missing snapshot raises loudly rather than quietly going live. Nothing here
   generates a timestamp, so two replays of one snapshot set produce byte-identical output.

3. **jsonschema is never imported.** Schema validation is a test-time concern (D3), so the
   base runtime install stays at httpx, rapidfuzz, platformdirs. This module imports none of
   it, and the test suite does the validating.

Exit codes: ``0`` success, ``1`` an operational failure (a downed source, a missing snapshot,
a missing extra, nothing found where something was asked for), ``2`` invalid arguments, with
usage text, which is argparse's own convention and is preserved deliberately.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import PARSER_VERSION, PROTOCOL_VERSION, __version__
from .bib import BibError, records_from_bib
from .connectors import SourceError, available_connectors, create_connector
from .fulltext import ExtractedDocument, FullTextError, MissingExtraError, extract, resolve_oa
from .graph import DEFAULT_GRAPH_SOURCES, MAX_DEPTH, GraphResult, traverse
from .model import CSLRecord, is_valid_doi, normalize_doi
from .provenance import (
    EVENT_TYPES,
    PROVENANCE_SCHEMA_VERSION,
    ProvenanceError,
    ProvenanceEvent,
    ProvenanceLedger,
    Versions,
)
from .search import DEFAULT_SEARCH_SOURCES, SearchResult, search_sync
from .snapshots import (
    Snapshot,
    SnapshotError,
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
    diff_snapshot,
)
from .status import DEFAULT_STATUS_SOURCES, check_status
from .verify import DEFAULT_SOURCES as DEFAULT_VERIFY_SOURCES
from .verify import ReferenceClaim, verify_claims

__all__ = ["build_parser", "main"]

PROG = "researcher-core"

#: Every command in the plan's CLI surface table. Kept here so ``--help`` and the reference
#: doc (``references/core-cli.md``) can be checked against one list.
COMMANDS: tuple[str, ...] = (
    "search",
    "get",
    "verify-bib",
    "verify-ref",
    "status",
    "citations",
    "references",
    "oa-pdf",
    "fulltext",
    "passages",
    "faithfulness",
    "snapshot",
    "provenance",
    "compile",
)


class CLIError(RuntimeError):
    """An operational failure to report as ``exit 1``, with no traceback.

    Distinct from an argument error, which argparse reports as ``exit 2`` with usage text.
    The difference matters to a skill: a 2 means the invocation was wrong and retrying it
    unchanged is pointless, while a 1 means the invocation was fine and the world did not
    cooperate.
    """


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def configure_streams() -> None:
    """Force UTF-8, LF output on Windows consoles (D5).

    Without this, a Cyrillic author name or an en dash in a title raises
    ``UnicodeEncodeError`` under the default Windows code page, and CRLF translation would
    make "byte-identical" output a per-platform claim rather than a real one.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", newline="\n")
        except (ValueError, OSError):  # pragma: no cover - a stream that cannot be retuned
            pass


def emit_json(payload: Any) -> None:
    """Write one JSON document to stdout. The machine surface, and the validated one."""
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def emit(text: str) -> None:
    sys.stdout.write(f"{text}\n")


def render_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """A compact fixed-width table. The default human surface for every list command."""
    if not rows:
        return "(no rows)"
    columns = [[str(h) for h in headers]] + [[_cell(c) for c in row] for row in rows]
    widths = [max(len(row[i]) for row in columns) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(columns[0])).rstrip()]
    lines.append("  ".join("-" * width for width in widths))
    for row in columns[1:]:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    return "\n".join(lines)


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def truncate(text: str, width: int) -> str:
    text = str(text or "")
    return text if len(text) <= width else text[: width - 1] + "…"


def record_json(record: CSLRecord) -> dict[str, Any]:
    """CSL-JSON for one record, in the shape ``record.schema.json`` actually accepts.

    The schema types ``ISSN`` and ``keyword`` as string-or-number, exactly as upstream
    ``csl-data.json`` does, while :class:`~researcher_core.model.CSLRecord` types both as
    lists and serializes JSON arrays. Emitting a multi-ISSN journal record straight out of
    the model would therefore produce output the contract rejects. ``bib.py`` already settled
    this the same way for BibTeX input: both fields ride under the open ``custom`` extension
    rather than in the standard CSL namespace, losslessly, and nothing downstream loses a
    value. The schema is the contract, so the emitter bends, not the schema.
    """
    data = record.to_csl_json()
    custom: dict[str, Any] = dict(data.get("custom") or {})
    for csl_key, custom_key in (("ISSN", "issn"), ("keyword", "keywords")):
        value = data.pop(csl_key, None)
        if isinstance(value, list):
            if value:
                custom.setdefault(custom_key, list(value))
        elif value:
            data[csl_key] = value
    if custom:
        data["custom"] = custom
    return data


def record_rows(records: Sequence[CSLRecord]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for position, record in enumerate(records, start=1):
        sources = record.extra.get("sources")
        if not isinstance(sources, list) or not sources:
            sources = [record.source] if record.source else []
        rows.append(
            [
                position,
                record.year or "-",
                truncate(record.first_author_surname or "-", 18),
                truncate(record.title or "(untitled)", 58),
                ",".join(str(s) for s in sources) or "-",
                record.DOI or record.arxiv_id or record.id,
            ]
        )
    return rows


RECORD_HEADERS = ("#", "YEAR", "AUTHOR", "TITLE", "SOURCES", "ID")


def warning_lines(warnings: Sequence[Mapping[str, Any]]) -> list[str]:
    """One line per failed source. A result assembled while an index was down is not the
    same evidence as one assembled with every index answering, so it is always said out loud.
    """
    return [
        f"warning: {w.get('source')} {w.get('operation')} failed "
        f"({w.get('kind')}): {w.get('message')}"
        for w in warnings
    ]


# ---------------------------------------------------------------------------
# Session and argument plumbing
# ---------------------------------------------------------------------------


def build_session(args: argparse.Namespace) -> SnapshotSession:
    """The snapshot session for this invocation.

    Mode comes from the environment (``live`` unless told otherwise) and ``--record``
    overrides it to ``record``. Replay mode is set by the environment alone, because a test
    or an eval runner is the only thing that should ever be in it, and a stray ``--replay``
    flag on a user's command line would be an invitation to think the network was consulted
    when it was not.
    """
    session = SnapshotSession.from_env()
    if getattr(args, "record", False):
        session.mode = SnapshotMode.RECORD
    return session


def snapshot_store(args: argparse.Namespace, session: SnapshotSession) -> SnapshotStore:
    override = getattr(args, "store", None)
    return SnapshotStore(override) if override else session.store


def parse_sources(
    parser: argparse.ArgumentParser, raw: str | None, default: Sequence[str]
) -> list[str]:
    """``--sources a,b,c`` into a validated list. An unknown name is an argument error."""
    if not raw:
        return list(default)
    names = [name.strip().lower() for name in str(raw).split(",") if name.strip()]
    if not names:
        parser.error("--sources was given but names no source")
    known = available_connectors()
    unknown = [name for name in names if name not in known]
    if unknown:
        parser.error(
            f"unknown source(s): {', '.join(unknown)}. Available: {', '.join(known)}"
        )
    return names


def parse_params(parser: argparse.ArgumentParser, raw: Sequence[str] | None) -> dict[str, Any]:
    """``-p key=value`` pairs into request params.

    Values are read as JSON when they parse as JSON, so ``-p per-page=5`` is the integer 5,
    which is what the recorded request key was built from. A value that is not JSON stays a
    string, so ``-p search=self-supervised ECG`` needs no quoting gymnastics.
    """
    params: dict[str, Any] = {}
    for item in raw or ():
        key, sep, value = str(item).partition("=")
        if not sep or not key.strip():
            parser.error(f"--param expects key=value, got {item!r}")
        try:
            params[key.strip()] = json.loads(value)
        except json.JSONDecodeError:
            params[key.strip()] = value
    return params


def read_bib_records(path: Path) -> list[CSLRecord]:
    if not path.is_file():
        raise CLIError(f"No such file: {path}")
    try:
        return records_from_bib(path)
    except BibError as exc:
        raise CLIError(f"Cannot parse {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def cmd_search(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    sources = parse_sources(parser, args.sources, DEFAULT_SEARCH_SOURCES)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    session = build_session(args)
    result: SearchResult = search_sync(
        args.query,
        sources=sources,
        limit=args.limit,
        since=args.since,
        session=session,
    )

    if args.json:
        payload = result.to_json_dict()
        payload["records"] = [record_json(record) for record in result.records]
        emit_json(payload)
        return 0

    emit(render_table(RECORD_HEADERS, record_rows(result.records)))
    counts = (
        f"{result.retrieved_count} retrieved, {len(result.records)} after dedupe "
        f"({result.duplicates_removed} duplicates removed)"
    )
    emit("")
    emit(f"{counts}; sources ok: {', '.join(result.sources_ok) or 'none'}")
    for line in warning_lines([w.to_json_dict() for w in result.warnings]):
        emit(line)
    return 0


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def _resolve_one(
    identifier: str, sources: Sequence[str], session: SnapshotSession
) -> tuple[list[CSLRecord], list[dict[str, Any]], list[dict[str, Any]]]:
    """Ask every source for one identifier. Per-source isolation, exactly as in search.py."""
    from .dedupe import dedupe

    connectors = [create_connector(name, snapshots=session) for name in sources]
    doi = normalize_doi(identifier)
    records: list[CSLRecord] = []
    outcomes: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        for connector in connectors:
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
        for connector in connectors:
            await connector.aclose()

    merged = dedupe(records)
    return merged.records, outcomes, warnings


def cmd_get(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    sources = parse_sources(parser, args.sources, DEFAULT_SEARCH_SOURCES)
    session = build_session(args)
    records, outcomes, warnings = asyncio.run(
        _resolve_one(args.identifier, sources, session)
    )
    record = records[0] if records else None

    if args.json:
        emit_json(
            {
                "identifier": args.identifier,
                "found": record is not None,
                "record": record_json(record) if record is not None else None,
                "sources": outcomes,
                "warnings": warnings,
            }
        )
    else:
        if record is None:
            emit(f"not found: {args.identifier}")
        else:
            emit(render_table(RECORD_HEADERS, record_rows([record])))
        for line in warning_lines(warnings):
            emit(line)

    # A clean negative is a real answer, and it is reported as one. It is still a non-zero
    # exit, so a shell pipeline that asked for a record and got none notices.
    return 0 if record is not None else 1


# ---------------------------------------------------------------------------
# verify-bib, verify-ref
# ---------------------------------------------------------------------------


VERIFY_HEADERS = ("KEY", "IDENTITY", "REFUSAL", "STATUS", "ACCESS", "SOURCES", "TITLE")


def verify_rows(report: Mapping[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for entry in report.get("entries", []):
        tally = entry.get("tally", {})
        status = entry.get("status", {})
        rows.append(
            [
                truncate(entry.get("key") or "-", 24),
                entry.get("verdict"),
                entry.get("refusal_grade"),
                status.get("verdict") if status.get("checked") else "unchecked",
                (entry.get("accessibility") or {}).get("verdict"),
                f"{tally.get('confirmed', 0)}c/{tally.get('negative', 0)}n/"
                f"{tally.get('source_error', 0)}e",
                truncate((entry.get("reference") or {}).get("title") or "-", 44),
            ]
        )
    return rows


def emit_verify_report(report: Mapping[str, Any]) -> None:
    emit(render_table(VERIFY_HEADERS, verify_rows(report)))
    summary = report.get("summary", {})
    identity = summary.get("identity", {})
    emit("")
    emit(
        f"{summary.get('total', 0)} entries: "
        f"{identity.get('verified', 0)} verified, "
        f"{identity.get('mismatch', 0)} mismatch, "
        f"{identity.get('unresolvable', 0)} unresolvable, "
        f"{identity.get('inconclusive', 0)} inconclusive"
    )
    emit(
        f"refusal-grade: {summary.get('refusal_grade', 0)} "
        "(only unresolvable and mismatch are ever refusal-grade; inconclusive never is)"
    )
    for entry in report.get("entries", []):
        if entry.get("refusal_grade"):
            emit(f"  {entry.get('key')}: {entry.get('reason')}")
        status = entry.get("status", {})
        if status.get("checked") and status.get("verdict") != "current":
            emit(f"  {entry.get('key')}: axis (b) {status.get('verdict')}")


def cmd_verify_bib(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    sources = parse_sources(parser, args.sources, DEFAULT_VERIFY_SOURCES)
    path = Path(args.path)
    records = read_bib_records(path)
    claims = [ReferenceClaim.from_record(record) for record in records]
    report = verify_claims(
        claims,
        sources=sources,
        snapshots=build_session(args),
        input_kind="bib",
        input_path=str(path),
        run_id=args.run_id or "",
    )
    if args.json:
        emit_json(report)
    else:
        emit_verify_report(report)
    return 0


def cmd_verify_ref(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    sources = parse_sources(parser, args.sources, DEFAULT_VERIFY_SOURCES)
    reference = args.reference.strip()
    if not reference:
        parser.error("reference must not be empty")
    claim = (
        ReferenceClaim(doi=reference)
        if is_valid_doi(reference)
        else ReferenceClaim(title=reference)
    )
    report = verify_claims(
        [claim],
        sources=sources,
        snapshots=build_session(args),
        input_kind="reference",
        input_reference=reference,
        run_id=args.run_id or "",
    )
    if args.json:
        emit_json(report)
    else:
        emit_verify_report(report)
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


STATUS_HEADERS = ("DOI", "STATUS", "CHECKED", "CONFLICT", "NOTICES", "REASON")


def cmd_status(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    sources = parse_sources(parser, args.sources, DEFAULT_STATUS_SOURCES)
    target = args.target
    path = Path(target)
    if path.is_file():
        dois = [record.DOI for record in read_bib_records(path) if record.DOI]
        if not dois:
            raise CLIError(f"{path} carries no DOI, so axis (b) has nothing to check.")
        report = check_status(
            dois,
            sources=sources,
            snapshots=build_session(args),
            input_kind="bib",
            input_path=str(path),
            run_id=args.run_id or "",
        )
    else:
        doi = normalize_doi(target)
        if not is_valid_doi(doi):
            parser.error(
                f"{target!r} is neither a readable .bib file nor a DOI (expected 10.xxxx/yyyy)"
            )
        report = check_status(
            [doi],
            sources=sources,
            snapshots=build_session(args),
            input_kind="doi",
            input_doi=doi,
            run_id=args.run_id or "",
        )

    if args.json:
        emit_json(report)
        return 0

    rows = [
        [
            truncate(entry.get("doi") or entry.get("id") or "-", 40),
            entry.get("verdict"),
            entry.get("checked"),
            entry.get("conflict"),
            len(entry.get("notices") or []),
            truncate(entry.get("reason") or "-", 60),
        ]
        for entry in report.get("entries", [])
    ]
    emit(render_table(STATUS_HEADERS, rows))
    summary = report.get("summary", {})
    counts = summary.get("status", {})
    emit("")
    emit(
        f"{summary.get('total', 0)} checked: "
        f"{counts.get('current', 0)} current, {counts.get('corrected', 0)} corrected, "
        f"{counts.get('retracted', 0)} retracted, "
        f"{counts.get('expression-of-concern', 0)} expression-of-concern; "
        f"{summary.get('unchecked', 0)} unchecked"
    )
    if summary.get("unchecked"):
        emit("an unchecked status is an absence of evidence, not evidence of currency")
    return 0


# ---------------------------------------------------------------------------
# citations, references
# ---------------------------------------------------------------------------


def _traverse(args: argparse.Namespace, parser: argparse.ArgumentParser, direction: str) -> int:
    sources = parse_sources(parser, args.sources, DEFAULT_GRAPH_SOURCES)
    depth = getattr(args, "depth", 1)
    if depth < 1 or depth > MAX_DEPTH:
        parser.error(f"--depth must be between 1 and {MAX_DEPTH}")
    session = build_session(args)
    result: GraphResult = asyncio.run(
        traverse(
            [args.identifier],
            direction=direction,
            depth=depth,
            limit=args.limit,
            sources=sources,
            session=session,
        )
    )

    if args.json:
        payload = result.to_json_dict()
        payload["nodes"] = [record_json(record) for record in result.nodes]
        emit_json(payload)
        return 0

    emit(render_table(RECORD_HEADERS, record_rows(result.nodes)))
    emit("")
    emit(
        f"{len(result.nodes)} nodes, {len(result.edges)} edges at depth {depth} "
        f"({direction}); sources ok: "
        f"{', '.join(o.source for o in result.outcomes if o.ok) or 'none'}"
    )
    for line in warning_lines([w.to_json_dict() for w in result.warnings]):
        emit(line)
    return 0


def cmd_citations(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    return _traverse(args, parser, "forward")


def cmd_references(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    return _traverse(args, parser, "backward")


# ---------------------------------------------------------------------------
# oa-pdf
# ---------------------------------------------------------------------------


def cmd_oa_pdf(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    doi = normalize_doi(args.doi)
    if not is_valid_doi(doi):
        parser.error(f"{args.doi!r} is not a DOI (expected 10.xxxx/yyyy)")
    session = build_session(args)
    resolution = asyncio.run(resolve_oa(doi, snapshots=session))
    payload = resolution.to_json_dict()

    if args.json:
        emit_json(payload)
    else:
        location = resolution.location
        emit(f"{doi}: {resolution.verdict}")
        if location is not None:
            emit(f"  url:    {location.url}")
            emit(f"  type:   {location.content_type}")
            emit(f"  source: {location.source or '-'}")
            emit(f"  license: {location.license or '-'}")
        emit(f"  cascade: {', '.join(resolution.sources_tried) or 'none'}")
        for error in resolution.errors:
            emit(f"  warning: {error.get('source')} errored ({error.get('kind')})")

    return 0 if resolution.location is not None else 1


# ---------------------------------------------------------------------------
# fulltext
# ---------------------------------------------------------------------------


def cmd_fulltext(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    session = build_session(args)
    document: ExtractedDocument = asyncio.run(
        extract(args.identifier, snapshots=session)
    )
    payload = document.to_json_dict()

    if args.json:
        # One shape, always, whether or not --sections was passed: the document dict already
        # carries the section list, so a consumer never has to run the command twice.
        emit_json(payload)
        return 0

    emit(f"{document.doc_id}: {document.accessibility}")
    emit(f"  source:    {document.source or '-'}")
    emit(f"  url:       {document.url or '-'}")
    emit(f"  chars:     {len(document.text)}")
    emit(f"  sections:  {len(document.sections())}")
    emit(f"  segments:  {len(document.segments)}")
    if document.reason:
        emit(f"  reason:    {document.reason}")

    if args.sections and document.segments:
        emit("")
        emit(
            render_table(
                ("#", "SECTION", "START", "END", "CHARS", "PAGES"),
                [
                    [
                        segment.ordinal,
                        truncate(segment.section_path or "(body)", 40),
                        segment.char_start,
                        segment.char_end,
                        segment.char_end - segment.char_start,
                        ",".join(str(rect.page) for rect in segment.page_coords) or "-",
                    ]
                    for segment in document.segments
                ],
            )
        )
    return 0


# ---------------------------------------------------------------------------
# passages
# ---------------------------------------------------------------------------


def open_index(args: argparse.Namespace) -> Any:
    from .passages import PassageIndex, PassageIndexError

    try:
        return PassageIndex(args.db)
    except PassageIndexError as exc:
        raise CLIError(str(exc)) from exc


PASSAGE_HEADERS = ("#", "PASSAGE", "SECTION", "CHARS", "PAGES", "BM25", "TEXT")


def passage_rows(passages: Sequence[Any]) -> list[list[Any]]:
    return [
        [
            position,
            passage.passage_id[:12],
            truncate(passage.section_path or "(body)", 26),
            f"{passage.char_start}-{passage.char_end}",
            ",".join(str(rect.page) for rect in passage.page_coords) or "-",
            "-" if passage.bm25_score is None else f"{passage.bm25_score:.3f}",
            truncate(passage.text, 50),
        ]
        for position, passage in enumerate(passages, start=1)
    ]


def cmd_passages_index(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    session = build_session(args)
    document = asyncio.run(extract(args.identifier, snapshots=session))
    index = open_index(args)
    try:
        passages = index.index_document(document)
        record = index.get_document(document.doc_id)
    finally:
        index.close()

    if args.json:
        emit_json(
            {
                "document": record.to_json_dict() if record is not None else None,
                "passages": [passage.to_json_dict() for passage in passages],
            }
        )
        return 0

    emit(f"{document.doc_id}: {document.accessibility}, {len(passages)} passages indexed")
    if not passages:
        # Never silently. An abstract-only document is indexed with zero passages ON PURPOSE:
        # that verdict is what makes axis (c) abstain instead of pretending it looked.
        emit(f"  reason: {document.reason or 'no full text was reachable'}")
        return 0
    emit("")
    emit(render_table(PASSAGE_HEADERS, passage_rows(passages)))
    return 0


def cmd_passages_search(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    index = open_index(args)
    try:
        passages = index.search(args.query, doc_id=args.doc, limit=args.limit)
    finally:
        index.close()

    if args.json:
        emit_json(
            {
                "query": args.query,
                "doc_id": args.doc,
                "count": len(passages),
                "passages": [passage.to_json_dict() for passage in passages],
            }
        )
        return 0

    if not passages:
        emit(f"no passage matched: {args.query!r}")
        return 0
    emit(render_table(PASSAGE_HEADERS, passage_rows(passages)))
    return 0


# ---------------------------------------------------------------------------
# faithfulness
# ---------------------------------------------------------------------------


def cmd_faithfulness(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from .faithfulness import FaithfulnessError, check_claims

    index = open_index(args)
    try:
        report = check_claims(
            [args.claim],
            args.doc,
            index,
            top_k=args.top_k,
            run_id=args.run_id or "",
        )
    except FaithfulnessError as exc:
        raise CLIError(str(exc)) from exc
    finally:
        index.close()

    payload = report.to_json_dict()
    if args.json:
        emit_json(payload)
        return 0

    for claim in payload.get("claims", []):
        emit(f"{claim.get('verdict')} (clean: {'yes' if claim.get('clean') else 'no'})")
        emit(f"  claim:  {claim.get('claim')}")
        emit(f"  reason: {claim.get('reason')}")
        for anchor in claim.get("evidence", []):
            emit(
                f"  anchor: {anchor.get('passage_id', '')[:12]} "
                f"[{anchor.get('section_path') or '(body)'} "
                f"{anchor.get('char_start')}-{anchor.get('char_end')}]"
            )
            emit(f"          {truncate(anchor.get('text') or '', 76)}")
    document = payload.get("document", {})
    emit("")
    emit(
        f"document {document.get('doc_id')}: axis (d) {document.get('accessibility')}, "
        f"{document.get('passage_count')} passages, method {payload.get('method')}"
    )
    return 0


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------


def cmd_snapshot_record(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    params = parse_params(parser, args.param)
    if args.source not in available_connectors():
        parser.error(
            f"unknown source {args.source!r}. Available: {', '.join(available_connectors())}"
        )
    store = SnapshotStore(args.store) if args.store else SnapshotStore.eval_store()
    session = SnapshotSession(store, SnapshotMode.RECORD, retrieved_at=args.retrieved_at)

    async def run() -> Any:
        connector = create_connector(args.source, snapshots=session)
        try:
            return await connector.request_json(args.endpoint, params)
        finally:
            await connector.aclose()

    try:
        asyncio.run(run())
    except SourceError as exc:
        raise CLIError(str(exc)) from exc
    snapshot = store.load(args.source, args.endpoint, params)

    if args.json:
        emit_json(snapshot.to_json_dict())
    else:
        emit(f"recorded {snapshot.source}/{snapshot.endpoint}")
        emit(f"  request_key:   {snapshot.request_key}")
        emit(f"  response_hash: {snapshot.response_hash}")
        emit(f"  path:          {store.path_for_key(snapshot.source, snapshot.request_key)}")
    return 0


def cmd_snapshot_replay(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    session = build_session(args)
    store = snapshot_store(args, session)

    if args.source and args.endpoint:
        params = parse_params(parser, args.param)
        snapshot = store.load(args.source, args.endpoint, params)
        if args.json:
            emit_json(snapshot.to_json_dict())
        else:
            emit(f"{snapshot.source}/{snapshot.endpoint}")
            emit(f"  request_key:   {snapshot.request_key}")
            emit(f"  response_hash: {snapshot.response_hash}")
            emit(f"  retrieved_at:  {snapshot.retrieved_at}")
        return 0

    if args.source or args.endpoint:
        parser.error("snapshot replay needs both a source and an endpoint, or neither")

    # The whole stored request set, verified on the way out: every body is re-hashed against
    # its stored response_hash, so a corrupted or hand-edited snapshot fails here rather than
    # silently changing a verdict downstream.
    snapshots: list[Snapshot] = []
    for source in store.sources():
        for snapshot in store.iter_snapshots(source):
            snapshot.verify()
            snapshots.append(snapshot)

    if args.json:
        emit_json([snapshot.to_json_dict() for snapshot in snapshots])
        return 0

    emit(
        render_table(
            ("SOURCE", "ENDPOINT", "RESPONSE_HASH", "RETRIEVED_AT"),
            [
                [
                    snapshot.source,
                    truncate(snapshot.endpoint, 40),
                    snapshot.response_hash[:16],
                    snapshot.retrieved_at,
                ]
                for snapshot in snapshots
            ],
        )
    )
    emit("")
    emit(f"{len(snapshots)} snapshots in {store.root}, all hashes verified")
    return 0


def cmd_snapshot_diff(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    session = build_session(args)
    store = snapshot_store(args, session)

    if args.live_from:
        # The offline diff: a stored snapshot against a live-SHAPED response fixture. This is
        # what makes drift reporting testable without the network.
        if not (args.source and args.endpoint):
            parser.error("--live-from needs a source and an endpoint to diff against")
        params = parse_params(parser, args.param)
        try:
            live_body = json.loads(Path(args.live_from).read_text(encoding="utf-8"))
        except OSError as exc:
            raise CLIError(f"Cannot read {args.live_from}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CLIError(f"{args.live_from} is not valid JSON: {exc}") from exc
        diffs = [store.diff(args.source, args.endpoint, params, live_body)]
    elif args.all:
        diffs = asyncio.run(_diff_store_live(store))
    else:
        if not (args.source and args.endpoint):
            parser.error("snapshot diff needs a source and an endpoint, or --all")
        params = parse_params(parser, args.param)
        stored = store.load(args.source, args.endpoint, params)
        diffs = [asyncio.run(_diff_one_live(stored, store))]

    changed = [d for d in diffs if d.changed]
    if args.json:
        emit_json(
            {
                "compared": len(diffs),
                "changed": len(changed),
                "diffs": [d.to_json_dict() for d in diffs],
            }
        )
        return 0

    emit(
        render_table(
            ("SOURCE", "ENDPOINT", "CHANGED", "FIELDS"),
            [
                [d.source, truncate(d.endpoint, 44), d.changed, len(d.fields)]
                for d in diffs
            ],
        )
    )
    emit("")
    emit(f"{len(diffs)} compared, {len(changed)} drifted")
    for diff in changed:
        for field in diff.fields[:20]:
            emit(f"  {diff.source}/{diff.endpoint} {field.kind}: {field.path}")
    return 0


async def _diff_one_live(stored: Snapshot, store: SnapshotStore) -> Any:
    """Re-run one stored request live and diff the response against the stored body.

    The session is LIVE with no cache: a cached body would make the diff compare the store
    against itself and report no drift, which is the one answer a drift report must never be
    able to give by accident. Nothing is written back, so the stored snapshot survives the
    comparison untouched and a refresh stays a deliberate act.
    """
    live_session = SnapshotSession(store, SnapshotMode.LIVE, cache=None)
    connector = create_connector(stored.source, snapshots=live_session)
    try:
        body = await connector.request_json(stored.endpoint, stored.request_params)
    finally:
        await connector.aclose()
    return diff_snapshot(stored, body)


async def _diff_store_live(store: SnapshotStore) -> list[Any]:
    """The canary sweep: every stored request, re-run live, diffed."""
    diffs = []
    for snapshot in store.iter_snapshots():
        try:
            diffs.append(await _diff_one_live(snapshot, store))
        except SourceError as exc:
            raise CLIError(
                f"Cannot diff {snapshot.source}/{snapshot.endpoint} against the live API: {exc}"
            ) from exc
    return diffs


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------


def open_ledger(args: argparse.Namespace) -> ProvenanceLedger:
    return ProvenanceLedger(args.ledger) if args.ledger else ProvenanceLedger()


def event_from_mapping(data: Mapping[str, Any]) -> ProvenanceEvent:
    """Build an event from a caller-supplied JSON object.

    ``run_id``, ``type``, ``ts``, and ``payload`` are the caller's business. Everything else
    (the schema and protocol versions, the component versions, the content-addressed event
    id) has exactly one correct value, which the kernel knows and the caller should not have
    to type. ``ts`` stays caller-supplied and is never generated here: a self-generated
    timestamp would make two replays of one run produce two different ledgers (D15).
    """
    missing = [key for key in ("run_id", "type", "ts") if not data.get(key)]
    if missing:
        raise CLIError(
            f"The event is missing required field(s) {', '.join(missing)}. "
            "A minimal event is "
            '{"run_id": "...", "type": "retrieval", "ts": "2026-07-14T12:00:00Z", '
            '"payload": {...}}. ts is caller-supplied on purpose, so replays stay '
            "deterministic."
        )
    if data["type"] not in EVENT_TYPES:
        raise CLIError(
            f"Unknown event type {data['type']!r}. The vocabulary is closed: "
            f"{', '.join(EVENT_TYPES)}."
        )
    return ProvenanceEvent(
        run_id=str(data["run_id"]),
        type=str(data["type"]),
        ts=str(data["ts"]),
        payload=dict(data.get("payload") or {}),
        source_response_hashes=tuple(str(h) for h in data.get("source_response_hashes") or ()),
        versions=Versions.from_json_dict(data.get("versions")),
        protocol_version=str(data.get("protocol_version") or PROTOCOL_VERSION),
        event_id=str(data.get("event_id") or ""),
        schema_version=str(data.get("schema_version") or PROVENANCE_SCHEMA_VERSION),
    )


def load_event_json(raw: str) -> Mapping[str, Any]:
    """The event argument: inline JSON, a path to a JSON file, or ``-`` for stdin."""
    text = raw
    if raw == "-":
        text = sys.stdin.read()
    else:
        candidate = Path(raw)
        try:
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - a path too long to even stat
            pass
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CLIError(
            f"The event is not valid JSON: {exc}. Pass inline JSON, a path to a JSON file, "
            "or '-' to read from stdin."
        ) from exc
    if not isinstance(data, Mapping):
        raise CLIError("A provenance event must be a JSON object.")
    return data


def cmd_provenance_append(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    event = event_from_mapping(load_event_json(args.event))
    ledger = open_ledger(args)
    try:
        stored = ledger.append(event)
    except ProvenanceError as exc:
        raise CLIError(str(exc)) from exc
    finally:
        ledger.close()

    if args.json:
        emit_json(stored.to_json_dict())
    else:
        emit(f"appended {stored.type} event {stored.event_id[:16]} to run {stored.run_id}")
        emit(f"  ts:        {stored.ts}")
        emit(f"  snapshots: {len(stored.source_response_hashes)}")
    return 0


def cmd_provenance_prisma(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    ledger = open_ledger(args)
    try:
        counts = ledger.prisma(args.run_id)
    finally:
        ledger.close()
    payload = counts.to_json_dict()

    if args.json:
        emit_json(payload)
        return 0

    emit(
        render_table(
            ("STAGE", "N"),
            [
                ["identified", payload["identified"]],
                ["duplicates removed", payload["duplicates_removed"]],
                ["after duplicates removed", payload["deduplicated"]],
                ["screened", payload["screened"]],
                ["included", payload["included"]],
                ["excluded", payload["excluded"]],
            ],
        )
    )
    if payload["identified_by_source"]:
        emit("")
        emit(
            render_table(
                ("SOURCE", "IDENTIFIED"),
                [[name, n] for name, n in payload["identified_by_source"].items()],
            )
        )
    emit("")
    emit("counts are DERIVED by aggregating events, never stored (D10)")
    return 0


def cmd_provenance_export(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    ledger = open_ledger(args)
    try:
        events = ledger.events(run_id=args.run_id)
    finally:
        ledger.close()

    if args.json:
        emit_json([event.to_json_dict() for event in events])
        return 0

    # JSONL is the export format (D19): one canonical event per line, in append order. It is
    # never the write path; SQLite transactions are.
    text = "".join(f"{event.canonical_json()}\n" for event in events)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        emit(f"exported {len(events)} events to {target}")
        return 0
    sys.stdout.write(text)
    return 0


# ---------------------------------------------------------------------------
# compile (M3.2): the evidence-lineage gate
# ---------------------------------------------------------------------------


def _git_ancestry_check(worktree: Path) -> Any:
    """Return an ancestry check backed by real git, or None if this is not a git worktree.

    The check answers "is `commit` an ancestor of, or equal to, the current HEAD". Any git
    failure (an unknown commit, a detached state) is read as NOT an ancestor, because an
    unverifiable commit is exactly the drift C006 exists to catch.
    """
    import subprocess

    try:
        inside = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
    except (OSError, ValueError):
        return None
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None

    def check(commit: str) -> bool:
        if not commit:
            return True  # an empty commit is "not recorded", not a drift
        result = subprocess.run(
            ["git", "-C", str(worktree), "merge-base", "--is-ancestor", commit, "HEAD"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    return check


def _status_checker_from_recheck(args: argparse.Namespace, dois: Sequence[str]) -> Any:
    """Build a compile status checker by re-running axis (b) over the edge source DOIs.

    Offline by default (replays snapshots via build_session); a DOI whose status could not be
    checked (a source error) maps to a StatusCheck with source_error set, which the compiler
    turns into an inconclusive line item, never a defect (D9).
    """
    from .lineage.compile import StatusCheck

    if not dois:
        return None
    report = check_status(
        list(dict.fromkeys(dois)),
        sources=DEFAULT_STATUS_SOURCES,
        snapshots=build_session(args),
        input_kind="doi",
    )
    by_doi: dict[str, StatusCheck] = {}
    for entry in report.get("entries", []):
        doi = normalize_doi(entry.get("doi") or entry.get("id") or "")
        if not doi:
            continue
        by_doi[doi] = StatusCheck(
            verdict=entry.get("verdict") if entry.get("checked") else None,
            source_error=not entry.get("checked", False),
        )

    def checker(doi: str) -> StatusCheck:
        return by_doi.get(normalize_doi(doi), StatusCheck(source_error=True))

    return checker


def cmd_compile(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from .lineage.compile import (
        compile_graph,
        default_artifact_hasher,
        gate_event_payload,
    )
    from .lineage.graph import LineageGraph
    from .provenance import load_jsonl

    manuscript = Path(args.manuscript)
    if not manuscript.is_dir():
        raise CLIError(
            f"{manuscript} is not a directory. Point --manuscript at a manuscript folder."
        )
    lineage_path = Path(args.lineage) if args.lineage else manuscript / "lineage" / "graph.jsonl"
    if not lineage_path.is_file():
        raise CLIError(
            f"No lineage graph at {lineage_path}. Record claim nodes and evidence edges first "
            "(the graph is a stream of record_lineage events)."
        )

    events = load_jsonl(lineage_path)
    graph = LineageGraph.from_events(events)

    status_checker = None
    if args.recheck_status:
        dois = [e.source_doi for e in graph.edges if e.source_doi]
        status_checker = _status_checker_from_recheck(args, dois)

    report = compile_graph(
        graph,
        status_checker=status_checker,
        artifact_hasher=default_artifact_hasher(manuscript),
        ancestry_check=_git_ancestry_check(manuscript),
        ts=args.ts or "",
    )

    # Append the gate event to the ledger so the derived gate state (D19) reflects this run.
    # ts is caller-supplied; without one, the gate event is not written (a compile stays a pure
    # read), which keeps a no-ts run replayable and side-effect-free.
    if args.ts:
        ledger = open_ledger(args)
        try:
            ledger.append(
                ProvenanceEvent(
                    run_id=args.run_id or "compile",
                    type="gate",
                    ts=args.ts,
                    payload=gate_event_payload(report),
                )
            )
        except ProvenanceError as exc:
            raise CLIError(str(exc)) from exc
        finally:
            ledger.close()

    if args.json:
        emit_json(report.to_json_dict())
    else:
        emit(report.to_human())
    return 0 if report.passed else 1


# ---------------------------------------------------------------------------
# The parser
# ---------------------------------------------------------------------------


def _common(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """The two flags every command carries, per the plan's CLI surface table."""
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (validated against core/schemas/) "
        "instead of the human table.",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Make live calls and capture every response as a snapshot (D15).",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Deterministic multi-source literature retrieval and per-axis citation "
            "verification. Every command takes --json (machine output) and --record "
            "(live calls with snapshot capture)."
        ),
        epilog=(
            "Verdict vocabularies: axis (a) identity verified/mismatch/unresolvable/"
            "inconclusive (only the first two are ever refusal-grade); axis (b) status "
            "current/corrected/retracted/expression-of-concern; axis (c) faithfulness "
            "supported/partial/contradicted/insufficient-passage; axis (d) accessibility "
            "full-text/abstract-only/unavailable. See references/core-cli.md."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROG} {__version__} (parser {PARSER_VERSION}, protocol {PROTOCOL_VERSION})",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # -- search ------------------------------------------------------------
    search = _common(
        subparsers.add_parser(
            "search",
            help="Fan out across sources, dedupe, rank; returns CSL-JSON records.",
        )
    )
    search.add_argument("query", help="Free-text query.")
    search.add_argument(
        "--sources",
        help=f"Comma-separated source names. Default: {','.join(DEFAULT_SEARCH_SOURCES)}.",
    )
    search.add_argument("--limit", type=int, default=25, help="Records per source (default 25).")
    search.add_argument("--since", type=int, help="Only works published in this year or later.")
    search.set_defaults(func=cmd_search, cmd_parser=search)

    # -- get ---------------------------------------------------------------
    get = _common(
        subparsers.add_parser("get", help="One normalized record by DOI, arXiv ID, or OpenAlex ID.")
    )
    get.add_argument("identifier", help="DOI, arXiv ID, or OpenAlex work ID.")
    get.add_argument(
        "--sources",
        help=f"Comma-separated source names. Default: {','.join(DEFAULT_SEARCH_SOURCES)}.",
    )
    get.set_defaults(func=cmd_get, cmd_parser=get)

    # -- verify-bib --------------------------------------------------------
    verify_bib = _common(
        subparsers.add_parser(
            "verify-bib",
            help="Per-entry axis (a) identity with per-source outcomes, plus axis (b) and (d).",
        )
    )
    verify_bib.add_argument("path", help="Path to a .bib file.")
    verify_bib.add_argument(
        "--sources",
        help=f"Comma-separated source names. Default: {','.join(DEFAULT_VERIFY_SOURCES)}.",
    )
    verify_bib.add_argument("--run-id", help="Run identifier to stamp on the report.")
    verify_bib.set_defaults(func=cmd_verify_bib, cmd_parser=verify_bib)

    # -- verify-ref --------------------------------------------------------
    verify_ref = _common(
        subparsers.add_parser("verify-ref", help="The same report for one reference.")
    )
    verify_ref.add_argument("reference", help="A DOI or a title.")
    verify_ref.add_argument(
        "--sources",
        help=f"Comma-separated source names. Default: {','.join(DEFAULT_VERIFY_SOURCES)}.",
    )
    verify_ref.add_argument("--run-id", help="Run identifier to stamp on the report.")
    verify_ref.set_defaults(func=cmd_verify_ref, cmd_parser=verify_ref)

    # -- status ------------------------------------------------------------
    status = _common(
        subparsers.add_parser(
            "status",
            help="Axis (b) sweep: current / corrected / retracted / expression-of-concern.",
        )
    )
    status.add_argument("target", help="A DOI or a path to a .bib file.")
    status.add_argument(
        "--sources",
        help=f"Comma-separated source names. Default: {','.join(DEFAULT_STATUS_SOURCES)}.",
    )
    status.add_argument("--run-id", help="Run identifier to stamp on the report.")
    status.set_defaults(func=cmd_status, cmd_parser=status)

    # -- citations / references --------------------------------------------
    citations = _common(
        subparsers.add_parser("citations", help="Forward citations: works that cite this one.")
    )
    citations.add_argument("identifier", help="DOI, arXiv ID, or OpenAlex work ID.")
    citations.add_argument(
        "--depth", type=int, default=1, help=f"Hops to traverse, 1 to {MAX_DEPTH} (default 1)."
    )
    citations.add_argument("--limit", type=int, default=100, help="Neighbors per node per source.")
    citations.add_argument(
        "--sources",
        help=f"Comma-separated source names. Default: {','.join(DEFAULT_GRAPH_SOURCES)}.",
    )
    citations.set_defaults(func=cmd_citations, cmd_parser=citations)

    references = _common(
        subparsers.add_parser("references", help="Backward references: works this one cites.")
    )
    references.add_argument("identifier", help="DOI, arXiv ID, or OpenAlex work ID.")
    references.add_argument(
        "--depth", type=int, default=1, help=f"Hops to traverse, 1 to {MAX_DEPTH} (default 1)."
    )
    references.add_argument("--limit", type=int, default=100, help="Neighbors per node per source.")
    references.add_argument(
        "--sources",
        help=f"Comma-separated source names. Default: {','.join(DEFAULT_GRAPH_SOURCES)}.",
    )
    references.set_defaults(func=cmd_references, cmd_parser=references)

    # -- oa-pdf ------------------------------------------------------------
    oa_pdf = _common(
        subparsers.add_parser(
            "oa-pdf", help="OA location cascade: Unpaywall, then arXiv, then PMC."
        )
    )
    oa_pdf.add_argument("doi", help="A DOI.")
    oa_pdf.set_defaults(func=cmd_oa_pdf, cmd_parser=oa_pdf)

    # -- fulltext ----------------------------------------------------------
    fulltext = _common(
        subparsers.add_parser(
            "fulltext",
            help="Resolve an OA copy, extract text, split into sections. PDFs need [fulltext].",
        )
    )
    fulltext.add_argument("identifier", help="A DOI, an arXiv ID, or a direct OA URL.")
    fulltext.add_argument(
        "--sections",
        action="store_true",
        help="Print the per-section table. (--json always carries the sections.)",
    )
    fulltext.set_defaults(func=cmd_fulltext, cmd_parser=fulltext)

    # -- passages ----------------------------------------------------------
    passages = subparsers.add_parser(
        "passages", help="The D21 passage index: extract, index, and BM25-search passages."
    )
    passage_subs = passages.add_subparsers(dest="passages_command", metavar="SUBCOMMAND")

    passages_index = _common(
        passage_subs.add_parser(
            "index", help="Extract a document and index it with stable passage IDs."
        )
    )
    passages_index.add_argument("identifier", help="A DOI, an arXiv ID, or a direct OA URL.")
    passages_index.add_argument("--db", help="Passage index path (default: the user cache dir).")
    passages_index.set_defaults(func=cmd_passages_index, cmd_parser=passages_index)

    passages_search = _common(
        passage_subs.add_parser("search", help="BM25-ranked passages with IDs, offsets, pages.")
    )
    passages_search.add_argument("query", help="Free-text query.")
    passages_search.add_argument("--doc", help="Restrict the search to one indexed document.")
    passages_search.add_argument("--limit", type=int, default=10, help="Passages to return.")
    passages_search.add_argument("--db", help="Passage index path (default: the user cache dir).")
    passages_search.set_defaults(func=cmd_passages_search, cmd_parser=passages_search)

    passages.set_defaults(
        func=_require_subcommand(passages, "passages"), cmd_parser=passages
    )

    # -- faithfulness ------------------------------------------------------
    faithfulness = _common(
        subparsers.add_parser(
            "faithfulness", help="Axis (c) verdict for one claim, anchored on passage IDs."
        )
    )
    faithfulness.add_argument("claim", help="The claim to check.")
    faithfulness.add_argument("--doc", required=True, help="The indexed document to check against.")
    faithfulness.add_argument("--db", help="Passage index path (default: the user cache dir).")
    faithfulness.add_argument("--top-k", type=int, default=8, help="Candidate passages to score.")
    faithfulness.add_argument("--run-id", help="Run identifier to stamp on the report.")
    faithfulness.set_defaults(func=cmd_faithfulness, cmd_parser=faithfulness)

    # -- snapshot ----------------------------------------------------------
    snapshot = subparsers.add_parser(
        "snapshot", help="Capture, replay, and diff content-addressed API responses (D15)."
    )
    snapshot_subs = snapshot.add_subparsers(dest="snapshot_command", metavar="SUBCOMMAND")

    snap_record = _common(
        snapshot_subs.add_parser("record", help="Call a source live and store the response.")
    )
    snap_record.add_argument("source", help="Connector name.")
    snap_record.add_argument(
        "endpoint", help="Endpoint path, parameter-free (for example 'works')."
    )
    snap_record.add_argument(
        "-p", "--param", action="append", metavar="KEY=VALUE", help="Request parameter."
    )
    snap_record.add_argument("--store", help="Snapshot store root (default: the eval store).")
    snap_record.add_argument(
        "--retrieved-at", help="Pin the retrieved_at timestamp, so a re-record is byte-stable."
    )
    snap_record.set_defaults(func=cmd_snapshot_record, cmd_parser=snap_record)

    snap_replay = _common(
        snapshot_subs.add_parser(
            "replay", help="Read one stored snapshot, or the whole request set, verifying hashes."
        )
    )
    snap_replay.add_argument("source", nargs="?", help="Connector name.")
    snap_replay.add_argument("endpoint", nargs="?", help="Endpoint path.")
    snap_replay.add_argument(
        "-p", "--param", action="append", metavar="KEY=VALUE", help="Request parameter."
    )
    snap_replay.add_argument("--store", help="Snapshot store root.")
    snap_replay.set_defaults(func=cmd_snapshot_replay, cmd_parser=snap_replay)

    snap_diff = _common(
        snapshot_subs.add_parser(
            "diff", help="Drift report: a stored snapshot against the live response."
        )
    )
    snap_diff.add_argument("source", nargs="?", help="Connector name.")
    snap_diff.add_argument("endpoint", nargs="?", help="Endpoint path.")
    snap_diff.add_argument(
        "-p", "--param", action="append", metavar="KEY=VALUE", help="Request parameter."
    )
    snap_diff.add_argument("--store", help="Snapshot store root.")
    snap_diff.add_argument(
        "--all", action="store_true", help="Diff every stored snapshot against the live API."
    )
    snap_diff.add_argument(
        "--live-from",
        metavar="FILE",
        help="Diff against a live-shaped response body read from a JSON file, not the network.",
    )
    snap_diff.set_defaults(func=cmd_snapshot_diff, cmd_parser=snap_diff)

    snapshot.set_defaults(
        func=_require_subcommand(snapshot, "snapshot"), cmd_parser=snapshot
    )

    # -- provenance --------------------------------------------------------
    provenance = subparsers.add_parser(
        "provenance", help="The append-only event ledger (D19) and the PRISMA counts it derives."
    )
    provenance_subs = provenance.add_subparsers(dest="provenance_command", metavar="SUBCOMMAND")

    prov_append = _common(
        provenance_subs.add_parser("append", help="Append one event, in a SQLite transaction.")
    )
    prov_append.add_argument(
        "event", help="The event as inline JSON, a path to a JSON file, or '-' for stdin."
    )
    prov_append.add_argument("--ledger", help="Ledger path (default: the user cache dir).")
    prov_append.set_defaults(func=cmd_provenance_append, cmd_parser=prov_append)

    prov_prisma = _common(
        provenance_subs.add_parser("prisma", help="Derive PRISMA flow counts by aggregation.")
    )
    prov_prisma.add_argument("--run-id", help="Restrict to one run.")
    prov_prisma.add_argument("--ledger", help="Ledger path (default: the user cache dir).")
    prov_prisma.set_defaults(func=cmd_provenance_prisma, cmd_parser=prov_prisma)

    prov_export = _common(
        provenance_subs.add_parser("export", help="Export the ledger as JSONL (the export format).")
    )
    prov_export.add_argument("--run-id", help="Restrict to one run.")
    prov_export.add_argument("--out", help="Write to this file instead of stdout.")
    prov_export.add_argument("--ledger", help="Ledger path (default: the user cache dir).")
    prov_export.set_defaults(func=cmd_provenance_export, cmd_parser=prov_export)

    provenance.set_defaults(
        func=_require_subcommand(provenance, "provenance"), cmd_parser=provenance
    )

    # -- compile (M3.2) ----------------------------------------------------
    compile_cmd = _common(
        subparsers.add_parser(
            "compile",
            help="The evidence-lineage gate: check every claim compiles from clean evidence.",
        )
    )
    compile_cmd.add_argument(
        "--manuscript",
        default="manuscript",
        help="The manuscript folder to compile (default: manuscript/).",
    )
    compile_cmd.add_argument(
        "--lineage",
        help="Path to the lineage graph (default: <manuscript>/lineage/graph.jsonl).",
    )
    compile_cmd.add_argument(
        "--recheck-status",
        action="store_true",
        help="Re-run publication status over cited sources (offline via snapshots). A source "
        "error becomes an inconclusive line item, never a defect (D9).",
    )
    compile_cmd.add_argument("--store", help="Snapshot store root for the status re-check.")
    compile_cmd.add_argument(
        "--ts",
        help="Caller-supplied timestamp (D19). When given, a gate event is appended to the "
        "ledger; without it, compile is a pure read.",
    )
    compile_cmd.add_argument("--run-id", help="Run id for the gate event.")
    compile_cmd.add_argument("--ledger", help="Ledger path (default: the user cache dir).")
    compile_cmd.set_defaults(func=cmd_compile, cmd_parser=compile_cmd)

    return parser


def _require_subcommand(parser: argparse.ArgumentParser, name: str) -> Any:
    """A command group invoked with no subcommand is an argument error, not a silent no-op."""

    def handler(_args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
        parser.error(f"{name} needs a subcommand")
        return 2  # pragma: no cover - parser.error raises SystemExit(2)

    return handler


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    configure_streams()
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    # Argument errors are reported by the subparser that owns them, so `--sources nope` on
    # `search` prints the usage line for `search`, not for the whole program.
    owner: argparse.ArgumentParser = getattr(args, "cmd_parser", parser)

    try:
        return int(args.func(args, owner))
    except SnapshotMissingError as exc:
        # Never degraded into a source error: a hole in the snapshot set is a defect in the
        # fixtures, not an outage, and replay never falls through to a live call.
        sys.stderr.write(f"error: {exc}\n")
        return 1
    except (CLIError, SnapshotError, SourceError, MissingExtraError, FullTextError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    except ProvenanceError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    except BrokenPipeError:  # pragma: no cover - `| head` on a long report
        return 0
    except KeyboardInterrupt:  # pragma: no cover
        sys.stderr.write("interrupted\n")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
