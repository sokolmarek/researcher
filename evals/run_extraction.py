#!/usr/bin/env python
"""The M4.7 extraction gate: replay a labeled extraction table and MEASURE the anchoring layer.

This is the gate for the ``extraction-tables`` skill (D18): the skill may only claim measured
accuracy from THIS benchmark. Like the axis (c) faithfulness runner it is a LEXICAL baseline
harness, and like that runner it does not assert, it reports. Richer extraction (reading a
number out of a table cell, resolving a hedged population, disambiguating two datasets) is
Claude's judgment layer ON TOP of this floor, not core's job. What core is measured on here is
narrow and honest: given a paper's indexed passages and an answer-free probe, can the labeled
value be LOCATED, and when the value is genuinely absent does the extractor ABSTAIN.

A cell is a ``(paper, column, expected value)`` triple. ``expected`` is either a value the
paper really states, or the sentinel ``not reported`` for a value the paper genuinely does not
give. The six column types are population, method, dataset, metric_name, metric_value, and
sample_size. Every value was read off the paper's own text; nothing was invented (a fabricated
cell is worse than a missing one).

What it measures, per cell, using ONLY the answer-free ``query`` probe and the paper index
(never the gold value, for the present/absent decision):

* **Retrieve.** ``index.search(query)`` returns the BM25-top passages of the paper.
* **Ground.** The cell carries ``must`` tokens naming the concept (never the answer). The
  extractor is *grounded* when a retrieved passage contains all of them.
* **Locate.** For a numeric column the grounded passage must also contain a digit (a value of
  the type is stated); for an entity column grounding is enough. ``located`` is that decision.

Scoring against the gold label:

* **Location accuracy** (present cells): the extractor ``located`` the cell AND the labeled
  value actually appears in a retrieved passage. This is "can the extractor find where this
  value is stated", reported overall and per column type, with a 95% Wilson interval.
* **"Not reported" precision** (the abstention row): of every cell the extractor called ABSENT
  (``not located``), the fraction that are truly ``not reported`` in gold. A present cell the
  extractor wrongly abstained on (a location miss) drags this down; a not-reported cell it
  correctly abstained on holds it up.
* **Fabrication risk** (the safety number): of the gold ``not reported`` cells, the fraction the
  extractor wrongly claimed to LOCATE. Asserting a value the paper never gave is the extraction
  analog of the worst error this system can make, so it is featured, not buried.

Every cell also carries an **anchor layer**. A paper with extractable open-access full text is
indexed into passages and its cells anchor at the ``full-text`` layer; a paper with only an
abstract is indexed from that abstract and its cells anchor at the ``abstract`` layer and are
NEVER reported as full-text-verified (D11/D18). The runner asserts that invariant.

**It runs fully offline.** Every source response is replayed from the snapshot store
(``evals/snapshots/`` by default). A gold cell whose snapshot is missing is reported SKIPPED,
loudly, with a nonzero exit code, exactly like ``run_axes.py``; it is never silently dropped or
turned into a live call. The only way to reach the network is ``--record`` / ``--record-missing``.

Two consecutive runs produce byte-identical output (D15): nothing here reads a clock, orders by
completion, or iterates a set.

Usage::

    uv run --project core python evals/run_extraction.py                 # offline replay
    uv run --project core python evals/run_extraction.py --json          # machine-readable
    uv run --project core python evals/run_extraction.py --record-missing # LIVE: fill new snapshots
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
DEFAULT_SNAPSHOT_DIR = EVALS_DIR / "snapshots"

# The kernel lives in core/. `uv run --project core` already has it importable; adding it to
# sys.path lets a plain `python evals/run_extraction.py` work from a bare checkout too.
sys.path.insert(0, str(REPO_ROOT / "core"))
sys.path.insert(0, str(EVALS_DIR))

# House-style helpers, shared with the axis runner so the two report the same way.
from run_axes import (  # noqa: E402
    POLITE_EMAIL,
    Wilson,
    gold_items,
    session_for,
    set_polite_env,
    wilson,
)

from researcher_core import __version__ as CORE_VERSION  # noqa: E402
from researcher_core.connectors import create_connector  # noqa: E402
from researcher_core.fulltext import FULL_TEXT, extract  # noqa: E402
from researcher_core.model import normalize_doi  # noqa: E402
from researcher_core.passages import PassageIndex, tokenize  # noqa: E402
from researcher_core.snapshots import SnapshotMissingError, SnapshotSession  # noqa: E402

#: The six column types the gate covers, in report order.
COLUMN_TYPES = (
    "population",
    "method",
    "dataset",
    "metric_name",
    "metric_value",
    "sample_size",
)

#: Columns whose value is a number. For these the grounded passage must contain a digit before
#: the extractor will claim a value is stated; entity columns only need the concept grounded.
NUMERIC_COLUMNS = frozenset({"metric_value", "sample_size"})

#: The two anchor layers. ``abstract`` is never presented as full-text-verified (D11/D18).
FULL_TEXT_LAYER = "full-text"
ABSTRACT_LAYER = "abstract"

#: The abstract-only source used when a paper has no extractable OA full text: OpenAlex carries
#: an abstract for most works, reconstructed from its inverted index.
ABSTRACT_SOURCE = "openalex"

#: How many BM25-top passages the answer-free probe may inspect.
RETRIEVE_K = 10

#: The sentinel gold label for a value the paper genuinely does not state.
NOT_REPORTED = "not reported"


# ---------------------------------------------------------------------------
# The document view the extractor searches: a small uniform surface over either a
# full-text passage index or a single abstract passage.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchHit:
    """One retrieved unit of text. The extractor only ever reads ``text``."""

    text: str
    section_path: str
    passage_id: str


class DocumentView:
    """A paper the extractor can search, at a stated anchor layer.

    Full text is a real :class:`~researcher_core.passages.PassageIndex` with BM25 ranking; an
    abstract-only paper is a single abstract passage. Both answer the same ``search`` question,
    so the extractor logic below is layer-agnostic and the layer is only ever a label, never a
    silent promotion.
    """

    def __init__(self, layer: str) -> None:
        self.layer = layer

    def search(self, query: str) -> list[SearchHit]:  # pragma: no cover - overridden
        raise NotImplementedError


class FullTextView(DocumentView):
    def __init__(self, index: PassageIndex, doc_id: str) -> None:
        super().__init__(FULL_TEXT_LAYER)
        self._index = index
        self._doc_id = doc_id

    def search(self, query: str) -> list[SearchHit]:
        return [
            SearchHit(text=p.text, section_path=p.section_path, passage_id=p.passage_id)
            for p in self._index.search(query, doc_id=self._doc_id, limit=RETRIEVE_K)
        ]


class AbstractView(DocumentView):
    """One abstract, indexed as a single passage. There is nothing else honest to search."""

    def __init__(self, abstract: str, doc_id: str) -> None:
        super().__init__(ABSTRACT_LAYER)
        self._hit = SearchHit(text=abstract, section_path="Abstract", passage_id=doc_id)

    def search(self, query: str) -> list[SearchHit]:
        # A single unit: the whole abstract is the retrieved passage. Grounding and containment
        # below decide whether it actually answers the query.
        return [self._hit]


# ---------------------------------------------------------------------------
# The lexical extractor: grounding, locating, containment. No gold value is read here.
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace, for a robust substring containment test."""
    return " ".join(str(text).lower().split())


def _token_set(text: str) -> set[str]:
    """Every token of a passage, stopwords kept: a ``must`` token may be a short common word."""
    return set(tokenize(text, keep_stopwords=True))


def _has_digit(text: str) -> bool:
    return any(character.isdigit() for character in text)


def _grounded_hit(must: list[str], hits: list[SearchHit]) -> SearchHit | None:
    """The first retrieved passage that contains ALL concept tokens, or ``None``."""
    wanted = {str(token).casefold() for token in must}
    for hit in hits:
        if wanted <= _token_set(hit.text):
            return hit
    return None


def _value_locatable(value: str, hits: list[SearchHit]) -> bool:
    """True when the labeled value appears verbatim (normalized) in a retrieved passage."""
    needle = _normalize(value)
    return any(needle in _normalize(hit.text) for hit in hits)


@dataclass
class CellOutcome:
    """One scored cell: what the extractor decided, and how it lands against the gold label."""

    cell_id: str
    column: str
    layer: str
    is_not_reported: bool
    grounded: bool
    located: bool
    value_locatable: bool
    located_correct: bool  # present cells only: located AND the value is really there
    abstain_correct: bool  # not-reported cells only: correctly not located


def score_cell(cell: dict[str, Any], view: DocumentView) -> CellOutcome:
    """Run the lexical extractor on one cell and score it against its gold label."""
    column = str(cell["column"])
    query = str(cell["query"])
    must = _as_list(cell.get("must"))
    expected = str(cell["expected"])
    is_not_reported = expected.strip().casefold() == NOT_REPORTED

    hits = view.search(query)
    anchor = _grounded_hit(must, hits)
    grounded = anchor is not None
    if anchor is None:
        located = False
    elif column in NUMERIC_COLUMNS:
        # A numeric column only counts as located when the grounded passage states a number.
        located = _has_digit(anchor.text)
    else:
        located = True

    value_locatable = False if is_not_reported else _value_locatable(expected, hits)
    located_correct = (not is_not_reported) and located and value_locatable
    abstain_correct = is_not_reported and not located

    return CellOutcome(
        cell_id=str(cell["id"]),
        column=column,
        layer=view.layer,
        is_not_reported=is_not_reported,
        grounded=grounded,
        located=located,
        value_locatable=value_locatable,
        located_correct=located_correct,
        abstain_correct=abstain_correct,
    )


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


# ---------------------------------------------------------------------------
# Building the document views, offline, from snapshots.
# ---------------------------------------------------------------------------


async def build_views(
    docs: list[str],
    session: SnapshotSession,
) -> tuple[dict[str, DocumentView | SnapshotMissingError], PassageIndex, list[Any]]:
    """Index every distinct doc once, in gold order, so a doc scored many times stays identical.

    A doc named by a URL is treated as open-access full text (fetched and indexed into
    passages). A doc named by a bare DOI is treated as abstract-only: its OpenAlex abstract is
    the searchable unit, and its cells anchor at the abstract layer. A missing snapshot is
    captured as the error, so the caller can report that cell SKIPPED rather than crash.
    """
    index = PassageIndex(":memory:")
    openalex = create_connector(ABSTRACT_SOURCE, snapshots=session)
    connectors_to_close: list[Any] = [openalex]
    views: dict[str, DocumentView | SnapshotMissingError] = {}

    for ref in docs:
        if ref in views:
            continue
        try:
            if _looks_like_url(ref):
                document = await extract(ref, snapshots=session)
                if document.accessibility != FULL_TEXT:
                    raise RuntimeError(
                        f"{ref} did not extract to full text (got {document.accessibility!r}); "
                        "a URL doc in the extraction gold must resolve to full text."
                    )
                index.index_document(document)
                views[ref] = FullTextView(index, document.doc_id)
            else:
                doi = normalize_doi(ref)
                record = await openalex.resolve_doi(doi)
                abstract = record.abstract if record is not None else ""
                if not abstract:
                    raise RuntimeError(
                        f"{ref} has no OpenAlex abstract to anchor on; drop it or pick a DOI "
                        "that carries one."
                    )
                views[ref] = AbstractView(abstract, doi)
        except SnapshotMissingError as exc:
            views[ref] = exc

    return views, index, connectors_to_close


def _looks_like_url(value: str) -> bool:
    return str(value).strip().lower().startswith(("http://", "https://"))


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    n_gold: int
    skipped: list[str] = field(default_factory=list)
    outcomes: list[CellOutcome] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def scored(self) -> int:
        return len(self.outcomes)


async def run_extraction(session: SnapshotSession) -> ExtractionResult:
    cells = gold_items("extraction")
    result = ExtractionResult(n_gold=len(cells))

    docs = list(dict.fromkeys(str(cell["doc"]) for cell in cells))
    views, index, connectors = await build_views(docs, session)
    try:
        for cell in cells:
            ref = str(cell["doc"])
            view = views[ref]
            if isinstance(view, SnapshotMissingError):
                result.skipped.append(f"{cell['id']} ({ref}): {view.source} snapshot missing")
                continue
            result.outcomes.append(score_cell(cell, view))
    finally:
        index.close()
        for connector in connectors:
            await connector.aclose()

    _summarize(result)
    return result


def _summarize(result: ExtractionResult) -> None:
    outcomes = result.outcomes
    present = [o for o in outcomes if not o.is_not_reported]
    not_reported = [o for o in outcomes if o.is_not_reported]

    # Layer invariant: an abstract-layer cell must NEVER be reported at the full-text layer.
    full_text_cells = sum(1 for o in outcomes if o.layer == FULL_TEXT_LAYER)
    abstract_cells = sum(1 for o in outcomes if o.layer == ABSTRACT_LAYER)
    bad_layer = [o.cell_id for o in outcomes if o.layer not in (FULL_TEXT_LAYER, ABSTRACT_LAYER)]
    if bad_layer:
        raise RuntimeError(f"cells with an unknown anchor layer: {bad_layer}")

    # Headline: location accuracy over present cells (located AND the value is really there).
    location = wilson(sum(1 for o in present if o.located_correct), len(present))
    grounding = wilson(sum(1 for o in present if o.grounded), len(present))
    value_present = wilson(sum(1 for o in present if o.value_locatable), len(present))

    # Per column type, over present cells only (a column's not-reported cells are the abstention
    # side and are scored there, not here).
    per_column: dict[str, Wilson] = {}
    for column in COLUMN_TYPES:
        rows = [o for o in present if o.column == column]
        per_column[column] = wilson(sum(1 for o in rows if o.located_correct), len(rows))

    # The abstention row. The extractor "calls a cell absent" when it does not locate a value.
    called_absent = [o for o in outcomes if not o.located]
    truly_absent_when_called = sum(1 for o in called_absent if o.is_not_reported)
    nr_precision = wilson(truly_absent_when_called, len(called_absent))

    # Of the gold not-reported cells, how many did the extractor correctly abstain on; the
    # complement is the fabrication risk (a value asserted where none is reported).
    nr_recall = wilson(sum(1 for o in not_reported if o.abstain_correct), len(not_reported))
    fabrications = sum(1 for o in not_reported if not o.abstain_correct)
    fabrication_risk = wilson(fabrications, len(not_reported))

    # Per-layer location accuracy, so an abstract-layer number is never blended into full text.
    def layer_location(layer: str) -> Wilson:
        rows = [o for o in present if o.layer == layer]
        return wilson(sum(1 for o in rows if o.located_correct), len(rows))

    column_counts = {c: sum(1 for o in outcomes if o.column == c) for c in COLUMN_TYPES}

    result.lines.extend(
        [
            "EXTRACTION (axis M4.7): a LEXICAL anchoring baseline",
            "",
            "  A cell is (paper, column, expected value). 'located' means the answer-free probe",
            "  retrieved a passage grounded on the concept that states a value of the column's",
            "  type; a present cell is scored right only when the LABELED value is also in a",
            "  retrieved passage. This is core's floor; reading the value out is Claude's layer.",
            "",
            f"  cells scored                   {len(outcomes):>4}   "
            f"({len(present)} with a value, {len(not_reported)} 'not reported')",
            "  per column type                "
            + ", ".join(f"{c}={column_counts[c]}" for c in COLUMN_TYPES),
            f"  anchor layer                   full-text={full_text_cells}, "
            f"abstract={abstract_cells}",
            "    An abstract-layer cell is never reported as full-text-verified (D11/D18); the",
            "    runner asserts it, and the two layers are scored separately below.",
            "",
            "  LOCATION ACCURACY (present cells: the labeled value is locatable)",
            "",
            f"    overall                      {location.fraction():>7}   {location.rate()}",
            f"    of which grounded on concept {grounding.fraction():>7}   {grounding.rate()}",
            f"    value present in a passage   {value_present.fraction():>7}   {value_present.rate()}",
            "",
            "    per column type",
            *[
                f"      {column:<13}            {per_column[column].fraction():>7}   "
                f"{per_column[column].rate()}"
                for column in COLUMN_TYPES
            ],
            "",
            "    per anchor layer",
            f"      full-text                  {layer_location(FULL_TEXT_LAYER).fraction():>7}   "
            f"{layer_location(FULL_TEXT_LAYER).rate()}",
            f"      abstract                   {layer_location(ABSTRACT_LAYER).fraction():>7}   "
            f"{layer_location(ABSTRACT_LAYER).rate()}",
            "",
            "  ABSTENTION (the 'not reported' side)",
            "",
            f"    'not reported' precision     {nr_precision.fraction():>7}   {nr_precision.rate()}",
            "      of the cells the extractor called ABSENT, the fraction truly not reported. A",
            "      present cell it wrongly abstained on (a location miss) is the drag on this.",
            "",
            f"    'not reported' detection     {nr_recall.fraction():>7}   {nr_recall.rate()}",
            f"    FABRICATION RISK             {fabrication_risk.fraction():>7}   "
            f"{fabrication_risk.rate()}",
            "      of the gold 'not reported' cells, the fraction the extractor wrongly claimed to",
            "      locate. Asserting a value the paper never gave is the worst extraction error,",
            "      so it is reported as its own number, not folded into accuracy.",
        ]
    )

    result.data = {
        "axis": "extraction",
        "cells_scored": len(outcomes),
        "present": len(present),
        "not_reported": len(not_reported),
        "column_counts": column_counts,
        "layers": {"full-text": full_text_cells, "abstract": abstract_cells},
        "location_accuracy": location.to_json_dict(),
        "grounding_rate": grounding.to_json_dict(),
        "value_present_rate": value_present.to_json_dict(),
        "location_accuracy_by_column": {
            column: per_column[column].to_json_dict() for column in COLUMN_TYPES
        },
        "location_accuracy_by_layer": {
            FULL_TEXT_LAYER: layer_location(FULL_TEXT_LAYER).to_json_dict(),
            ABSTRACT_LAYER: layer_location(ABSTRACT_LAYER).to_json_dict(),
        },
        "not_reported_precision": nr_precision.to_json_dict(),
        "not_reported_detection": nr_recall.to_json_dict(),
        "fabrication_risk": fabrication_risk.to_json_dict(),
    }


# ---------------------------------------------------------------------------
# Rendering and driver
# ---------------------------------------------------------------------------

MODE_NOTE = {
    "replay": "offline replay from snapshots; no network",
    "record": "LIVE: this run hit the network and rewrote snapshots",
    "fill": "LIVE for MISSING snapshots only; everything already stored was replayed",
}


def render(result: ExtractionResult, mode: str) -> str:
    out: list[str] = [
        "=" * 78,
        "RESEARCHER EVIDENCE KERNEL: EXTRACTION BENCHMARK (M4.7)",
        "=" * 78,
        "",
        f"core version    {CORE_VERSION}",
        f"mode            {mode} ({MODE_NOTE[mode]})",
        "intervals       95% Wilson score intervals, never the normal approximation",
        "",
        "-" * 78,
    ]
    out.extend(result.lines)
    out.append("")
    if result.skipped:
        out.append(f"  !! SKIPPED {len(result.skipped)} of {result.n_gold} GOLD CELLS !!")
        out.append("     A skipped cell has no snapshot. It is NOT scored and NOT silently")
        out.append("     dropped: every number above is over the scored cells only.")
        for line in result.skipped[:20]:
            out.append(f"       - {line}")
        if len(result.skipped) > 20:
            out.append(f"       ... and {len(result.skipped) - 20} more")
    else:
        out.append(f"  scored {result.scored}/{result.n_gold} gold cells, 0 skipped")
    out.extend(
        [
            "",
            "=" * 78,
            "WHAT THIS n CERTIFIES (D17)",
            "=" * 78,
            "  This is a baseline measurement, not a zero-error certification. A per-column n of",
            "  ~20 cannot certify an error rate below 0.10 even at a perfect score (a 20/20 Wilson",
            "  interval still reaches 0.839). The gate size (>= 100 cells, >= 20 per column type)",
            "  makes each column MEASURABLE; it does not license a bound. See evals/BENCHMARKS.md,",
            "  which states for each number what it can and cannot certify.",
            "",
        ]
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_extraction.py",
        description="Replay the extraction gold set over the evidence kernel and report the numbers.",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="LIVE MODE: hit the real APIs and write snapshots. Not deterministic, by definition.",
    )
    parser.add_argument(
        "--record-missing",
        action="store_true",
        help="LIVE, but only for cells whose snapshot is MISSING; everything stored is replayed.",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help=f"snapshot store to replay from or record into (default: {DEFAULT_SNAPSHOT_DIR})",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--out", type=Path, help="write the report to this file as well as to stdout"
    )
    args = parser.parse_args(argv)

    if args.record and args.record_missing:
        parser.error("--record and --record-missing are mutually exclusive")

    set_polite_env()
    if args.record:
        mode = "record"
    elif args.record_missing:
        mode = "fill"
    else:
        mode = "replay"
    session = session_for(mode, args.snapshot_dir)

    if mode == "replay" and not args.snapshot_dir.is_dir():
        print(
            f"No snapshot store at {args.snapshot_dir}. This runner never goes live on its own: "
            f"record one first with\n"
            f"    uv run --project core python evals/run_extraction.py --record-missing",
            file=sys.stderr,
        )
        return 2

    result = asyncio.run(run_extraction(session))

    if args.json:
        payload = {
            "core_version": CORE_VERSION,
            "mode": mode,
            "polite_email": POLITE_EMAIL,
            **result.data,
            "gold_cells": result.n_gold,
            "scored": result.scored,
            "skipped": len(result.skipped),
            "skipped_cells": list(result.skipped),
        }
        text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    else:
        text = render(result, mode)

    sys.stdout.write(text + "\n")
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")

    # A missing snapshot is a defect in the eval; exit nonzero so CI cannot go green over a
    # benchmark that quietly measured half its gold set.
    return 1 if result.skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
