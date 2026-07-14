"""Tests for scripts/journal-lookup.py against the real journal database."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "journal-lookup.py"
REAL_DB = Path(__file__).resolve().parent.parent.parent / "references" / "journal-database.md"

# The database ships exactly this many profiles. An equality, not a floor: a
# profile silently appearing or vanishing is a regression either way.
EXPECTED_PROFILE_COUNT = 16


def run_script(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


# --------------------------------------------------------------------------
# Independent re-walk of the database, used to round-trip the real parser.
# Deliberately hand-written (no regex, no import of the script) so that a bug
# in load_journal_database cannot hide behind the same bug in the oracle.
# --------------------------------------------------------------------------
def independent_parse(path: Path) -> dict:
    """Re-derive {lowercased name: {field: value}} by walking the markdown by hand."""
    profiles = {}
    owner = None       # heading currently collecting bullets
    pending_h2 = None  # H2 that becomes a profile only if bullets follow directly
    fields = {}

    def commit():
        nonlocal owner, fields
        if owner and fields:
            record = {"name": owner}
            record.update(fields)
            profiles[owner.lower()] = record
        owner, fields = None, {}

    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("### "):
            commit()
            pending_h2 = None
            owner = line[4:].strip()
        elif line.startswith("## "):
            commit()
            pending_h2 = line[3:].strip()
        elif line.startswith("- **"):
            if owner is None and pending_h2:
                owner = pending_h2
                pending_h2 = None
            if owner is None:
                continue
            body = line[len("- **"):]
            key_raw, sep, rest = body.partition("**")
            if not sep:
                continue
            key = key_raw.strip().rstrip(":")
            value = rest.lstrip()
            if value.startswith(":"):
                value = value[1:]
            value = value.strip()
            if not key or not value:
                continue
            fields[key.lower().replace(" ", "_")] = value

    commit()
    return profiles


def test_database_loads_all_profiles(journal_lookup):
    db = journal_lookup.load_journal_database()
    assert len(db) == EXPECTED_PROFILE_COUNT
    # The five leaf-H2 publishers that the old H3-only parser silently dropped:
    for name in ("wiley journals", "taylor & francis", "plos one", "science (aaas)", "mdpi journals"):
        assert name in db, f"missing leaf-H2 profile: {name}"


def test_database_round_trips_against_independent_walk(journal_lookup):
    """Every profile, every field, byte-identical: no missing, no extra, no mangled.

    Spot-checking three journals let a value-mangling regression on the other
    thirteen through unnoticed.
    """
    expected = independent_parse(REAL_DB)
    actual = journal_lookup.load_journal_database()

    assert len(expected) == EXPECTED_PROFILE_COUNT, "the oracle itself drifted from the DB"
    assert set(actual) == set(expected), (
        f"profile names differ: missing={set(expected) - set(actual)}, "
        f"extra={set(actual) - set(expected)}"
    )
    for name in expected:
        assert actual[name] == expected[name], f"field values mangled for {name}"


def test_fields_actually_parse(journal_lookup):
    """The old regex expected '**Field**:' while the DB writes '**Field:**';
    zero fields parsed. The real DB exercises '**Field:**' here; the other form
    is exercised against a synthetic fixture in test_alternate_bold_colon_form."""
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


# --------------------------------------------------------------------------
# db_path parameter + the alternate bullet form the real DB never uses
# --------------------------------------------------------------------------
SYNTHETIC_DB = """# Synthetic Database

## Group Publisher

### Alpha Journal
- **Class**: `alpha`
- **Word limit**: 5000 words

## Leaf Journal

- **Citation**: Numbered, [1]
- **Figures:** PNG only
"""


def test_load_journal_database_honours_db_path(journal_lookup, tmp_path):
    """The db_path parameter had zero coverage: nothing proved it was read at all."""
    fixture = tmp_path / "synthetic.md"
    fixture.write_text(SYNTHETIC_DB, encoding="utf-8")

    db = journal_lookup.load_journal_database(db_path=fixture)

    assert set(db) == {"alpha journal", "leaf journal"}, "db_path was ignored or misparsed"
    assert "group publisher" not in db, "group H2 wrongly parsed as a profile"


def test_alternate_bold_colon_form_parses(journal_lookup, tmp_path):
    """'- **Field**: value' must parse as well as '- **Field:** value'.

    The docstring claimed both forms parse but no test ever executed the first
    form: the real DB uses only '- **Field:**'.
    """
    fixture = tmp_path / "synthetic.md"
    fixture.write_text(SYNTHETIC_DB, encoding="utf-8")
    db = journal_lookup.load_journal_database(db_path=fixture)

    alpha = db["alpha journal"]
    assert alpha["class"] == "`alpha`"            # **Field**: form
    assert alpha["word_limit"] == "5000 words"    # **Field**: form
    leaf = db["leaf journal"]
    assert leaf["citation"] == "Numbered, [1]"    # **Field**: form
    assert leaf["figures"] == "PNG only"          # **Field:** form


def test_missing_db_path_returns_empty(journal_lookup, tmp_path):
    assert journal_lookup.load_journal_database(db_path=tmp_path / "nope.md") == {}


# --------------------------------------------------------------------------
# Null-field regression lock: absence, not just presence
# --------------------------------------------------------------------------
def test_absent_fields_are_absent_from_the_record(journal_lookup):
    """Parse level: a record carries only the fields its DB entry actually has."""
    db = journal_lookup.load_journal_database()
    wiley = db["wiley journals"]
    assert set(wiley) == {"name", "submission", "citation", "figures", "required_sections"}
    for absent in ("class", "word_limit", "abstract", "page_limit", "references"):
        assert absent not in wiley, f"fabricated field on Wiley: {absent}"


def test_absent_fields_are_not_rendered(journal_lookup):
    """Render level: format_result must not invent a placeholder for a missing field.

    Guards against a `info.get(key, "N/A")` style regression, which would print
    'LaTeX Class: N/A' for a publisher whose entry has no class.
    """
    db = journal_lookup.load_journal_database()
    rendered = journal_lookup.format_result("wiley journals", db["wiley journals"])

    assert "LaTeX Class" not in rendered
    assert "Word Limit" not in rendered
    assert "N/A" not in rendered
    assert "None" not in rendered
    # Every label that IS printed must correspond to a key the record carries.
    for key, label in journal_lookup.FIELD_LABELS.items():
        if f"  {label}: " in rendered:
            assert key in db["wiley journals"], f"rendered a label for absent field: {key}"


def test_no_placeholder_leak_in_stdout():
    """End to end: running the script on Wiley emits no N/A and no LaTeX Class line."""
    result = run_script("Wiley")
    assert result.returncode == 0
    assert "Wiley Journals" in result.stdout
    assert "LaTeX Class" not in result.stdout
    assert "N/A" not in result.stdout
    assert "None" not in result.stdout


def test_no_placeholder_leak_in_json():
    result = run_script("Wiley", "--format", "json")
    assert result.returncode == 0
    wiley = json.loads(result.stdout)["matches"]["wiley journals"]
    assert "class" not in wiley
    assert "N/A" not in json.dumps(wiley)


# --------------------------------------------------------------------------
# Fuzzy matches must be labeled as guesses, never as database hits
# --------------------------------------------------------------------------
def test_search_separates_matches_from_suggestions(journal_lookup):
    db = journal_lookup.load_journal_database()

    matches, suggestions = journal_lookup.search_journals("PLOS ONE", db)
    assert [name for name, _ in matches] == ["plos one"]
    assert suggestions == []

    # Absent journal that merely shares two words with a real profile.
    matches, suggestions = journal_lookup.search_journals("Journal of Machine Learning Research", db)
    assert matches == [], "a word-overlap guess was reported as a database hit"
    assert [name for name, _ in suggestions] == ["machine learning (springer)"]

    # Substring hit plus a word-overlap guess: the two must not be conflated.
    matches, suggestions = journal_lookup.search_journals("IEEE Transactions on Neural Networks", db)
    assert [name for name, _ in matches] == ["ieee transactions"]
    assert [name for name, _ in suggestions] == ["neural networks (elsevier)"]


def test_exact_match_sorts_ahead_of_substring_match(journal_lookup):
    db = journal_lookup.load_journal_database()
    matches, _ = journal_lookup.search_journals("IEEE Transactions", db)
    assert matches[0][0] == "ieee transactions"


def test_fuzzy_only_query_is_not_reported_as_a_hit():
    """The absent 'Journal of Machine Learning Research' used to print the full
    Machine Learning (Springer) profile at exit 0, with no caveat."""
    result = run_script("Journal of Machine Learning Research")
    assert result.returncode == 1
    assert "not found in the local database" in result.stdout
    assert "Closest matches (not exact database entries)" in result.stdout
    assert "Machine Learning (Springer)" in result.stdout
    # The guess must NOT be dressed up as this journal's requirements.
    assert "svjour3" not in result.stdout
    assert "Word Limit" not in result.stdout


def test_fuzzy_suggestion_is_labeled_alongside_a_real_match():
    result = run_script("IEEE Transactions on Neural Networks")
    assert result.returncode == 0
    assert "IEEE Transactions" in result.stdout
    heading = result.stdout.index("Closest matches (not exact database entries)")
    # The Elsevier guess appears only under the caveat heading, never above it.
    assert "Neural Networks (Elsevier)" not in result.stdout[:heading]
    assert "Neural Networks (Elsevier)" in result.stdout[heading:]


def test_json_separates_matches_from_suggestions():
    result = run_script("IEEE Transactions on Neural Networks", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["query"] == "IEEE Transactions on Neural Networks"
    assert list(payload["matches"]) == ["ieee transactions"]
    assert list(payload["suggestions"]) == ["neural networks (elsevier)"]
    assert payload["matches"]["ieee transactions"]["abstract"] == "Max 250 words"


def test_json_hit_carries_full_profile():
    result = run_script("PLOS ONE", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    plos = payload["matches"]["plos one"]
    assert plos["name"] == "PLOS ONE"
    assert "Vancouver" in plos["citation"]
    assert payload["suggestions"] == {}


def test_json_miss_is_valid_json_and_exits_nonzero():
    result = run_script("Journal of Nonexistent Studies Quarterly", "--format", "json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["matches"] == {}
    assert payload["suggestions"] == {}
    assert "author guidelines" in payload["note"]


def test_json_fuzzy_only_miss_reports_suggestions_and_exits_nonzero():
    result = run_script("Journal of Machine Learning Research", "--format", "json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["matches"] == {}
    assert list(payload["suggestions"]) == ["machine learning (springer)"]
    assert "not in the local database" in payload["note"]


# --------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------
def test_list_works_without_positional():
    result = run_script("--list")
    assert result.returncode == 0
    assert f"Journals in database ({EXPECTED_PROFILE_COUNT})" in result.stdout
    assert "PLOS ONE" in result.stdout


def test_lookup_prints_full_fields():
    result = run_script("Nature family")
    assert result.returncode == 0
    assert "Word Limit" in result.stdout
    assert "Required" in result.stdout  # a field outside the old fixed allow-list


def test_missing_journal_suggests_without_web_claim():
    result = run_script("Journal of Nonexistent Studies Quarterly")
    assert result.returncode == 1
    assert "not found" in result.stdout
    assert "author guidelines" in result.stdout
    assert "Closest matches" not in result.stdout  # nothing to suggest, so claim nothing
