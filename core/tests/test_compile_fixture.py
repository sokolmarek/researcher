"""Integration test for `researcher compile` against the seeded-defect fixture worktree.

The acceptance gate (M3.2): the defects fixture must produce exactly one of each defect class,
the clean sibling must pass with zero diagnostics, and two runs must be byte-identical (D15).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researcher_core.cli import main

FIXTURE = Path(__file__).resolve().parents[1].parent / "evals" / "fixtures" / "lineage-defects"


def run_compile(manuscript: Path, capsys) -> dict:
    code = main(["compile", "--manuscript", str(manuscript), "--json"])
    out = capsys.readouterr().out
    return {"exit": code, "report": json.loads(out)}


@pytest.mark.skipif(not FIXTURE.is_dir(), reason="fixture not present")
def test_defects_fixture_fires_every_defect_code(capsys):
    result = run_compile(FIXTURE / "defects", capsys)
    report = result["report"]
    codes = sorted(d["code"] for d in report["diagnostics"])
    assert codes == ["C001", "C002", "C003", "C004", "C005", "C006"]
    assert report["verdict"] == "fail"
    assert result["exit"] == 1
    # every diagnostic is refusal-grade (none is an inconclusive line item)
    assert all(d["refusal_grade"] for d in report["diagnostics"])


@pytest.mark.skipif(not FIXTURE.is_dir(), reason="fixture not present")
def test_clean_sibling_passes_with_zero_diagnostics(capsys):
    result = run_compile(FIXTURE / "clean", capsys)
    report = result["report"]
    assert report["verdict"] == "pass"
    assert report["diagnostics"] == []
    assert report["counts"]["open_items"] == 0
    assert result["exit"] == 0


@pytest.mark.skipif(not FIXTURE.is_dir(), reason="fixture not present")
def test_compile_is_byte_identical_across_runs(capsys):
    main(["compile", "--manuscript", str(FIXTURE / "defects"), "--json"])
    first = capsys.readouterr().out
    main(["compile", "--manuscript", str(FIXTURE / "defects"), "--json"])
    second = capsys.readouterr().out
    assert first == second
