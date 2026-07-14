"""Record the verify-gold snapshot set from the live APIs.

Run it from the repo root when a gold case is added, or when a stored response has drifted
far enough that the live canary says the snapshot no longer reflects the world::

    uv run --project core python core/tests/snapshots/verify-gold/record.py

It drives the real ``verify.py`` and ``status.py`` code paths in RECORD mode over the cases
in ``cases.json`` and ``status-cases.json``, so exactly the requests the offline tests replay
are the ones that get recorded, no more and no less. The ``retrieved_at`` timestamp is pinned
to the value in the case files, which keeps a re-record byte-identical when the API response
has not changed (D15).

This script is the ONLY thing in the repo that calls a live API outside an opt-in ``-m live``
test. It is never imported by the test suite.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

GOLD_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(GOLD_ROOT.parent.parent))  # core/, so `researcher_core` imports

from researcher_core.connectors import create_connector  # noqa: E402
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore  # noqa: E402
from researcher_core.status import check_status_async  # noqa: E402
from researcher_core.verify import ReferenceClaim, verify_claim_async  # noqa: E402


async def main() -> int:
    cases = json.loads((GOLD_ROOT / "cases.json").read_text(encoding="utf-8"))
    status_cases = json.loads((GOLD_ROOT / "status-cases.json").read_text(encoding="utf-8"))

    session = SnapshotSession(
        SnapshotStore(GOLD_ROOT),
        SnapshotMode.RECORD,
        retrieved_at=cases["recorded_at"],
    )
    connectors = {
        name: create_connector(name, snapshots=session)
        for name in ("openalex", "crossref", "datacite", "semantic_scholar")
    }

    try:
        for case in cases["cases"]:
            if case.get("inject_source_error"):
                # An outage cannot be recorded: the error is injected in the test, over the
                # snapshots the clean version of the same claim already recorded.
                print(f"--  {case['name']:<36} (source error injected at test time, not recorded)")
                continue
            claim = ReferenceClaim.from_mapping(case["claim"])
            selected = [connectors[n] for n in case["sources"]]
            entry = await verify_claim_async(claim, selected)
            flag = "ok " if entry.verdict == case["expected"] else "DIFF"
            print(
                f"{flag} {case['name']:<36} {entry.verdict:<13} "
                f"(expected {case['expected']}) {entry.decision.reason[:70]}"
            )

        print()
        for case in status_cases["cases"]:
            selected = [connectors[n] for n in status_cases["sources"]]
            entry = await check_status_async(case["doi"], selected)
            flag = "ok " if entry.verdict == case["expected"] else "DIFF"
            print(
                f"{flag} {case['doi']:<34} {entry.verdict:<22} "
                f"(expected {case['expected']}) {entry.reason[:50]}"
            )
    finally:
        for connector in connectors.values():
            await connector.aclose()

    store = SnapshotStore(GOLD_ROOT)
    print(f"\nrecorded {store.count()} snapshots under {GOLD_ROOT}")
    for source in store.sources():
        print(f"  {source}: {store.count(source)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
