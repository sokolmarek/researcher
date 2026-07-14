"""Offline tests for scripts/bib-validator.py (brace-aware parser + verdicts)."""

import re

COMPACT_SAMPLE = """
@article{mehari2022ssl,
  title={Self-supervised representation learning from 12-lead ECG data},
  author={Mehari, Temesgen and Strodthoff, Nils},
  journal={Computers in Biology and Medicine}, volume={141}, pages={105114}, year={2022},
  doi={10.1016/j.compbiomed.2021.105114}}

@article{sarkar2022ssl,
  title={Self-Supervised ECG Representation Learning for Emotion Recognition},
  author={Sarkar, Pritam and Etemad, Ali},
  journal={IEEE Transactions on Affective Computing}, volume={13}, number={3}, pages={1541--1554}, year={2022},
  doi={10.1109/taffc.2020.3014842}}
"""


def test_compact_entries_parse(bib_validator):
    entries = bib_validator.parse_bib(COMPACT_SAMPLE)
    assert len(entries) == 2
    keys = {e["key"] for e in entries}
    assert keys == {"mehari2022ssl", "sarkar2022ssl"}
    first = next(e for e in entries if e["key"] == "mehari2022ssl")
    assert first["doi"] == "10.1016/j.compbiomed.2021.105114"
    assert first["title"] == "Self-supervised representation learning from 12-lead ECG data"
    assert first["year"] == "2022"


def test_citation_audit_example_parses_all_ten(bib_validator, repo_root):
    """The showcased bibliography (compact }}-terminated entries) must fully parse."""
    example = repo_root / "examples" / "research-verification" / "citation-audit.md"
    text = example.read_text(encoding="utf-8")
    blocks = re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL)
    bib_block = next(b for b in blocks if "@article" in b)
    entries = bib_validator.parse_bib(bib_block)
    assert len(entries) == 10
    keys = {e["key"] for e in entries}
    assert "kessler2021cmae" in keys  # the seeded fake
    for entry in entries:
        assert entry.get("doi"), f"{entry['key']} lost its DOI in parsing"
        assert entry.get("title"), f"{entry['key']} lost its title in parsing"


def test_nested_braces_not_truncated(bib_validator):
    entries = bib_validator.parse_bib(
        "@article{key1,\n  title={A {Nested} Title with {Deep {Braces}}},\n  year={2020},\n}"
    )
    assert entries[0]["title"] == "A {Nested} Title with {Deep {Braces}}"


def test_quoted_and_bare_values(bib_validator):
    entries = bib_validator.parse_bib(
        '@article{key2, author = "Doe, Jane", year = 2020, pages = {1--10}}'
    )
    entry = entries[0]
    assert entry["author"] == "Doe, Jane"
    assert entry["year"] == "2020"
    assert entry["pages"] == "1--10"


def test_string_concatenation(bib_validator):
    entries = bib_validator.parse_bib(
        '@article{key3, title = "Part one " # "and part two", year = {1999}}'
    )
    assert entries[0]["title"] == "Part one and part two"


def test_comment_preamble_string_skipped(bib_validator):
    text = """
@comment{this is not an entry}
@string{jbhi = {IEEE Journal of Biomedical and Health Informatics}}
@preamble{"\\newcommand{\\x}{y}"}
@article{real1, title={Real}, year={2021}}
"""
    entries = bib_validator.parse_bib(text)
    assert [e["key"] for e in entries] == ["real1"]


def test_torture_fixture_file_parses(bib_validator, fixtures_dir):
    """The torture fixture FILE: every hard case in one .bib, nothing truncated."""
    entries = bib_validator.parse_bib(fixtures_dir / "torture.bib")

    assert len(entries) == 5, "the @comment/@preamble/@string blocks must yield no entries"
    assert [e["key"] for e in entries] == [
        "nested2020", "quoted2021", "bare2022", "compact2023", "trailing2024",
    ]

    by_key = {e["key"]: e for e in entries}

    # Nested braces, and a comma inside a braced value, survive whole.
    assert by_key["nested2020"]["title"] == "A {Nested {Deep}} Title, with comma"
    assert by_key["nested2020"]["journal"] == "Journal of Balanced Braces"

    # A quoted value carrying BOTH a comma and braces is not cut at either.
    assert by_key["quoted2021"]["title"] == "Commas, {Braces}, and Quotes All in One Value"
    assert by_key["quoted2021"]["author"] == "van der Berg, Hans"
    assert by_key["quoted2021"]["year"] == "2021"  # bare numeric

    # Bare numeric and bare macro values.
    assert by_key["bare2022"]["volume"] == "26"
    assert by_key["bare2022"]["journal"] == "jbhi"  # unexpanded @string macro name

    # Compact entry closed by }} on its last field line.
    assert by_key["compact2023"]["type"] == "inproceedings"
    assert by_key["compact2023"]["booktitle"] == "Proceedings of Compactness"
    assert by_key["compact2023"]["doi"] == "10.1234/compact"

    # Trailing comma before the closing brace.
    assert by_key["trailing2024"]["publisher"] == "Addison-Wesley"
    assert by_key["trailing2024"]["doi"] == "10.1234/trailing"

    # No field value truncated: every entry keeps a full title, year and DOI, and
    # no value ends on a dangling separator.
    for entry in entries:
        for field in ("title", "author", "year", "doi"):
            assert entry.get(field), f"{entry['key']} lost its {field}"
        for name, value in entry.items():
            assert not value.endswith(("{", ",", "\\")), f"{entry['key']}.{name} looks truncated"

    # The skipped blocks leaked nothing: no entry inherited @comment/@preamble text.
    blob = " ".join(v for e in entries for v in e.values())
    assert "noopsort" not in blob
    assert "Not an entry" not in blob


def test_check_duplicates_can_be_deselected(bib_validator, tmp_path, capsys):
    """Duplicates are a selectable check like its siblings, not an unconditional one."""
    bib = tmp_path / "dupes.bib"
    bib.write_text(
        "@article{dup, title={A}, year={2020}, doi={10.1/x}}\n"
        "@article{dup, title={B}, year={2021}, doi={10.1/x}}\n",
        encoding="utf-8",
    )
    errors = bib_validator.validate(
        str(bib), check_doi=False, check_retracted=False, check_fields=False,
        check_duplicates=False,
    )
    out = capsys.readouterr().out
    assert errors == 0
    assert "Duplicate" not in out


def test_duplicates_reported(bib_validator, tmp_path, capsys):
    bib = tmp_path / "dupes.bib"
    bib.write_text(
        "@article{dup, title={A}, year={2020}, doi={10.1/x}}\n"
        "@article{dup, title={B}, year={2021}, doi={10.1/x}}\n",
        encoding="utf-8",
    )
    errors = bib_validator.validate(
        str(bib), check_doi=False, check_retracted=False, check_fields=False
    )
    out = capsys.readouterr().out
    assert errors == 2
    assert "Duplicate citation key: dup" in out
    assert "Duplicate DOI: 10.1/x" in out


def _one_entry_bib(tmp_path):
    bib = tmp_path / "one.bib"
    bib.write_text(
        "@article{sample2020,\n"
        "  title={A Fine Paper},\n"
        "  author={Doe, Jane},\n"
        "  journal={Journal of Tests},\n"
        "  year={2020},\n"
        "  doi={10.1234/fine}}\n",
        encoding="utf-8",
    )
    return bib


def test_doi_404_is_error(bib_validator, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(bib_validator, "resolve_doi", lambda doi: ("not_found", None))
    errors = bib_validator.validate(str(_one_entry_bib(tmp_path)), check_fields=False)
    out = capsys.readouterr().out
    assert errors == 1
    assert "does not resolve (404" in out


def test_network_error_is_warning_not_error(bib_validator, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(bib_validator, "resolve_doi", lambda doi: ("error", None))
    errors = bib_validator.validate(str(_one_entry_bib(tmp_path)), check_fields=False)
    out = capsys.readouterr().out
    assert errors == 0
    assert "network error" in out


def test_metadata_match_ok(bib_validator, tmp_path, capsys, monkeypatch):
    metadata = {
        "title": ["A Fine Paper"],
        "author": [{"family": "Doe", "given": "Jane", "sequence": "first"}],
        "issued": {"date-parts": [[2020]]},
    }
    monkeypatch.setattr(bib_validator, "resolve_doi", lambda doi: ("ok", metadata))
    errors = bib_validator.validate(str(_one_entry_bib(tmp_path)), check_fields=False)
    out = capsys.readouterr().out
    assert errors == 0
    assert "mismatch" not in out.lower()
    assert "similarity" not in out.lower()


def test_title_and_author_mismatch_warn(bib_validator, tmp_path, capsys, monkeypatch):
    metadata = {
        "title": ["A Completely Different Subject Entirely Unrelated"],
        "author": [{"family": "Smith", "given": "Ann", "sequence": "first"}],
        "issued": {"date-parts": [[2019]]},
    }
    monkeypatch.setattr(bib_validator, "resolve_doi", lambda doi: ("ok", metadata))
    errors = bib_validator.validate(str(_one_entry_bib(tmp_path)), check_fields=False)
    out = capsys.readouterr().out
    assert errors == 0  # mismatches warn, they do not hard-fail
    assert "Title similarity" in out
    assert "surname mismatch" in out
    assert "Year mismatch" in out


def test_retraction_flagged(bib_validator, tmp_path, capsys, monkeypatch):
    metadata = {
        "title": ["A Fine Paper"],
        "author": [{"family": "Doe", "sequence": "first"}],
        "issued": {"date-parts": [[2020]]},
        "update-to": [{"label": "Retraction"}],
    }
    monkeypatch.setattr(bib_validator, "resolve_doi", lambda doi: ("ok", metadata))
    errors = bib_validator.validate(str(_one_entry_bib(tmp_path)), check_fields=False)
    out = capsys.readouterr().out
    assert errors == 1
    assert "RETRACTED" in out


def test_doi_verdicts_are_tri_state_and_named(bib_validator, tmp_path, capsys, monkeypatch):
    """A resolved DOI is STATED as confirmed, not inferred from silence, and a failed
    lookup is its own verdict rather than being laundered into a pass."""
    bib = tmp_path / "three.bib"
    bib.write_text(
        "@article{good2020, title={A Fine Paper}, author={Doe, Jane},\n"
        "  journal={Journal of Tests}, year={2020}, doi={10.1234/fine}}\n"
        "@article{nodoi2021, title={No Identifier}, author={Roe, Rick},\n"
        "  journal={Journal of Tests}, year={2021}}\n"
        "@article{offline2022, title={Unreachable}, author={Poe, Pat},\n"
        "  journal={Journal of Tests}, year={2022}, doi={10.1234/unreachable}}\n",
        encoding="utf-8",
    )
    metadata = {
        "title": ["A Fine Paper"],
        "author": [{"family": "Doe", "sequence": "first"}],
        "issued": {"date-parts": [[2020]]},
    }

    def fake_resolve(doi):
        return ("ok", metadata) if doi == "10.1234/fine" else ("error", None)

    monkeypatch.setattr(bib_validator, "resolve_doi", fake_resolve)
    errors = bib_validator.validate(str(bib), check_fields=False)
    out = capsys.readouterr().out

    assert errors == 0  # a resolution failure is a warning, never an entry error
    assert "DOI VERDICTS" in out
    assert "confirmed" in out
    assert "no-doi" in out
    assert "resolution-failed" in out
    # Each verdict lands on the right entry.
    lines = [line.strip() for line in out.splitlines()]
    assert any(l.startswith("confirmed") and "[good2020]" in l for l in lines)
    assert any(l.startswith("no-doi") and "[nodoi2021]" in l for l in lines)
    assert any(l.startswith("resolution-failed") and "[offline2022]" in l for l in lines)
    assert "1 confirmed, 1 no-doi, 1 resolution-failed" in out


def test_not_found_and_retracted_have_their_own_verdicts(bib_validator, tmp_path, capsys,
                                                         monkeypatch):
    monkeypatch.setattr(bib_validator, "resolve_doi", lambda doi: ("not_found", None))
    bib_validator.validate(str(_one_entry_bib(tmp_path)), check_fields=False)
    out = capsys.readouterr().out
    assert "not-found" in out
    assert "confirmed" not in out  # a 404 is never reported as a pass

    metadata = {
        "title": ["A Fine Paper"],
        "author": [{"family": "Doe", "sequence": "first"}],
        "issued": {"date-parts": [[2020]]},
        "update-to": [{"label": "Retraction"}],
    }
    monkeypatch.setattr(bib_validator, "resolve_doi", lambda doi: ("ok", metadata))
    bib_validator.validate(str(_one_entry_bib(tmp_path)), check_fields=False)
    out = capsys.readouterr().out
    assert "retracted  [sample2020]" in out.lower()


def test_first_author_surname_forms(bib_validator):
    f = bib_validator.first_author_surname
    assert f("Doe, Jane and Smith, Ann") == "Doe"
    assert f("Jane Doe and Ann Smith") == "Doe"
    assert f("{van der Berg}, Hans") == "van der Berg"
    assert f("") == ""
