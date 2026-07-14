"""The minimal passage index: stable IDs, content hashes, SQLite FTS5 with BM25 (M2.9, D21).

This is what axis (c) anchors on. A faithfulness verdict is worthless if it cannot point at
the exact text that justified it, so every verdict carries a passage ID, and a passage ID is
a stable function of what was actually extracted:

    passage_id = sha256(doc_hash + section_path + char_start + char_end + parser_version)

The consequences, all of them intended:

* **Stable across machines and across re-extraction.** The same document bytes under the same
  parser version yield the same IDs on Windows and Linux, today and next year. An ID recorded
  in a manuscript's evidence ledger still resolves after a re-index.
* **A parser upgrade changes every ID.** That is the point (D15): a verdict is replayable only
  under a stated parser version, so a changed parser invalidates the derived IDs rather than
  silently repointing them at different text.
* **Two hashes, both stored.** ``doc_hash`` over the whole extracted canonical text, and
  ``passage_hash`` over the passage's own text. When a source PDF is re-fetched and differs,
  the document hash moves, every passage ID moves with it, and stale evidence is detectable
  (the query the M3 compile gate needs).

Storage is stdlib :mod:`sqlite3` with an FTS5 virtual table over the passage text, ranked by
BM25. No new dependency: FTS5 ships compiled into the SQLite that CPython bundles on Windows,
macOS, and Linux. It is checked at open time anyway (:func:`fts5_available`), because a
kernel that silently degrades its retrieval is worse than one that says it cannot run.

Every passage validates against ``core/schemas/passage.schema.json``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import user_cache_root
from .fulltext import (
    FULL_TEXT,
    PARSER_VERSION,
    ExtractedDocument,
    PageRect,
    TextSegment,
)
from .model import canonical_json, sha256_hex

__all__ = [
    "DEFAULT_DB_NAME",
    "PARSER_VERSION",
    "IndexedDocument",
    "Passage",
    "PassageIndex",
    "PassageIndexError",
    "compute_passage_id",
    "fts5_available",
    "match_query",
    "passages_from_document",
    "tokenize",
]

DEFAULT_DB_NAME = "passages.sqlite3"

#: Tokens dropped from an FTS5 MATCH query and from overlap scoring. Deliberately short: BM25
#: already downweights frequent terms, and an over-eager stoplist throws away the negations
#: and qualifiers that axis (c) needs.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
)


class PassageIndexError(RuntimeError):
    """The passage index cannot do what was asked of it."""


# ---------------------------------------------------------------------------
# FTS5 availability
# ---------------------------------------------------------------------------


def fts5_available() -> bool:
    """True when the bundled SQLite has FTS5 compiled in.

    Checked rather than assumed. The plan flags this as a Windows risk; it is verified here
    at runtime and in the test suite, so an environment without FTS5 fails loudly at open
    time with an actionable message instead of producing a mysteriously empty search.
    """
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE VIRTUAL TABLE _fts5_probe USING fts5(text)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------


def tokenize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    """Lowercase word and number tokens, in order. The one tokenizer the kernel scores with."""
    tokens: list[str] = []
    current: list[str] = []
    for char in str(text).casefold():
        if char.isalnum() or char in {".", "-", "_"} and current:
            current.append(char)
        else:
            if current:
                tokens.append("".join(current).strip(".-_"))
                current = []
    if current:
        tokens.append("".join(current).strip(".-_"))
    return [
        token
        for token in tokens
        if token and (keep_stopwords or token not in STOPWORDS)
    ]


def match_query(text: str) -> str:
    """Turn free text into an FTS5 MATCH expression: quoted tokens joined by ``OR``.

    Quoting every token is what keeps a claim containing ``(p < 0.05)`` or a hyphenated term
    from being read as FTS5 query syntax and raising instead of searching.
    """
    tokens = [t for t in tokenize(text) if len(t) > 1]
    if not tokens:
        tokens = [t for t in tokenize(text, keep_stopwords=True) if t]
    if not tokens:
        return ""
    unique = list(dict.fromkeys(tokens))
    return " OR ".join(f'"{token}"' for token in unique)


# ---------------------------------------------------------------------------
# Passage identity
# ---------------------------------------------------------------------------


def compute_passage_id(
    doc_hash: str,
    section_path: str,
    char_start: int,
    char_end: int,
    parser_version: str = PARSER_VERSION,
) -> str:
    """The D21 passage ID: ``hash(doc hash + section path + char offsets + parser version)``.

    Hashed over the canonical JSON of the five inputs, so the field separator can never be
    ambiguous (a section path containing the delimiter cannot collide with a different one).
    """
    return sha256_hex(
        canonical_json(
            {
                "doc_hash": str(doc_hash),
                "section_path": str(section_path),
                "char_start": int(char_start),
                "char_end": int(char_end),
                "parser_version": str(parser_version),
            }
        )
    )


@dataclass(frozen=True)
class Passage:
    """One indexed passage. Validates against ``core/schemas/passage.schema.json``."""

    passage_id: str
    doc_hash: str
    section_path: str
    char_start: int
    char_end: int
    passage_hash: str
    text: str
    page_coords: list[PageRect] = field(default_factory=list)
    doc_id: str = ""
    parser_version: str = PARSER_VERSION
    ordinal: int = 0
    bm25_score: float | None = None

    @classmethod
    def from_segment(
        cls,
        segment: TextSegment,
        *,
        doc_hash: str,
        doc_id: str = "",
        parser_version: str = PARSER_VERSION,
    ) -> Passage:
        return cls(
            passage_id=compute_passage_id(
                doc_hash,
                segment.section_path,
                segment.char_start,
                segment.char_end,
                parser_version,
            ),
            doc_hash=doc_hash,
            section_path=segment.section_path,
            char_start=segment.char_start,
            char_end=segment.char_end,
            passage_hash=sha256_hex(segment.text),
            text=segment.text,
            page_coords=list(segment.page_coords),
            doc_id=doc_id,
            parser_version=parser_version,
            ordinal=segment.ordinal,
        )

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "passage_id": self.passage_id,
            "doc_hash": self.doc_hash,
            "passage_hash": self.passage_hash,
            "section_path": self.section_path,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "page_coords": [r.to_json_dict() for r in self.page_coords] or None,
            "text": self.text,
            "doc_id": self.doc_id,
            "parser_version": self.parser_version,
            "ordinal": self.ordinal,
        }
        if self.bm25_score is not None:
            out["bm25_score"] = self.bm25_score
        return out

    def anchor_dict(self) -> dict[str, Any]:
        """The passage-anchor shape the faithfulness report embeds."""
        return {
            "passage_id": self.passage_id,
            "passage_hash": self.passage_hash,
            "doc_hash": self.doc_hash,
            "section_path": self.section_path,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "page_coords": [r.to_json_dict() for r in self.page_coords] or None,
            "bm25_score": self.bm25_score,
            "text": self.text,
        }


@dataclass(frozen=True)
class IndexedDocument:
    """The per-document row: what was indexed, how deep the evidence went, under which parser."""

    doc_id: str
    doc_hash: str
    accessibility: str
    parser_version: str
    doi: str = ""
    url: str = ""
    content_type: str = ""
    abstract: str = ""
    passage_count: int = 0
    source_response_hashes: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doi": self.doi or None,
            "doc_hash": self.doc_hash,
            "accessibility": self.accessibility,
            "parser_version": self.parser_version,
            "passage_count": self.passage_count,
            "source_response_hashes": list(self.source_response_hashes),
        }


def passages_from_document(document: ExtractedDocument) -> list[Passage]:
    """Passages for an extracted document. Empty unless axis (d) is ``full-text``.

    An ``abstract-only`` or ``unavailable`` document has no extracted bytes, so it has no
    passages. There is no path here that manufactures one.
    """
    if document.accessibility != FULL_TEXT:
        return []
    doc_hash = document.doc_hash
    return [
        Passage.from_segment(
            segment,
            doc_hash=doc_hash,
            doc_id=document.doc_id,
            parser_version=document.parser_version,
        )
        for segment in document.segments
    ]


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id                TEXT PRIMARY KEY,
    doc_hash              TEXT NOT NULL,
    doi                   TEXT NOT NULL DEFAULT '',
    url                   TEXT NOT NULL DEFAULT '',
    content_type          TEXT NOT NULL DEFAULT '',
    accessibility         TEXT NOT NULL,
    parser_version        TEXT NOT NULL,
    abstract              TEXT NOT NULL DEFAULT '',
    passage_count         INTEGER NOT NULL DEFAULT 0,
    source_response_hashes TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS passages (
    passage_id     TEXT PRIMARY KEY,
    doc_id         TEXT NOT NULL,
    doc_hash       TEXT NOT NULL,
    section_path   TEXT NOT NULL,
    char_start     INTEGER NOT NULL,
    char_end       INTEGER NOT NULL,
    page_coords    TEXT,
    passage_hash   TEXT NOT NULL,
    text           TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    ordinal        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS passages_doc_idx ON passages(doc_id, ordinal);
CREATE INDEX IF NOT EXISTS passages_hash_idx ON passages(doc_hash);

CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
    text,
    passage_id UNINDEXED,
    doc_id UNINDEXED,
    tokenize = 'unicode61'
);
"""


class PassageIndex:
    """A SQLite passage store with an FTS5 BM25 index over the passage text.

    Use it as a context manager, or call :meth:`close`. The default database lives in the
    platformdirs user cache directory (Windows-safe per D5); pass ``":memory:"`` for a
    throwaway index and a path for anything else.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        if not fts5_available():
            raise PassageIndexError(
                "This Python's bundled SQLite has no FTS5 module, so BM25 passage search "
                "cannot run. FTS5 ships in the standard CPython builds on Windows, macOS, "
                "and Linux; a Python built against a custom SQLite without "
                "-DSQLITE_ENABLE_FTS5 is the usual cause."
            )
        if path is None:
            path = user_cache_root() / DEFAULT_DB_NAME
        self.path = Path(path) if str(path) != ":memory:" else Path(":memory:")
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(_SCHEMA)
        self.connection.commit()

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> PassageIndex:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- writes ------------------------------------------------------------

    def index_document(self, document: ExtractedDocument) -> list[Passage]:
        """Index an extracted document, replacing any previous version of it.

        Re-indexing the same bytes under the same parser version is idempotent: the passage
        IDs are recomputed to exactly the same values (that is the D21 guarantee, and the
        test suite asserts it), so nothing downstream that stored an ID goes stale.

        A document that is not ``full-text`` is still recorded, with zero passages, because
        the axis (d) verdict is itself evidence: it is what tells the faithfulness layer to
        abstain with ``insufficient-passage`` rather than pretend it looked.
        """
        passages = passages_from_document(document)
        record = IndexedDocument(
            doc_id=document.doc_id,
            doc_hash=document.doc_hash,
            accessibility=document.accessibility,
            parser_version=document.parser_version,
            doi=document.doi,
            url=document.url,
            content_type=document.content_type,
            abstract=document.abstract,
            passage_count=len(passages),
            source_response_hashes=list(document.source_response_hashes),
        )
        with self.connection:  # one transaction: a half-indexed document never exists
            self._delete_document(document.doc_id)
            self.connection.execute(
                """
                INSERT INTO documents (
                    doc_id, doc_hash, doi, url, content_type, accessibility,
                    parser_version, abstract, passage_count, source_response_hashes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.doc_id,
                    record.doc_hash,
                    record.doi,
                    record.url,
                    record.content_type,
                    record.accessibility,
                    record.parser_version,
                    record.abstract,
                    record.passage_count,
                    json.dumps(record.source_response_hashes),
                ),
            )
            self.connection.executemany(
                """
                INSERT INTO passages (
                    passage_id, doc_id, doc_hash, section_path, char_start, char_end,
                    page_coords, passage_hash, text, parser_version, ordinal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        p.passage_id,
                        p.doc_id,
                        p.doc_hash,
                        p.section_path,
                        p.char_start,
                        p.char_end,
                        json.dumps([r.to_json_dict() for r in p.page_coords]),
                        p.passage_hash,
                        p.text,
                        p.parser_version,
                        p.ordinal,
                    )
                    for p in passages
                ],
            )
            self.connection.executemany(
                "INSERT INTO passages_fts (text, passage_id, doc_id) VALUES (?, ?, ?)",
                [(p.text, p.passage_id, p.doc_id) for p in passages],
            )
        return passages

    def delete_document(self, doc_id: str) -> None:
        with self.connection:
            self._delete_document(doc_id)

    def _delete_document(self, doc_id: str) -> None:
        self.connection.execute("DELETE FROM passages_fts WHERE doc_id = ?", (doc_id,))
        self.connection.execute("DELETE FROM passages WHERE doc_id = ?", (doc_id,))
        self.connection.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))

    # -- reads -------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        doc_id: str | None = None,
        limit: int = 10,
    ) -> list[Passage]:
        """BM25-ranked passages for a free-text query, best match first.

        ``bm25_score`` is SQLite's raw FTS5 value: more negative is a better match, and the
        numbers are comparable only within one query. An empty result is an honest "nothing
        matched", never an error.
        """
        expression = match_query(query)
        if not expression:
            return []
        sql = [
            "SELECT p.*, bm25(passages_fts) AS score",
            "FROM passages_fts",
            "JOIN passages p ON p.passage_id = passages_fts.passage_id",
            "WHERE passages_fts MATCH ?",
        ]
        params: list[Any] = [expression]
        if doc_id:
            sql.append("AND passages_fts.doc_id = ?")
            params.append(doc_id)
        sql.append("ORDER BY score ASC, p.ordinal ASC")
        sql.append("LIMIT ?")
        params.append(int(limit))
        try:
            rows = self.connection.execute(" ".join(sql), params).fetchall()
        except sqlite3.OperationalError as exc:  # pragma: no cover - malformed MATCH guard
            raise PassageIndexError(f"FTS5 rejected the query {expression!r}: {exc}") from exc
        return [_row_to_passage(row, score=row["score"]) for row in rows]

    def get_passage(self, passage_id: str) -> Passage | None:
        row = self.connection.execute(
            "SELECT * FROM passages WHERE passage_id = ?", (passage_id,)
        ).fetchone()
        return _row_to_passage(row) if row is not None else None

    def passages(self, doc_id: str) -> list[Passage]:
        rows = self.connection.execute(
            "SELECT * FROM passages WHERE doc_id = ? ORDER BY ordinal ASC", (doc_id,)
        ).fetchall()
        return [_row_to_passage(row) for row in rows]

    def get_document(self, doc_id: str) -> IndexedDocument | None:
        row = self.connection.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            return None
        return IndexedDocument(
            doc_id=row["doc_id"],
            doc_hash=row["doc_hash"],
            accessibility=row["accessibility"],
            parser_version=row["parser_version"],
            doi=row["doi"],
            url=row["url"],
            content_type=row["content_type"],
            abstract=row["abstract"],
            passage_count=int(row["passage_count"]),
            source_response_hashes=_json_list(row["source_response_hashes"]),
        )

    def documents(self) -> list[IndexedDocument]:
        rows = self.connection.execute("SELECT doc_id FROM documents ORDER BY doc_id").fetchall()
        out: list[IndexedDocument] = []
        for row in rows:
            document = self.get_document(row["doc_id"])
            if document is not None:
                out.append(document)
        return out

    def count(self, doc_id: str | None = None) -> int:
        if doc_id:
            row = self.connection.execute(
                "SELECT COUNT(*) AS n FROM passages WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        else:
            row = self.connection.execute("SELECT COUNT(*) AS n FROM passages").fetchone()
        return int(row["n"])


def _row_to_passage(row: Mapping[str, Any] | sqlite3.Row, *, score: float | None = None) -> Passage:
    coords = _json_list(row["page_coords"])
    return Passage(
        passage_id=row["passage_id"],
        doc_hash=row["doc_hash"],
        section_path=row["section_path"],
        char_start=int(row["char_start"]),
        char_end=int(row["char_end"]),
        passage_hash=row["passage_hash"],
        text=row["text"],
        page_coords=[PageRect.from_json_dict(c) for c in coords],
        doc_id=row["doc_id"],
        parser_version=row["parser_version"],
        ordinal=int(row["ordinal"]),
        bm25_score=score,
    )


def _json_list(raw: Any) -> list[Any]:
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return list(value) if isinstance(value, Iterable) and not isinstance(value, str) else []


def index_documents(
    documents: Sequence[ExtractedDocument], *, path: Path | str | None = None
) -> PassageIndex:
    """Open an index and index every document in ``documents``. Convenience for the CLI."""
    index = PassageIndex(path)
    for document in documents:
        index.index_document(document)
    return index
