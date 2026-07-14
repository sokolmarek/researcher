"""Tests for scripts/journal-lookup.py against the real journal database."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "journal-lookup.py"


def test_database_loads_all_profiles(journal_lookup):
    db = journal_lookup.load_journal_database()
    assert len(db) >= 16
    # The five leaf-H2 publishers that the old H3-only parser silently dropped:
    for name in ("wiley journals", "taylor & francis", "plos one", "science (aaas)", "mdpi journals"):
        assert name in db, f"missing leaf-H2 profile: {name}"


def test_fields_actually_parse(journal_lookup):
    """The old regex expected '**Field**:' while the DB writes '**Field:**';
    zero fields parsed. Both forms must parse now."""
    db = journal_lookup.load_journal_database()
    nature = db["nature family"]
    assert nature.get("word_limit", "").startswith("~3000")
    assert "superscript" in nature.get("citation", "")
    ieee = db["generic ieee"]
    assert "IEEEtran" in ieee.get("class", "")
    assert ieee.get("bibliography") == "`IEEEtran.bst`"
    plos = db["plos one"]
    assert "Vancouver" in plos.get("citation", "")


def test_group_h2_headings_are_not_profiles(journal_lookup):
    db = journal_lookup.load_journal_database()
    for group in ("elsevier journals", "springer journals", "ieee journals", "acm journals"):
        assert group not in db, f"group heading wrongly parsed as a profile: {group}"


def test_list_works_without_positional():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--list"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0
    assert "Journals in database" in result.stdout
    assert "PLOS ONE" in result.stdout


def test_lookup_prints_full_fields():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "Nature family"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0
    assert "Word Limit" in result.stdout
    assert "Required" in result.stdout  # a field outside the old fixed allow-list


def test_missing_journal_suggests_without_web_claim():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "Journal of Nonexistent Studies Quarterly"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 1
    assert "not found" in result.stdout
    assert "author guidelines" in result.stdout
