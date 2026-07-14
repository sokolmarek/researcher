#!/usr/bin/env python
"""The M2 exit gate: replay every axis over its gold set and MEASURE it (M2.12, D15/D16/D17).

This runner does not assert. It reports. A benchmark that asserts tells you a threshold was
met; a benchmark that reports tells you what the kernel actually does, including the parts
that are bad. The exit gate is a human reading these numbers, not a green check.

What it measures, and why each one is shaped the way it is:

* **Axis (a), reference identity.** The headline is the REFUSAL-GRADE FALSE POSITIVE RATE: how
  often a real reference (gold ``verified`` or ``inconclusive``) is called ``unresolvable`` or
  ``mismatch``. That is the rate at which the kernel accuses an honest researcher, and it is
  reported separately from accuracy because accuracy hides it.
* **Axes (b) and (d).** Confusion matrices with 95% Wilson intervals.
* **Axis (c), faithfulness.** A confusion matrix, plus SELECTIVE ABSTENTION as a RISK-COVERAGE
  CURVE. ``insufficient-passage`` is abstention. An oracle that abstains on everything has
  perfect accuracy on what it answers and is worthless; only the curve exposes that, so the
  curve is what this runner prints.
* **Retrieval.** recall@k over known-item queries.
* **Dedup.** Pair accuracy with BOTH error directions reported separately, because a false
  merge destroys data and a false split merely leaves a duplicate behind.

Every interval is a **Wilson** score interval, never a normal approximation. At these n the
normal approximation is wrong exactly where our numbers live (near 0 and near 1): it produces
intervals that run below zero and it collapses to zero width at p = 0, which would let a
zero-error run claim certainty it has not earned.

**It runs fully offline.** Every source response is replayed from the snapshot store
(``evals/snapshots/`` by default). A gold item whose snapshot is missing is reported as
SKIPPED, with a loud count in the report and a nonzero exit code, and is NEVER silently
dropped or quietly turned into a live call. The only way to reach the network is ``--record``,
which is how the snapshots got there in the first place.

Two consecutive runs produce byte-identical output (D15). Nothing here reads a clock, orders
by completion, or iterates a set.

Usage::

    uv run --project core python evals/run_axes.py                 # offline replay, all axes
    uv run --project core python evals/run_axes.py --axis identity # one axis
    uv run --project core python evals/run_axes.py --json          # machine-readable
    uv run --project core python evals/run_axes.py --record        # LIVE: refresh snapshots
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
GOLD_DIR = EVALS_DIR / "gold"
DEFAULT_SNAPSHOT_DIR = EVALS_DIR / "snapshots"

# The kernel lives in core/. Adding it to sys.path lets `python evals/run_axes.py` work from a
# plain checkout; `uv run --project core` already has it importable and this is a no-op there.
sys.path.insert(0, str(REPO_ROOT / "core"))

from researcher_core import __version__ as CORE_VERSION  # noqa: E402
from researcher_core.connectors import create_connector  # noqa: E402
from researcher_core.dedupe import dedupe  # noqa: E402
from researcher_core.faithfulness import (  # noqa: E402
    CONTRADICTED,
    DEFAULT_TOP_K,
    INSUFFICIENT_PASSAGE,
    PARTIAL,
    SUPPORT_THRESHOLD,
    SUPPORTED,
    check_claim,
    score_passage,
)
from researcher_core.fulltext import extract  # noqa: E402
from researcher_core.model import CSLName, CSLDate, CSLRecord, normalize_doi  # noqa: E402
from researcher_core.passages import PassageIndex  # noqa: E402
from researcher_core.search import search  # noqa: E402
from researcher_core.snapshots import (  # noqa: E402
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)
from researcher_core.status import check_status_async  # noqa: E402
from researcher_core.verify import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    INCONCLUSIVE,
    MISMATCH,
    ReferenceClaim,
    UNRESOLVABLE,
    VERIFIED,
    is_refusal_grade,
    verify_claim_async,
)

# The polite-pool identity every recorded call carries. Keyless, per the M2 plan.
POLITE_EMAIL = "mareksokol98@gmail.com"

#: Sources per axis. Pinned here rather than taken from the kernel's defaults, because a
#: benchmark whose source set drifts with a default is not comparable across runs.
IDENTITY_SOURCES = ("openalex", "crossref", "datacite")
STATUS_SOURCES = ("crossref", "openalex")
ACCESSIBILITY_SOURCES = ("unpaywall", "arxiv", "pubmed")
RETRIEVAL_SOURCES = ("openalex", "crossref", "arxiv")

#: recall@k is reported at each of these k.
RECALL_K = (1, 3, 5, 10)

AXES = ("identity", "status", "accessibility", "faithfulness", "retrieval", "dedup")

Z95 = 1.959963984540054


# ---------------------------------------------------------------------------
# A minimal YAML reader
# ---------------------------------------------------------------------------
#
# The gold sets are YAML, and the kernel's base runtime dependencies are httpx, rapidfuzz and
# platformdirs, full stop. PyYAML is not among them and this runner is not the place to add a
# dependency, so the subset the gold files actually use is parsed here: comments, block
# mappings, block sequences, flow sequences, flow mappings, and quoted or bare scalars. It is
# strict: anything it does not understand raises rather than guessing, because a gold set
# silently half-read is worse than one that fails to load.


class GoldFormatError(RuntimeError):
    """A gold file is not in the subset of YAML this reader accepts."""


def _split_comment(line: str) -> str:
    """Strip a trailing ``#`` comment, respecting quotes."""
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def _scalar(text: str) -> Any:
    """One YAML scalar: quoted string, int, float, bool, null, or bare string."""
    raw = text.strip()
    if not raw:
        return ""
    if raw[0] == '"' and raw[-1] == '"' and len(raw) >= 2:
        return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if raw[0] == "'" and raw[-1] == "'" and len(raw) >= 2:
        return raw[1:-1].replace("''", "'")
    lowered = raw.casefold()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if lowered in {"null", "~", ""}:
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _split_flow(body: str) -> list[str]:
    """Split a flow collection's body on top-level commas, respecting quotes and nesting."""
    parts: list[str] = []
    depth = 0
    quote = ""
    current: list[str] = []
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
            current.append(char)
        elif char in "[{":
            depth += 1
            current.append(char)
        elif char in "]}":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _split_key(text: str) -> tuple[str, str] | None:
    """Split ``key: value`` at the first top-level colon. ``None`` when there is none."""
    quote = ""
    depth = 0
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        elif char == ":" and depth == 0:
            after = text[index + 1 : index + 2]
            if after in ("", " ", "\t"):
                return text[:index].strip(), text[index + 1 :].strip()
    return None


def _value(text: str) -> Any:
    """A scalar or a flow collection."""
    raw = text.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [_value(part) for part in _split_flow(raw[1:-1])]
    if raw.startswith("{") and raw.endswith("}"):
        out: dict[str, Any] = {}
        for part in _split_flow(raw[1:-1]):
            pair = _split_key(part)
            if pair is None:
                raise GoldFormatError(f"Flow mapping entry is not 'key: value': {part!r}")
            out[pair[0]] = _value(pair[1])
        return out
    return _scalar(raw)


@dataclass
class _Line:
    indent: int
    text: str
    number: int


def _lines(source: str) -> list[_Line]:
    out: list[_Line] = []
    for number, raw in enumerate(source.splitlines(), start=1):
        stripped = _split_comment(raw).rstrip()
        if not stripped.strip():
            continue
        out.append(_Line(len(stripped) - len(stripped.lstrip()), stripped.strip(), number))
    return out


def _parse_block(lines: Sequence[_Line], start: int, indent: int) -> tuple[Any, int]:
    if start >= len(lines):
        return None, start
    if lines[start].text.startswith("- "):
        return _parse_sequence(lines, start, indent)
    return _parse_mapping(lines, start, indent)


def _parse_sequence(lines: Sequence[_Line], start: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line.indent < indent or not line.text.startswith("- "):
            break
        if line.indent > indent:
            raise GoldFormatError(f"line {line.number}: unexpected indent in sequence")
        body = line.text[2:].strip()
        pair = _split_key(body)
        if pair is None:
            items.append(_value(body))
            index += 1
            continue
        # A mapping that starts on the dash line: its remaining keys are indented to the
        # column the first key started at.
        inner_indent = line.indent + 2
        mapping: dict[str, Any] = {}
        _assign(mapping, pair, lines, index, inner_indent)
        index += 1
        while index < len(lines) and lines[index].indent >= inner_indent:
            if lines[index].text.startswith("- "):
                break
            inner = _split_key(lines[index].text)
            if inner is None:
                raise GoldFormatError(f"line {lines[index].number}: expected 'key: value'")
            consumed = _assign(mapping, inner, lines, index, inner_indent)
            index += consumed
        items.append(mapping)
    return items, index


def _parse_mapping(lines: Sequence[_Line], start: int, indent: int) -> tuple[dict[str, Any], int]:
    mapping: dict[str, Any] = {}
    index = start
    while index < len(lines):
        line = lines[index]
        if line.indent < indent or line.text.startswith("- "):
            break
        pair = _split_key(line.text)
        if pair is None:
            raise GoldFormatError(f"line {line.number}: expected 'key: value'")
        index += _assign(mapping, pair, lines, index, indent)
    return mapping, index


def _assign(
    mapping: dict[str, Any],
    pair: tuple[str, str],
    lines: Sequence[_Line],
    index: int,
    indent: int,
) -> int:
    """Set one key. Returns how many lines were consumed (1 plus any nested block)."""
    key, raw = pair
    if raw:
        mapping[key] = _value(raw)
        return 1
    child_start = index + 1
    if child_start < len(lines) and lines[child_start].indent > indent:
        value, end = _parse_block(lines, child_start, lines[child_start].indent)
        mapping[key] = value
        return end - index
    if (
        child_start < len(lines)
        and lines[child_start].indent == indent
        and lines[child_start].text.startswith("- ")
    ):
        # A sequence at the SAME indent as its key, which is legal YAML and is what the gold
        # files use for `items:`.
        value, end = _parse_sequence(lines, child_start, indent)
        mapping[key] = value
        return end - index
    mapping[key] = None
    return 1


def read_gold(path: Path) -> dict[str, Any]:
    """Load one gold file. Raises :class:`GoldFormatError` rather than guessing."""
    lines = _lines(path.read_text(encoding="utf-8"))
    if not lines:
        raise GoldFormatError(f"{path} is empty")
    document, end = _parse_block(lines, 0, lines[0].indent)
    if end != len(lines):
        raise GoldFormatError(f"{path}: stopped at line {lines[end].number}, {lines[end].text!r}")
    if not isinstance(document, Mapping):
        raise GoldFormatError(f"{path}: top level is not a mapping")
    return dict(document)


def gold_items(name: str) -> list[dict[str, Any]]:
    document = read_gold(GOLD_DIR / f"{name}.yaml")
    items = document.get("items")
    if not isinstance(items, list) or not items:
        raise GoldFormatError(f"{name}.yaml has no 'items' list")
    return [dict(item) for item in items]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Wilson:
    """A 95% Wilson score interval for k successes in n trials."""

    k: int
    n: int
    low: float
    high: float

    @property
    def point(self) -> float:
        return self.k / self.n if self.n else 0.0

    def rate(self) -> str:
        if not self.n:
            return "n/a (n=0)"
        return f"{self.point:.3f} [{self.low:.3f}, {self.high:.3f}]"

    def fraction(self) -> str:
        return f"{self.k}/{self.n}"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "n": self.n,
            "point": round(self.point, 6),
            "ci95_low": round(self.low, 6),
            "ci95_high": round(self.high, 6),
        }


def wilson(k: int, n: int, z: float = Z95) -> Wilson:
    """The Wilson score interval, and deliberately not the normal approximation.

    The normal (Wald) interval is ``p +- z*sqrt(p(1-p)/n)``. At p = 0 it has zero width, which
    would let a zero-error run on n = 8 claim an error rate of exactly 0.000 with no
    uncertainty at all. Our numbers live at exactly that boundary. Wilson does not collapse:
    0 errors in 8 gives [0.000, 0.324], 0 errors in 100 gives [0.000, 0.037], and the
    difference between those two is the whole point of measuring.
    """
    if n <= 0:
        return Wilson(k=0, n=0, low=0.0, high=1.0)
    p = k / n
    denominator = 1.0 + (z * z) / n
    center = (p + (z * z) / (2 * n)) / denominator
    half = (z * math.sqrt(p * (1 - p) / n + (z * z) / (4 * n * n))) / denominator
    return Wilson(k=k, n=n, low=max(0.0, center - half), high=min(1.0, center + half))


@dataclass
class Confusion:
    """A confusion matrix over a fixed, ordered label vocabulary."""

    labels: tuple[str, ...]
    counts: dict[str, dict[str, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.counts:
            self.counts = {g: {p: 0 for p in self.labels} for g in self.labels}

    def add(self, gold: str, predicted: str) -> None:
        if gold not in self.counts:
            raise KeyError(f"gold label {gold!r} is outside the vocabulary {self.labels}")
        if predicted not in self.counts[gold]:
            raise KeyError(f"predicted label {predicted!r} is outside the vocabulary")
        self.counts[gold][predicted] += 1

    @property
    def total(self) -> int:
        return sum(sum(row.values()) for row in self.counts.values())

    @property
    def correct(self) -> int:
        return sum(self.counts[label][label] for label in self.labels)

    def accuracy(self) -> Wilson:
        return wilson(self.correct, self.total)

    def gold_total(self, label: str) -> int:
        return sum(self.counts[label].values())

    def predicted_total(self, label: str) -> int:
        return sum(self.counts[g][label] for g in self.labels)

    def recall(self, label: str) -> Wilson:
        return wilson(self.counts[label][label], self.gold_total(label))

    def precision(self, label: str) -> Wilson:
        return wilson(self.counts[label][label], self.predicted_total(label))

    def render(self) -> list[str]:
        width = max([len(label) for label in self.labels] + [len("gold \\ predicted")])
        cells = [max(len(label), 5) for label in self.labels]
        header = "  ".join(label.rjust(w) for label, w in zip(self.labels, cells))
        out = [f"{'gold \\ predicted'.ljust(width)}  {header}"]
        for gold in self.labels:
            row = "  ".join(
                str(self.counts[gold][p]).rjust(w) for p, w in zip(self.labels, cells)
            )
            out.append(f"{gold.ljust(width)}  {row}")
        return out

    def per_class_rows(self) -> list[str]:
        width = max(len(label) for label in self.labels)
        out = [f"{'class'.ljust(width)}  {'n':>4}  {'recall (95% Wilson)':<22}  precision (95% Wilson)"]
        for label in self.labels:
            out.append(
                f"{label.ljust(width)}  {self.gold_total(label):>4}  "
                f"{self.recall(label).rate():<22}  {self.precision(label).rate()}"
            )
        return out

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "labels": list(self.labels),
            "matrix": {g: dict(self.counts[g]) for g in self.labels},
            "total": self.total,
            "accuracy": self.accuracy().to_json_dict(),
            "per_class": {
                label: {
                    "n": self.gold_total(label),
                    "recall": self.recall(label).to_json_dict(),
                    "precision": self.precision(label).to_json_dict(),
                }
                for label in self.labels
            },
        }


# ---------------------------------------------------------------------------
# Result shell
# ---------------------------------------------------------------------------


@dataclass
class AxisResult:
    """One axis: its numbers, its skipped items, and the lines it prints."""

    name: str
    n_gold: int
    skipped: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def scored(self) -> int:
        return self.n_gold - len(self.skipped)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "axis": self.name,
            "gold_items": self.n_gold,
            "scored": self.scored,
            "skipped": len(self.skipped),
            "skipped_items": list(self.skipped),
            **self.data,
        }


def session_for(mode: str, snapshot_dir: Path) -> SnapshotSession:
    """The one snapshot session every axis runs through.

    In ``replay`` (the default) nothing below this can reach the network: ``afetch`` never
    calls its fetcher. In ``record`` every response is written to the store, which is the only
    way snapshots are ever created.
    """
    store = SnapshotStore(snapshot_dir)
    return SnapshotSession(store, SnapshotMode.parse(mode), cache=None)


def set_polite_env() -> None:
    """The keyless polite-pool identity, set only when the operator has not set their own."""
    for name in (
        "OPENALEX_MAILTO",
        "CROSSREF_MAILTO",
        "DATACITE_MAILTO",
        "UNPAYWALL_EMAIL",
        "NCBI_EMAIL",
        "RESEARCHER_CORE_MAILTO",
        "RESEARCHER_CORE_EMAIL",
    ):
        os.environ.setdefault(name, POLITE_EMAIL)


# ---------------------------------------------------------------------------
# Axis (a): reference identity
# ---------------------------------------------------------------------------

IDENTITY_LABELS = (VERIFIED, MISMATCH, UNRESOLVABLE, INCONCLUSIVE)


async def run_identity(session: SnapshotSession) -> AxisResult:
    items = gold_items("identity")
    result = AxisResult(name="identity", n_gold=len(items))
    matrix = Confusion(IDENTITY_LABELS)

    connectors = [create_connector(name, snapshots=session) for name in IDENTITY_SOURCES]
    try:
        for item in items:
            gold = str(item["expected"])
            doi = str(item.get("doi") or "")
            claim = ReferenceClaim(
                key=doi,
                title=str(item.get("title") or ""),
                doi=doi,
                year=item.get("year") if isinstance(item.get("year"), int) else None,
                authors=[str(item["first_author"])] if item.get("first_author") else [],
            )
            try:
                entry = await verify_claim_async(
                    claim,
                    connectors,
                    DEFAULT_THRESHOLDS,
                    check_status=False,
                    check_accessibility=False,
                )
            except SnapshotMissingError as exc:
                result.skipped.append(f"{doi or claim.title}: {exc.source} snapshot missing")
                continue
            matrix.add(gold, entry.verdict)
    finally:
        for connector in connectors:
            await connector.aclose()

    # The number this axis exists for. Negatives are the references that are REAL and must not
    # be refused: gold `verified` plus gold `inconclusive`. A refusal-grade false positive is
    # one of those called `unresolvable` or `mismatch`.
    negatives = [label for label in (VERIFIED, INCONCLUSIVE)]
    positives = [label for label in (UNRESOLVABLE, MISMATCH)]
    fp = sum(
        matrix.counts[gold][pred]
        for gold in negatives
        for pred in IDENTITY_LABELS
        if is_refusal_grade(pred)
    )
    n_negatives = sum(matrix.gold_total(gold) for gold in negatives)
    fn = sum(
        matrix.counts[gold][pred]
        for gold in positives
        for pred in IDENTITY_LABELS
        if not is_refusal_grade(pred)
    )
    n_positives = sum(matrix.gold_total(gold) for gold in positives)
    fpr = wilson(fp, n_negatives)
    fnr = wilson(fn, n_positives)

    result.lines.extend(
        [
            "AXIS (a): REFERENCE IDENTITY",
            "",
            "  Confusion matrix",
            *[f"    {line}" for line in matrix.render()],
            "",
            *[f"  {line}" for line in matrix.per_class_rows()],
            "",
            f"  accuracy                       {matrix.accuracy().fraction():>7}   "
            f"{matrix.accuracy().rate()}",
            "",
            "  THE HEADLINE NUMBER",
            "",
            f"    refusal-grade FALSE POSITIVE   {fpr.fraction():>7}   {fpr.rate()}",
            "      a REAL reference (gold verified or inconclusive) called unresolvable or",
            "      mismatch. This is the kernel accusing an honest researcher of fabricating a",
            "      citation that exists. It is the worst thing this system can do, it is the",
            "      reason the refusal-grade set excludes `inconclusive`, and it is the number",
            "      that must stay at zero.",
            "",
            f"    refusal-grade FALSE NEGATIVE   {fnr.fraction():>7}   {fnr.rate()}",
            "      a fabricated or wrong reference (gold unresolvable or mismatch) that the",
            "      kernel did not flag. This is a missed catch. It is worse for the literature",
            "      and better for the individual user, and D9's precedence trades deliberately",
            "      in that direction: thin or dirty evidence falls to `inconclusive`, never to",
            "      a refusal.",
        ]
    )
    result.data = {
        "confusion": matrix.to_json_dict(),
        "refusal_grade_false_positive": fpr.to_json_dict(),
        "refusal_grade_false_negative": fnr.to_json_dict(),
        "sources": list(IDENTITY_SOURCES),
    }
    return result


# ---------------------------------------------------------------------------
# Axis (b): publication status
# ---------------------------------------------------------------------------

STATUS_LABELS = ("current", "corrected", "retracted", "expression-of-concern")


async def run_status(session: SnapshotSession) -> AxisResult:
    items = gold_items("status")
    result = AxisResult(name="status", n_gold=len(items))
    matrix = Confusion(STATUS_LABELS)
    unchecked = 0
    conflicts = 0

    connectors = [create_connector(name, snapshots=session) for name in STATUS_SOURCES]
    try:
        for item in items:
            doi = str(item["doi"])
            gold = str(item["expected"])
            try:
                entry = await check_status_async(doi, connectors)
            except SnapshotMissingError as exc:
                result.skipped.append(f"{doi}: {exc.source} snapshot missing")
                continue
            matrix.add(gold, entry.verdict)
            unchecked += 0 if entry.checked else 1
            conflicts += 1 if entry.conflict else 0
    finally:
        for connector in connectors:
            await connector.aclose()

    result.lines.extend(
        [
            "AXIS (b): PUBLICATION STATUS",
            "",
            "  Confusion matrix",
            *[f"    {line}" for line in matrix.render()],
            "",
            *[f"  {line}" for line in matrix.per_class_rows()],
            "",
            f"  accuracy                       {matrix.accuracy().fraction():>7}   "
            f"{matrix.accuracy().rate()}",
            f"  unchecked (every source errored)   {unchecked:>3}",
            f"  source conflicts reported          {conflicts:>3}",
        ]
    )
    result.data = {
        "confusion": matrix.to_json_dict(),
        "unchecked": unchecked,
        "conflicts": conflicts,
        "sources": list(STATUS_SOURCES),
    }
    return result


# ---------------------------------------------------------------------------
# Axis (d): accessibility
# ---------------------------------------------------------------------------

ACCESSIBILITY_LABELS = ("full-text", "abstract-only", "unavailable")


async def run_accessibility(session: SnapshotSession) -> AxisResult:
    from researcher_core.fulltext import resolve_oa

    items = gold_items("accessibility")
    result = AxisResult(name="accessibility", n_gold=len(items))
    matrix = Confusion(ACCESSIBILITY_LABELS)

    connectors = {
        name: create_connector(name, snapshots=session) for name in ACCESSIBILITY_SOURCES
    }
    try:
        for item in items:
            doi = str(item["doi"])
            gold = str(item["expected"])
            try:
                resolution = await resolve_oa(doi, connectors=connectors)
            except SnapshotMissingError as exc:
                result.skipped.append(f"{doi}: {exc.source} snapshot missing")
                continue
            matrix.add(gold, resolution.verdict)
    finally:
        for connector in connectors.values():
            await connector.aclose()

    result.lines.extend(
        [
            "AXIS (d): ACCESSIBILITY",
            "",
            "  Confusion matrix",
            *[f"    {line}" for line in matrix.render()],
            "",
            *[f"  {line}" for line in matrix.per_class_rows()],
            "",
            f"  accuracy                       {matrix.accuracy().fraction():>7}   "
            f"{matrix.accuracy().rate()}",
            "",
            "  The gold labels come from Unpaywall alone. The kernel's cascade is Unpaywall,",
            "  then arXiv, then PMC, so it can find an OA copy where Unpaywall reports none.",
            "  Off-diagonal cells in the abstract-only row are therefore not automatically",
            "  errors: read them with the per-item detail before calling them defects.",
        ]
    )
    result.data = {"confusion": matrix.to_json_dict(), "sources": list(ACCESSIBILITY_SOURCES)}
    return result


# ---------------------------------------------------------------------------
# Axis (c): faithfulness, with the risk-coverage curve
# ---------------------------------------------------------------------------

FAITHFULNESS_LABELS = (SUPPORTED, PARTIAL, CONTRADICTED, INSUFFICIENT_PASSAGE)
ANSWERED_LABELS = (SUPPORTED, PARTIAL, CONTRADICTED)


def forced_verdict(claim: str, doc_id: str, index: PassageIndex) -> tuple[str, float]:
    """The verdict the kernel WOULD emit if the abstention rule were deleted, plus confidence.

    This is not a second classifier. It is :func:`researcher_core.faithfulness.check_claim`'s
    own precedence with the ``insufficient-passage`` floor removed: the same BM25 candidates,
    the same :func:`score_passage`, the same contradiction-beats-support ordering. Everything
    the abstention would have hidden now has to commit to an answer, which is exactly what a
    risk-coverage curve needs: a prediction and a confidence for every item, so abstention can
    be priced instead of being folded into an accuracy number.

    Confidence is the best passage-overlap score. An item with no candidate passages at all
    gets confidence 0.0 and the weakest answer, which is the right place for it: it is the
    first thing any sane abstention policy gives up on.
    """
    candidates = index.search(claim, doc_id=doc_id, limit=DEFAULT_TOP_K)
    if not candidates:
        return PARTIAL, 0.0
    assessments = [score_passage(claim, passage) for passage in candidates]
    supporting = [a.score for a in assessments if not a.is_contradicting]
    contradicting = [a.score for a in assessments if a.is_contradicting]
    best_support = max(supporting) if supporting else 0.0
    best_contra = max(contradicting) if contradicting else 0.0
    if best_contra >= best_support and best_contra > 0.0:
        return CONTRADICTED, best_contra
    if best_support >= SUPPORT_THRESHOLD:
        return SUPPORTED, best_support
    return PARTIAL, best_support


@dataclass
class RiskPoint:
    threshold: float
    coverage: float
    answered: int
    errors: int
    risk: float


def risk_coverage(rows: Sequence[tuple[str, str, float]]) -> list[RiskPoint]:
    """The selective-prediction risk-coverage curve.

    ``rows`` is ``(gold, forced_prediction, confidence)`` for every ANSWERABLE item. A policy
    with confidence threshold ``t`` answers every item whose confidence is at least ``t`` and
    abstains on the rest. Coverage is the fraction answered; risk is the error rate among the
    answered.

    The curve is what makes abstention honest. An oracle that abstains on everything reaches
    coverage 0.0, where risk is undefined and the system has done nothing; a system that
    answers everything reaches coverage 1.0 and pays its full error rate. Any accuracy figure
    quoted without its coverage is a number from somewhere on this curve with the coverage
    filed off.
    """
    if not rows:
        return []
    thresholds = sorted({round(confidence, 4) for _, _, confidence in rows}, reverse=True)
    points: list[RiskPoint] = []
    total = len(rows)
    for threshold in thresholds:
        answered = [r for r in rows if round(r[2], 4) >= threshold]
        errors = sum(1 for gold, predicted, _ in answered if gold != predicted)
        points.append(
            RiskPoint(
                threshold=threshold,
                coverage=len(answered) / total,
                answered=len(answered),
                errors=errors,
                risk=errors / len(answered) if answered else 0.0,
            )
        )
    return points


def aurc(points: Sequence[RiskPoint]) -> float:
    """Area under the risk-coverage curve, by the trapezoid rule over coverage."""
    if len(points) < 2:
        return points[0].risk if points else 0.0
    ordered = sorted(points, key=lambda p: p.coverage)
    area = 0.0
    for left, right in zip(ordered, ordered[1:]):
        area += (right.coverage - left.coverage) * (left.risk + right.risk) / 2.0
    span = ordered[-1].coverage - ordered[0].coverage
    return area / span if span else ordered[0].risk


async def run_faithfulness(session: SnapshotSession) -> AxisResult:
    items = gold_items("faithfulness")
    result = AxisResult(name="faithfulness", n_gold=len(items))
    matrix = Confusion(FAITHFULNESS_LABELS)

    connectors = {
        name: create_connector(name, snapshots=session) for name in ACCESSIBILITY_SOURCES
    }
    index = PassageIndex(":memory:")
    documents: dict[str, Any] = {}
    anchor_hits = 0
    anchor_checked = 0
    rows: list[tuple[str, str, float]] = []
    unanswerable = 0

    try:
        # Index every distinct document first, in gold order, so a document fetched once is
        # scored many times and the run stays byte-identical whatever the item order.
        for item in items:
            reference = str(item["doc"])
            if reference in documents:
                continue
            try:
                extracted = await extract(reference, snapshots=session, connectors=connectors)
            except SnapshotMissingError as exc:
                documents[reference] = exc
                continue
            index.index_document(extracted)
            # check_claim takes the INDEXED document, not the extracted one: the axis (c)
            # verdict must be a function of what is actually in the index, not of what the
            # extractor believed it had.
            documents[reference] = index.get_document(extracted.doc_id)

        for item in items:
            reference = str(item["doc"])
            document = documents[reference]
            if isinstance(document, SnapshotMissingError):
                result.skipped.append(f"{item['id']}: {document.source} snapshot missing")
                continue
            gold = str(item["expected"])
            claim = str(item["claim"])
            verdict = check_claim(claim, document, index, claim_id=str(item["id"]))
            matrix.add(gold, verdict.verdict)

            expected_passage = str(item.get("passage_id") or "")
            if expected_passage:
                anchor_checked += 1
                if any(a.passage.passage_id == expected_passage for a in verdict.evidence):
                    anchor_hits += 1

            if document.passage_count > 0:
                prediction, confidence = forced_verdict(claim, document.doc_id, index)
                rows.append((gold if gold in ANSWERED_LABELS else gold, prediction, confidence))
            else:
                unanswerable += 1
    finally:
        index.close()
        for connector in connectors.values():
            await connector.aclose()

    abstained = sum(matrix.counts[g][INSUFFICIENT_PASSAGE] for g in FAITHFULNESS_LABELS)
    total = matrix.total
    coverage = wilson(total - abstained, total)
    answered_correct = sum(matrix.counts[g][g] for g in ANSWERED_LABELS)
    answered_total = total - abstained
    answered_accuracy = wilson(answered_correct, answered_total)
    correct_abstentions = wilson(
        matrix.counts[INSUFFICIENT_PASSAGE][INSUFFICIENT_PASSAGE],
        matrix.gold_total(INSUFFICIENT_PASSAGE),
    )

    curve = risk_coverage(rows)
    area = aurc(curve)

    curve_lines = [
        f"    {'confidence':>10}  {'coverage':>8}  {'answered':>8}  {'errors':>6}  {'risk':>6}"
    ]
    for point in curve:
        curve_lines.append(
            f"    {point.threshold:>10.3f}  {point.coverage:>8.3f}  {point.answered:>8}  "
            f"{point.errors:>6}  {point.risk:>6.3f}"
        )

    anchor = wilson(anchor_hits, anchor_checked)
    result.lines.extend(
        [
            "AXIS (c): CLAIM FAITHFULNESS",
            "",
            "  Confusion matrix (insufficient-passage is ABSTENTION, not a wrong answer)",
            *[f"    {line}" for line in matrix.render()],
            "",
            *[f"  {line}" for line in matrix.per_class_rows()],
            "",
            f"  accuracy over ALL items        {matrix.accuracy().fraction():>7}   "
            f"{matrix.accuracy().rate()}",
            f"  accuracy over ANSWERED items   {answered_accuracy.fraction():>7}   "
            f"{answered_accuracy.rate()}",
            f"  coverage (fraction answered)   {coverage.fraction():>7}   {coverage.rate()}",
            f"  correct abstentions            {correct_abstentions.fraction():>7}   "
            f"{correct_abstentions.rate()}",
            "",
            "    The second line is the number a vendor would quote. It is meaningless on its",
            "    own: quoting accuracy over answered items while abstaining freely is how an",
            "    oracle that abstains on everything reports perfect accuracy. Read it only",
            "    against the coverage on the line below it.",
            "",
            "  RISK-COVERAGE CURVE (selective prediction)",
            "",
            "    Every answerable item is forced to an answer (the same decision procedure with",
            "    the insufficient-passage floor removed) and scored by its best passage-overlap",
            "    confidence. A policy answers everything at or above the confidence threshold",
            "    and abstains below it.",
            "",
            *curve_lines,
            "",
            f"    answerable items          {len(rows):>4}   (documents with indexed passages)",
            f"    structurally unanswerable {unanswerable:>4}   (no full text: nothing to anchor on,",
            "                                    so abstention is the only honest answer and",
            "                                    these items are excluded from the curve)",
            f"    AURC (mean risk over the curve)  {area:.3f}",
            "",
            "    Coverage 0.0 is the degenerate oracle: it abstains on everything, has no risk,",
            "    and is useless. Any operating point is a trade between the two columns, and the",
            "    curve is the only place that trade is visible.",
            "",
            f"  passage anchoring              {anchor.fraction():>7}   {anchor.rate()}",
            "    of the non-abstaining gold items with a recorded passage ID, the fraction whose",
            "    verdict cited that exact passage. An anchor miss is not a verdict error: the",
            "    kernel may have justified the same verdict from a different real passage of the",
            "    same document.",
        ]
    )
    result.data = {
        "confusion": matrix.to_json_dict(),
        "coverage": coverage.to_json_dict(),
        "answered_accuracy": answered_accuracy.to_json_dict(),
        "correct_abstentions": correct_abstentions.to_json_dict(),
        "risk_coverage_curve": [
            {
                "confidence_threshold": round(p.threshold, 4),
                "coverage": round(p.coverage, 4),
                "answered": p.answered,
                "errors": p.errors,
                "risk": round(p.risk, 4),
            }
            for p in curve
        ],
        "aurc": round(area, 4),
        "answerable": len(rows),
        "structurally_unanswerable": unanswerable,
        "passage_anchoring": anchor.to_json_dict(),
    }
    return result


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


async def run_retrieval(
    session: SnapshotSession, sources: Sequence[str] = RETRIEVAL_SOURCES
) -> AxisResult:
    items = gold_items("retrieval")
    result = AxisResult(name="retrieval", n_gold=len(items))
    hits = {k: 0 for k in RECALL_K}
    scored = 0
    ranks: list[int] = []

    connectors = [create_connector(name, snapshots=session) for name in sources]
    try:
        for item in items:
            query = str(item["query"])
            expected = normalize_doi(str(item["expect_doi"]))
            try:
                found = await search(
                    query, connectors=connectors, limit=max(RECALL_K), since=None
                )
            except SnapshotMissingError as exc:
                result.skipped.append(f"{query[:48]}: {exc.source} snapshot missing")
                continue
            scored += 1
            dois = [normalize_doi(record.DOI) for record in found.records]
            position = dois.index(expected) + 1 if expected in dois else 0
            if position:
                ranks.append(position)
            for k in RECALL_K:
                if position and position <= k:
                    hits[k] += 1
    finally:
        for connector in connectors:
            await connector.aclose()

    recall = {k: wilson(hits[k], scored) for k in RECALL_K}
    mrr = sum(1.0 / r for r in ranks) / scored if scored else 0.0

    result.lines.extend(
        [
            "RETRIEVAL: recall@k over known-item queries",
            "",
            "  Each query is the exact title of a real paper and the target is that paper's DOI.",
            "  A search that cannot find a paper when handed its exact title will not find it",
            "  from a vaguer one, so this is the floor, not the bar.",
            "",
            f"  {'k':>3}  {'hits':>7}  95% Wilson",
        ]
        + [f"  {k:>3}  {recall[k].fraction():>7}  {recall[k].rate()}" for k in RECALL_K]
        + [
            "",
            f"  MRR  {mrr:.3f}   (0 for a query whose target never appears)",
            f"  sources: {', '.join(sources)}, deduplicated and ranked",
        ]
    )
    result.data = {
        "recall_at_k": {str(k): recall[k].to_json_dict() for k in RECALL_K},
        "mrr": round(mrr, 6),
        "sources": list(sources),
    }
    return result


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def _record(side: Mapping[str, Any]) -> CSLRecord:
    year = side.get("year")
    return CSLRecord(
        title=str(side.get("title") or ""),
        DOI=str(side.get("doi") or ""),
        source=str(side.get("source") or ""),
        issued=CSLDate(year=int(year)) if isinstance(year, int) else None,
        author=[CSLName(family=str(side["first_author"]))] if side.get("first_author") else [],
    )


def run_dedup() -> AxisResult:
    """Dedup is pure computation over the labeled pairs: no source, no snapshot, no network."""
    items = gold_items("dedup")
    result = AxisResult(name="dedup", n_gold=len(items))
    matrix = Confusion(("same", "different"))

    for item in items:
        gold = str(item["label"])
        left = _record(item["a"])
        right = _record(item["b"])
        merged = dedupe([left, right])
        predicted = "same" if len(merged.records) == 1 else "different"
        matrix.add(gold, predicted)

    false_merge = matrix.counts["different"]["same"]
    false_split = matrix.counts["same"]["different"]
    fm = wilson(false_merge, matrix.gold_total("different"))
    fs = wilson(false_split, matrix.gold_total("same"))

    result.lines.extend(
        [
            "DEDUP: pair accuracy over labeled pairs",
            "",
            "  Confusion matrix",
            *[f"    {line}" for line in matrix.render()],
            "",
            f"  pair accuracy                  {matrix.accuracy().fraction():>7}   "
            f"{matrix.accuracy().rate()}",
            "",
            "  The two error directions, which are NOT equally bad:",
            "",
            f"    FALSE MERGE (gold different -> same)   {fm.fraction():>7}   {fm.rate()}",
            "      Two distinct papers collapsed into one. This DESTROYS DATA: one of the two",
            "      records is gone, its DOI no longer appears in the result set, and no",
            "      downstream step can recover it. A systematic review that false-merges has",
            "      silently dropped a study from its evidence base.",
            "",
            f"    FALSE SPLIT (gold same -> different)   {fs.fraction():>7}   {fs.rate()}",
            "      One paper left as two records. This is a cosmetic defect: the duplicate is",
            "      visible, a human can see it, and nothing is lost. It costs a reader's",
            "      attention, not a study.",
            "",
            "  The threshold is therefore tuned toward false splits, and this asymmetry is the",
            "  reason: dedupe requires DOI equality or a 0.90 normalized-title similarity, and",
            "  it refuses to merge records whose DOIs conflict outright.",
        ]
    )
    result.data = {
        "confusion": matrix.to_json_dict(),
        "false_merge": fm.to_json_dict(),
        "false_split": fs.to_json_dict(),
    }
    return result


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def run_axes(
    axes: Sequence[str],
    session: SnapshotSession,
    *,
    retrieval_sources: Sequence[str] = RETRIEVAL_SOURCES,
) -> list[AxisResult]:
    results: list[AxisResult] = []
    for axis in axes:
        if axis == "identity":
            results.append(await run_identity(session))
        elif axis == "status":
            results.append(await run_status(session))
        elif axis == "accessibility":
            results.append(await run_accessibility(session))
        elif axis == "faithfulness":
            results.append(await run_faithfulness(session))
        elif axis == "retrieval":
            results.append(await run_retrieval(session, retrieval_sources))
        elif axis == "dedup":
            results.append(run_dedup())
        else:  # pragma: no cover - argparse constrains the choices
            raise SystemExit(f"unknown axis {axis!r}")
    return results


def render(results: Sequence[AxisResult], mode: str) -> str:
    """The human report. No clock, no duration, no ordering by completion (D15)."""
    out: list[str] = [
        "=" * 78,
        "RESEARCHER EVIDENCE KERNEL: PER-AXIS BENCHMARKS",
        "=" * 78,
        "",
        f"core version    {CORE_VERSION}",
        f"mode            {mode} (offline replay from snapshots; no network)"
        if mode == "replay"
        else f"mode            {mode} (LIVE: this run hit the network and rewrote snapshots)",
        "intervals       95% Wilson score intervals, never the normal approximation",
        "",
    ]
    for result in results:
        out.append("-" * 78)
        out.extend(result.lines)
        out.append("")
        if result.skipped:
            out.append(f"  !! SKIPPED {len(result.skipped)} of {result.n_gold} GOLD ITEMS !!")
            out.append("     A skipped item has no snapshot. It is NOT scored, and it is NOT")
            out.append("     silently dropped: every number above is over the scored items only.")
            for line in result.skipped[:20]:
                out.append(f"       - {line}")
            if len(result.skipped) > 20:
                out.append(f"       ... and {len(result.skipped) - 20} more")
        else:
            out.append(f"  scored {result.scored}/{result.n_gold} gold items, 0 skipped")
        out.append("")

    total_skipped = sum(len(r.skipped) for r in results)
    out.append("=" * 78)
    out.append("SUMMARY")
    out.append("=" * 78)
    for result in results:
        out.append(
            f"  {result.name:<14} {result.scored:>4}/{result.n_gold:<4} scored"
            f"   {len(result.skipped):>3} skipped"
        )
    out.append("")
    if total_skipped:
        out.append(f"  {total_skipped} GOLD ITEMS WERE SKIPPED FOR MISSING SNAPSHOTS.")
        out.append("  The reported numbers do not cover them. Re-record with --record.")
    else:
        out.append("  Every gold item was scored. No snapshot was missing.")
    out.append("")
    out.append("  What these n can and cannot certify (D17): certifying a refusal-grade FPR")
    out.append("  below 0.10 at 95% confidence takes 0 errors in n >= 29. A per-class n of 25")
    out.append("  cannot certify that, whatever it measures. See evals/BENCHMARKS.md, which")
    out.append("  states for each number whether it certifies anything at its n.")
    out.append("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_axes.py",
        description="Replay the gold sets over the evidence kernel and report the numbers.",
    )
    parser.add_argument(
        "--axis",
        action="append",
        choices=AXES,
        help="run only this axis (repeatable). Default: all of them.",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="LIVE MODE: hit the real APIs and write snapshots. Not deterministic, by "
        "definition. This is how evals/snapshots/ is created and refreshed.",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help=f"snapshot store to replay from or record into (default: {DEFAULT_SNAPSHOT_DIR})",
    )
    parser.add_argument(
        "--retrieval-sources",
        default=",".join(RETRIEVAL_SOURCES),
        help="comma-separated fan-out sources for the retrieval axis (default: "
        f"{','.join(RETRIEVAL_SOURCES)}). Changing this changes the SYSTEM being measured, "
        "so a number from a reduced source set is not comparable with the default one and "
        "must be labelled as what it is.",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--out", type=Path, help="write the report to this file as well as to stdout"
    )
    args = parser.parse_args(argv)

    set_polite_env()
    axes = list(dict.fromkeys(args.axis)) if args.axis else list(AXES)
    mode = "record" if args.record else "replay"
    session = session_for(mode, args.snapshot_dir)

    if mode == "replay" and not args.snapshot_dir.is_dir() and axes != ["dedup"]:
        print(
            f"No snapshot store at {args.snapshot_dir}. This runner never goes live on its "
            f"own: record one first with\n"
            f"    uv run --project core python evals/run_axes.py --record",
            file=sys.stderr,
        )
        return 2

    retrieval_sources = tuple(
        name.strip() for name in str(args.retrieval_sources).split(",") if name.strip()
    )
    results = asyncio.run(
        run_axes(axes, session, retrieval_sources=retrieval_sources)
    )

    if args.json:
        payload = {
            "core_version": CORE_VERSION,
            "mode": mode,
            "axes": [r.to_json_dict() for r in results],
            "skipped_total": sum(len(r.skipped) for r in results),
        }
        text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    else:
        text = render(results, mode)

    sys.stdout.write(text + "\n")
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")

    # A missing snapshot is a defect in the eval, and it exits nonzero so CI cannot go green
    # over a benchmark that quietly measured half its gold set.
    return 1 if any(r.skipped for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
