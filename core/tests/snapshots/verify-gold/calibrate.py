"""Produce the numbers in core/CALIBRATION.md.

Two measurements, one offline and one live:

    uv run --project core python core/tests/snapshots/verify-gold/calibrate.py
        Replays the gold subset in this directory under several threshold settings and prints
        the per-class outcomes plus the refusal-grade false-positive and false-negative rates
        for each. Offline, deterministic, and the source of every axis (a) number in
        CALIBRATION.md.

    uv run --project core python core/tests/snapshots/verify-gold/calibrate.py --status-live
        Additionally classifies all 120 DOIs of evals/gold/status.yaml against the LIVE
        Crossref and OpenAlex APIs and prints the axis (b) confusion matrix. The full gold set
        is not snapshotted (only the 14 rows in status-cases.json are), so this arm needs the
        network and is not part of the offline suite.

Refusal-grade false positive: a reference that is NOT fabricated or wrong (gold verdict
verified or inconclusive) which the kernel calls unresolvable or mismatch. That is the
failure that accuses an honest researcher, and its rate is the number that matters most in
this file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

GOLD_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GOLD_ROOT.parents[3]
sys.path.insert(0, str(GOLD_ROOT.parents[1]))

from researcher_core.connectors import create_connector  # noqa: E402
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore  # noqa: E402
from researcher_core.status import check_status_async  # noqa: E402
from researcher_core.verify import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    REFUSAL_GRADE,
    ReferenceClaim,
    Thresholds,
    verify_claim_async,
)

VERDICTS = ("verified", "mismatch", "unresolvable", "inconclusive")
STATUS_VERDICTS = ("current", "corrected", "retracted", "expression-of-concern")


def wilson(successes: int, total: int) -> tuple[float, float]:
    """95% Wilson score interval for a proportion (D17 reports these, never bare rates)."""
    if total == 0:
        return (0.0, 1.0)
    z = 1.959963984540054
    phat = successes / total
    denom = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


SETTINGS: dict[str, Thresholds] = {
    "committed (verify.py)": DEFAULT_THRESHOLDS,
    "no preprint year relaxation": replace(
        DEFAULT_THRESHOLDS, preprint_year_tolerance=DEFAULT_THRESHOLDS.year_tolerance
    ),
    "no truncation rule": replace(DEFAULT_THRESHOLDS, truncation_min_chars=10_000),
    "title bar 0.90": replace(DEFAULT_THRESHOLDS, title_similarity=0.90),
    "surname check off": replace(DEFAULT_THRESHOLDS, require_first_author_surname=False),
    "one confirmation is enough": replace(DEFAULT_THRESHOLDS, min_confirmations=1),
}


async def run_axis_a(cases: list[dict[str, Any]]) -> None:
    session = SnapshotSession(SnapshotStore(GOLD_ROOT), SnapshotMode.REPLAY)

    for label, thresholds in SETTINGS.items():
        rows: list[tuple[str, str, str]] = []
        for case in cases:
            connectors = [create_connector(n, snapshots=session) for n in case["sources"]]
            if case.get("inject_source_error"):
                for connector in connectors:
                    if connector.name == case["inject_source_error"]:
                        _make_it_fail(connector)
            claim = ReferenceClaim.from_mapping(case["claim"])
            entry = await verify_claim_async(
                claim, connectors, thresholds, check_status=False, check_accessibility=False
            )
            rows.append((case["name"], case["expected"], entry.verdict))
            for connector in connectors:
                await connector.aclose()

        correct = sum(1 for _, want, got in rows if want == got)
        refusal_fp = [
            (name, want, got)
            for name, want, got in rows
            if got in REFUSAL_GRADE and want not in REFUSAL_GRADE
        ]
        refusal_fn = [
            (name, want, got)
            for name, want, got in rows
            if want in REFUSAL_GRADE and got not in REFUSAL_GRADE
        ]
        honest = sum(1 for _, want, _ in rows if want not in REFUSAL_GRADE)
        guilty = sum(1 for _, want, _ in rows if want in REFUSAL_GRADE)
        lo, hi = wilson(len(refusal_fp), honest)

        print(f"\n### {label}")
        print(f"  accuracy               {correct}/{len(rows)}")
        print(
            f"  refusal-grade FP       {len(refusal_fp)}/{honest} "
            f"(95% Wilson {lo:.3f}-{hi:.3f})"
        )
        print(f"  refusal-grade FN       {len(refusal_fn)}/{guilty}")
        for name, want, got in rows:
            if want != got:
                mark = "  FP" if got in REFUSAL_GRADE and want not in REFUSAL_GRADE else "  --"
                print(f"  {mark} {name:<38} want {want:<13} got {got}")


def _make_it_fail(connector: Any) -> None:
    from researcher_core.connectors.base import SourceError, SourceErrorKind

    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise SourceError(
            connector.name, "timed out", kind=SourceErrorKind.TIMEOUT, endpoint="works"
        )

    connector.resolve_doi = boom
    connector.get_by_id = boom
    connector.search = boom
    connector.get_oa_pdf = boom


async def run_axis_b_live() -> None:
    """Classify all 120 DOIs of evals/gold/status.yaml against the live APIs."""
    text = (REPO_ROOT / "evals" / "gold" / "status.yaml").read_text(encoding="utf-8")
    items = re.findall(r'- doi: "([^"]+)"\n    expected: (\S+)', text)
    print(f"\n### axis (b): {len(items)} DOIs from evals/gold/status.yaml (LIVE)")

    session = SnapshotSession(SnapshotStore(GOLD_ROOT), SnapshotMode.LIVE)
    connectors = [create_connector(n, snapshots=session) for n in ("crossref", "openalex")]
    matrix: dict[tuple[str, str], int] = {}
    misses: list[tuple[str, str, str, str]] = []
    unchecked = conflicts = 0
    try:
        for doi, expected in items:
            entry = await check_status_async(doi, connectors)
            matrix[(expected, entry.verdict)] = matrix.get((expected, entry.verdict), 0) + 1
            if entry.verdict != expected:
                misses.append((doi, expected, entry.verdict, entry.reason))
            unchecked += 0 if entry.checked else 1
            conflicts += 1 if entry.conflict else 0
    finally:
        for connector in connectors:
            await connector.aclose()

    header = "gold vs predicted"
    print(f"\n  {header:<24}" + "".join(f"{v:>24}" for v in STATUS_VERDICTS))
    for gold in STATUS_VERDICTS:
        row = "".join(f"{matrix.get((gold, p), 0):>24}" for p in STATUS_VERDICTS)
        print(f"  {gold:<24}{row}")
    correct = sum(c for (g, p), c in matrix.items() if g == p)
    lo, hi = wilson(correct, len(items))
    print(f"\n  accuracy   {correct}/{len(items)} (95% Wilson {lo:.3f}-{hi:.3f})")
    print(f"  unchecked  {unchecked}")
    print(f"  conflicts  {conflicts}")
    for doi, want, got, reason in misses:
        print(f"    MISS {doi:<36} want {want:<22} got {got:<22} {reason[:60]}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-live", action="store_true", help="also run axis (b) live")
    args = parser.parse_args()

    cases = json.loads((GOLD_ROOT / "cases.json").read_text(encoding="utf-8"))["cases"]
    print(f"## axis (a): {len(cases)} gold cases, replayed offline")
    await run_axis_a(cases)
    if args.status_live:
        await run_axis_b_live()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
