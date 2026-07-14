"""The D21 passage index: stable IDs, both content hashes, FTS5 BM25 (M2.9).

Offline by construction: every document here is built from in-memory blocks, so nothing
touches the network and nothing needs the ``[fulltext]`` extra (PDF page coordinates are
exercised by handing the builder blocks that carry rectangles, which is exactly the shape
PyMuPDF produces).

The three properties D21 exists for, each asserted directly:

1. Indexing the same document twice yields identical passage IDs.
2. Changing the parser version changes every ID, on purpose.
3. Changing the document bytes changes every ID, so stale evidence is detectable.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from researcher_core.fulltext import (
    ABSTRACT_ONLY,
    FULL_TEXT,
    PARSER_VERSION,
    UNAVAILABLE,
    ExtractedDocument,
    PageRect,
    TextBlock,
    build_document,
)
from researcher_core.passages import (
    PassageIndex,
    PassageIndexError,
    compute_passage_id,
    fts5_available,
    match_query,
    passages_from_document,
    tokenize,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "passage.schema.json"

DOC_ID = "10.7717/peerj.4375"


def blocks_with_pages() -> list[TextBlock]:
    """Blocks shaped exactly as :func:`pdf_to_blocks` returns them, rectangles and all."""
    return [
        TextBlock(text="Abstract", page=1, rect=PageRect(1, 72, 60, 200, 74)),
        TextBlock(
            text="We evaluate a self-supervised model on twelve-lead ECG data from 4200 patients.",
            page=1,
            rect=PageRect(1, 72, 90, 540, 130),
        ),
        TextBlock(text="2. Methods", page=1, rect=PageRect(1, 72, 160, 200, 174)),
        TextBlock(
            text="We pretrained the encoder on unlabeled recordings and fine-tuned on 500 labels.",
            page=1,
            rect=PageRect(1, 72, 190, 540, 230),
        ),
        TextBlock(text="3. Results", page=2, rect=PageRect(2, 72, 60, 200, 74)),
        TextBlock(
            text=(
                "The self-supervised model reached an accuracy of 0.91, which exceeded the "
                "supervised baseline by a wide margin on the held-out test set."
            ),
            page=2,
            rect=PageRect(2, 72, 90, 540, 140),
        ),
    ]


def full_text_document(parser_version: str = PARSER_VERSION) -> ExtractedDocument:
    return build_document(
        blocks_with_pages(),
        doc_id=DOC_ID,
        doi=DOC_ID,
        url="https://example.org/oa/paper.pdf",
        content_type="pdf",
        source="unpaywall",
        source_response_hashes=["a" * 64],
        parser_version=parser_version,
    )


@pytest.fixture()
def index() -> Any:
    with PassageIndex(":memory:") as instance:
        yield instance


# ---------------------------------------------------------------------------
# FTS5 availability: the Windows risk the plan flags, checked rather than assumed
# ---------------------------------------------------------------------------


def test_fts5_is_compiled_into_this_python() -> None:
    assert fts5_available() is True, (
        "This Python's SQLite has no FTS5, so BM25 passage search cannot run. "
        f"sqlite3 {sqlite3.sqlite_version}"
    )


def test_the_index_refuses_to_open_without_fts5(monkeypatch: pytest.MonkeyPatch) -> None:
    """A kernel that silently degrades its retrieval is worse than one that says it cannot run."""
    monkeypatch.setattr("researcher_core.passages.fts5_available", lambda: False)
    with pytest.raises(PassageIndexError, match="FTS5"):
        PassageIndex(":memory:")


# ---------------------------------------------------------------------------
# Passage identity
# ---------------------------------------------------------------------------


def test_indexing_the_same_document_twice_yields_identical_passage_ids(index: PassageIndex) -> None:
    first = index.index_document(full_text_document())
    second = index.index_document(full_text_document())

    assert first
    assert [p.passage_id for p in first] == [p.passage_id for p in second]
    assert [p.passage_hash for p in first] == [p.passage_hash for p in second]
    # Re-indexing replaces rather than duplicates.
    assert index.count(DOC_ID) == len(first)


def test_changing_the_parser_version_changes_every_passage_id() -> None:
    baseline = passages_from_document(full_text_document())
    upgraded = passages_from_document(full_text_document(parser_version="2.0"))

    assert len(baseline) == len(upgraded)
    assert {p.passage_id for p in baseline}.isdisjoint({p.passage_id for p in upgraded})
    # The text did not change, so the per-passage content hashes did not either. Only the IDs
    # moved, which is precisely what makes a verdict replayable per D15.
    assert [p.passage_hash for p in baseline] == [p.passage_hash for p in upgraded]


def test_changing_the_document_text_changes_every_passage_id() -> None:
    baseline = passages_from_document(full_text_document())

    edited = blocks_with_pages()
    edited[-1] = TextBlock(
        text="The model reached an accuracy of 0.55 on the held-out test set.",
        page=2,
        rect=PageRect(2, 72, 90, 540, 140),
    )
    changed = passages_from_document(
        build_document(edited, doc_id=DOC_ID, doi=DOC_ID, content_type="pdf")
    )

    assert {p.doc_hash for p in baseline} != {p.doc_hash for p in changed}
    assert {p.passage_id for p in baseline}.isdisjoint({p.passage_id for p in changed})


def test_passage_id_is_a_pure_function_of_its_five_inputs() -> None:
    args = ("f" * 64, "Methods/Participants", 10, 220, "1.0")
    assert compute_passage_id(*args) == compute_passage_id(*args)
    assert compute_passage_id(*args) != compute_passage_id("e" * 64, *args[1:])
    assert compute_passage_id(*args) != compute_passage_id(args[0], "Results", *args[2:])
    assert compute_passage_id(*args) != compute_passage_id(*args[:2], 11, 220, "1.0")
    assert compute_passage_id(*args) != compute_passage_id(*args[:4], "2.0")


def test_offsets_and_hashes_address_the_real_text() -> None:
    document = full_text_document()
    for passage in passages_from_document(document):
        assert document.text[passage.char_start : passage.char_end] == passage.text
        assert passage.doc_hash == document.doc_hash
        assert len(passage.passage_hash) == 64


# ---------------------------------------------------------------------------
# BM25 search
# ---------------------------------------------------------------------------


def test_search_returns_bm25_ranked_passages_with_page_coordinates(index: PassageIndex) -> None:
    index.index_document(full_text_document())

    hits = index.search("accuracy of the self-supervised model", limit=5)
    assert hits
    best = hits[0]
    assert "accuracy" in best.text
    assert best.section_path.endswith("3. Results")
    assert best.bm25_score is not None
    assert best.page_coords and best.page_coords[0].page == 2

    # FTS5 bm25() is negated: more negative is a better match, and the list is best first.
    scores = [h.bm25_score for h in hits]
    assert scores == sorted(scores)


def test_search_can_be_scoped_to_one_document(index: PassageIndex) -> None:
    index.index_document(full_text_document())
    other = build_document(
        [
            TextBlock(text="Results", heading_level=1),
            TextBlock(text="An unrelated study of accuracy in radiology reports.", heading_level=0),
        ],
        doc_id="10.1000/other",
        content_type="html",
    )
    index.index_document(other)

    everywhere = index.search("accuracy", limit=10)
    assert {h.doc_id for h in everywhere} == {DOC_ID, "10.1000/other"}

    scoped = index.search("accuracy", doc_id=DOC_ID, limit=10)
    assert scoped
    assert {h.doc_id for h in scoped} == {DOC_ID}


def test_search_survives_query_punctuation_that_is_fts5_syntax(index: PassageIndex) -> None:
    """A claim carrying `(p < 0.05)` or a hyphen must search, not raise."""
    index.index_document(full_text_document())
    hits = index.search('accuracy (0.91) "self-supervised" AND/OR * NEAR:', limit=5)
    assert hits
    assert index.search("!!! ???") == []


def test_a_matched_passage_round_trips_through_the_store(index: PassageIndex) -> None:
    indexed = index.index_document(full_text_document())
    fetched = index.get_passage(indexed[0].passage_id)
    assert fetched is not None
    assert fetched.text == indexed[0].text
    assert fetched.page_coords == indexed[0].page_coords
    assert fetched.parser_version == PARSER_VERSION


def test_search_of_an_empty_index_is_a_clean_negative(index: PassageIndex) -> None:
    assert index.search("anything at all") == []


# ---------------------------------------------------------------------------
# Documents that have no full text still get a row, with zero passages
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", [ABSTRACT_ONLY, UNAVAILABLE])
def test_a_document_without_full_text_indexes_zero_passages(
    index: PassageIndex, verdict: str
) -> None:
    document = ExtractedDocument(
        doc_id=DOC_ID,
        accessibility=verdict,
        doi=DOC_ID,
        abstract="Only the abstract is reachable.",
    )
    passages = index.index_document(document)

    assert passages == []
    stored = index.get_document(DOC_ID)
    assert stored is not None
    assert stored.accessibility == verdict
    assert stored.passage_count == 0
    assert index.search("abstract", doc_id=DOC_ID) == []


def test_delete_document_removes_its_passages_and_its_fts_rows(index: PassageIndex) -> None:
    index.index_document(full_text_document())
    assert index.search("accuracy", doc_id=DOC_ID)

    index.delete_document(DOC_ID)
    assert index.count(DOC_ID) == 0
    assert index.get_document(DOC_ID) is None
    assert index.search("accuracy", doc_id=DOC_ID) == []


def test_the_index_persists_to_disk(tmp_path: Path) -> None:
    path = tmp_path / "passages" / "index.sqlite3"
    with PassageIndex(path) as index:
        expected = [p.passage_id for p in index.index_document(full_text_document())]
    with PassageIndex(path) as reopened:
        assert [p.passage_id for p in reopened.passages(DOC_ID)] == expected
        assert reopened.documents()[0].doc_id == DOC_ID


# ---------------------------------------------------------------------------
# Tokenizer and schema
# ---------------------------------------------------------------------------


def test_tokenize_keeps_numbers_and_drops_stopwords() -> None:
    assert tokenize("The accuracy was 0.91 on the test set") == [
        "accuracy",
        "0.91",
        "test",
        "set",
    ]
    assert "the" in tokenize("The accuracy", keep_stopwords=True)


def test_match_query_quotes_every_token() -> None:
    assert match_query("self-supervised ECG") == '"self-supervised" OR "ecg"'
    assert match_query("!!!") == ""


def test_every_passage_validates_against_the_schema(index: PassageIndex) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    index.index_document(full_text_document())
    for passage in index.search("accuracy self-supervised model", limit=5):
        validator.validate(passage.to_json_dict())
    for passage in index.passages(DOC_ID):
        validator.validate(passage.to_json_dict())


def test_a_document_without_full_text_is_recorded_with_its_verdict(index: PassageIndex) -> None:
    document = full_text_document()
    index.index_document(document)
    stored = index.get_document(DOC_ID)
    assert stored is not None
    assert stored.accessibility == FULL_TEXT
    assert stored.doc_hash == document.doc_hash
    assert stored.source_response_hashes == ["a" * 64]
    assert stored.passage_count == index.count(DOC_ID)
