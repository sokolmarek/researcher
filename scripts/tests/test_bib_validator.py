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


def test_first_author_surname_forms(bib_validator):
    f = bib_validator.first_author_surname
    assert f("Doe, Jane and Smith, Ann") == "Doe"
    assert f("Jane Doe and Ann Smith") == "Doe"
    assert f("{van der Berg}, Hans") == "van der Berg"
    assert f("") == ""
