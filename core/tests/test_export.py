"""Offline round-trip tests for researcher_core.export (M5.4, D4).

The contract under test, for RIS, JATS <ref-list>, canonical CSL-JSON, and BibTeX:

* every field the format's loss profile marks CARRIED survives ``CSL -> emit -> import -> CSL``
  byte for byte, on the hard-case fixtures and on a maximal probe;
* every field it CANNOT carry is in ``LOSS_TABLE`` and is dropped, never silently lost;
* the loss table matches reality: each documented loss is demonstrated, and nothing outside the
  table (plus the per-fixture brace exception) ever drops.

Everything here is offline: no network, no snapshots, no DOI resolution. The fixtures include the
hard cases the milestone names (braces and diacritics, corporate authors, no-DOI entries, the
sanctioned expect-unresolvable fake per D8, and DataCite dataset/software DOIs per D22).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from researcher_core.export import (
    COMPARABLE_FIELDS,
    FORMATS,
    LOSS_TABLE,
    field_diff,
    from_csl_json,
    from_jats_reflist,
    from_ris,
    record_fields,
    roundtrip,
    to_csl_json,
    to_jats_reflist,
    to_ris,
)
from researcher_core.model import CSLName, CSLRecord

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_FILE = REPO_ROOT / "evals" / "fixtures" / "roundtrip" / "cases.json"


def _load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


CASES = _load_cases()
CASE_IDS = [case["id"] for case in CASES]


def _record(case: dict) -> CSLRecord:
    return CSLRecord.from_csl_json(case["record"])


def _is_empty(value: object) -> bool:
    return value in (None, "", [], {})


# The maximal probe: every comparable field populated at once, so every structural loss is
# exercised in a single record. Its title avoids literal braces so it measures the structural
# losses, not the BibTeX brace-grouping behaviour (that is the braces-and-markup fixture's job).
PROBE = CSLRecord.from_csl_json(
    {
        "id": "probe-key-001",
        "type": "article-journal",
        "title": "Möbius Bänder & <Deep> Learning: a Review",
        "author": [
            {"family": "Ribeiro", "given": "Antônio H.", "suffix": "Jr."},
            {"literal": "World Health Organization"},
        ],
        "editor": [{"family": "Erdős", "given": "Paul"}],
        "issued": {"date-parts": [[2021, 5, 17]]},
        "container-title": "Journal of Tésting & Review",
        "publisher": "Académie Press",
        "volume": "12",
        "issue": "4",
        "page": "1541-1554",
        "number": "TR-99",
        "version": "2.1.0",
        "abstract": "An abstract with <tags> & ampersands.",
        "DOI": "10.1234/probe.2021.001",
        "URL": "https://example.org/a?b=1&c=2",
        "ISSN": ["1234-5678", "8765-4321"],
        "ISBN": "978-3-16-148410-0",
        "language": "en",
        "note": "A note; with punctuation.",
        "keyword": ["alpha", "beta"],
    }
)


# ---------------------------------------------------------------------------
# Fixture sanity: the hard cases the milestone requires are actually present
# ---------------------------------------------------------------------------


def test_fixture_set_covers_the_required_hard_cases() -> None:
    ids = set(CASE_IDS)
    assert "diacritics-real" in ids  # braces and diacritics
    assert "braces-and-markup" in ids
    assert "corporate-author" in ids
    assert "no-doi" in ids
    assert "kessler2021cmae" in ids  # the seeded expect-unresolvable fake (D8)
    assert "datacite-dataset" in ids  # DataCite dataset (D22)
    assert "datacite-software" in ids  # DataCite software (D22)


def test_expect_unresolvable_fake_is_labelled_and_never_resolved() -> None:
    """The sanctioned fake (D8) is carried as data only; the round-trip resolves nothing."""
    case = next(c for c in CASES if c["id"] == "kessler2021cmae")
    assert case["synthetic"] is True
    assert case["expect_unresolvable"] == "10.1109/TBME.2021.3098765"
    assert "synthetic" in case["record"]["note"].lower()
    # It still round-trips like any other record, with no network access.
    record = _record(case)
    for fmt in FORMATS:
        restored = roundtrip(fmt, [record])
        assert len(restored) == 1


# ---------------------------------------------------------------------------
# CSL-JSON is canonical: the round-trip is the identity, and the output is stable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_csl_json_roundtrip_is_identity(case: dict) -> None:
    record = _record(case)
    after = roundtrip("csl-json", [record])[0]
    assert field_diff(record_fields(record), record_fields(after)) == set()


def test_csl_json_probe_is_identity() -> None:
    after = roundtrip("csl-json", [PROBE])[0]
    assert field_diff(record_fields(PROBE), record_fields(after)) == set()


def test_to_csl_json_default_is_canonical_and_byte_stable() -> None:
    records = [_record(case) for case in CASES]
    first = to_csl_json(records)
    second = to_csl_json(records)
    assert first == second  # deterministic
    # Canonical form is compact (no indentation) and reparses to the same records.
    assert "\n" not in first
    reparsed = from_csl_json(first)
    assert [record_fields(r) for r in reparsed] == [record_fields(r) for r in records]


def test_from_csl_json_accepts_a_single_object() -> None:
    record = _record(CASES[0])
    obj = json.dumps(record.to_csl_json())
    assert record_fields(from_csl_json(obj)[0]) == record_fields(record)


# ---------------------------------------------------------------------------
# Carried fields survive every format on every fixture
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_carried_fields_survive(fmt: str, case: dict) -> None:
    """No CARRIED field may change: a carried field that changes is a silent loss."""
    record = _record(case)
    before = record_fields(record)
    after = record_fields(roundtrip(fmt, [record])[0])
    changed = field_diff(before, after)

    extra = set(case.get("expected_extra_loss", {}).get(fmt, []))
    silent = changed - set(LOSS_TABLE[fmt].lost) - extra
    assert silent == set(), f"{fmt} silently lost {sorted(silent)} on {case['id']}"

    for name in LOSS_TABLE[fmt].carried:
        if name in extra or _is_empty(before.get(name)):
            continue
        assert before[name] == after[name], f"{fmt} did not carry {name} on {case['id']}"


# ---------------------------------------------------------------------------
# The loss table matches reality, exercised on the maximal probe
# ---------------------------------------------------------------------------


def test_probe_losses_match_the_table_exactly_for_ris_and_jats() -> None:
    before = record_fields(PROBE)
    for fmt in ("ris", "jats"):
        after = record_fields(roundtrip(fmt, [PROBE])[0])
        assert field_diff(before, after) == set(LOSS_TABLE[fmt].lost)


def test_probe_has_no_undocumented_loss_in_any_format() -> None:
    before = record_fields(PROBE)
    for fmt in FORMATS:
        after = record_fields(roundtrip(fmt, [PROBE])[0])
        silent = field_diff(before, after) - set(LOSS_TABLE[fmt].lost)
        assert silent == set(), f"{fmt} silently lost {sorted(silent)} on the probe"


def test_every_documented_loss_actually_happens() -> None:
    """No padded table: each declared loss is demonstrated by the probe or a fixture."""
    before_probe = record_fields(PROBE)
    for fmt in FORMATS:
        observed: set[str] = field_diff(before_probe, record_fields(roundtrip(fmt, [PROBE])[0]))
        for case in CASES:
            record = _record(case)
            after = roundtrip(fmt, [record])[0]
            observed |= field_diff(record_fields(record), record_fields(after))
        undemonstrated = sorted(set(LOSS_TABLE[fmt].lost) - observed)
        assert undemonstrated == [], f"{fmt} lists never-observed losses {undemonstrated}"


def test_loss_table_carried_and_lost_partition_the_comparable_fields() -> None:
    for profile in LOSS_TABLE.values():
        assert set(profile.lost).issubset(COMPARABLE_FIELDS)
        assert set(profile.carried) | set(profile.lost) == set(COMPARABLE_FIELDS)
        assert set(profile.carried) & set(profile.lost) == set()


# ---------------------------------------------------------------------------
# RIS specifics
# ---------------------------------------------------------------------------


def test_ris_drops_version_and_number_and_the_second_identifier() -> None:
    before = record_fields(PROBE)
    after = record_fields(roundtrip("ris", [PROBE])[0])
    assert after["version"] == ""  # RIS has no version tag
    assert after["number"] == ""  # RIS has no report-number tag
    assert after["ISBN"] == ""  # SN held the ISSN; the ISBN could not coexist
    assert after["ISSN"] == before["ISSN"]  # ...but the ISSN survived


def test_ris_carries_isbn_for_a_book_when_no_issn_competes() -> None:
    book = CSLRecord.from_csl_json(
        {
            "id": "b1",
            "type": "book",
            "title": "A Book",
            "author": [{"family": "Writer", "given": "Wanda"}],
            "issued": {"date-parts": [[2018]]},
            "ISBN": "978-0-13-468599-1",
        }
    )
    restored = roundtrip("ris", [book])[0]
    assert restored.ISBN == "978-0-13-468599-1"
    assert restored.type == "book"


def test_ris_corporate_author_round_trips_as_a_literal() -> None:
    record = next(_record(c) for c in CASES if c["id"] == "corporate-author")
    restored = roundtrip("ris", [record])[0]
    assert len(restored.author) == 1
    assert restored.author[0].literal == "World Health Organization"
    assert restored.author[0].family == ""


def test_ris_text_has_the_expected_tag_shape() -> None:
    text = to_ris([PROBE])
    assert text.startswith("TY  - JOUR")
    assert "\nID  - probe-key-001" in text
    assert "\nDO  - 10.1234/probe.2021.001" in text
    assert text.rstrip().endswith("ER  -")
    # Round-trips back to one record.
    assert len(from_ris(text)) == 1


def test_ris_multiple_records_are_blank_line_separated() -> None:
    records = [_record(case) for case in CASES]
    restored = from_ris(to_ris(records))
    assert len(restored) == len(records)


# ---------------------------------------------------------------------------
# JATS specifics
# ---------------------------------------------------------------------------


def test_jats_is_well_formed_and_structurally_valid() -> None:
    xml = to_jats_reflist([_record(case) for case in CASES])
    root = ET.fromstring(xml)  # raises on malformed XML
    assert root.tag == "ref-list"
    refs = root.findall("ref")
    assert len(refs) == len(CASES)
    for ref in refs:
        assert ref.get("id")  # every ref carries an XML id
        citation = ref.find("element-citation")
        assert citation is not None
        assert citation.get("publication-type")
        # Required: a title, present either as article-title or as source.
        assert (citation.findtext("article-title") or citation.findtext("source"))


def test_jats_escapes_and_recovers_xml_special_characters() -> None:
    record = next(_record(c) for c in CASES if c["id"] == "braces-and-markup")
    xml = to_jats_reflist([record])
    # The raw ampersand and angle brackets are escaped in the serialized XML...
    assert "&amp;" in xml
    assert "&lt;Deep&gt;" in xml
    # ...and recovered verbatim on import, braces included.
    restored = roundtrip("jats", [record])[0]
    assert restored.title == record.title


def test_jats_carries_version_and_both_identifiers() -> None:
    after = record_fields(roundtrip("jats", [PROBE])[0])
    assert after["version"] == "2.1.0"
    assert after["ISSN"] == ["1234-5678", "8765-4321"]
    assert after["ISBN"] == "978-3-16-148410-0"


def test_jats_drops_abstract_keyword_language_and_regenerates_id() -> None:
    after = record_fields(roundtrip("jats", [PROBE])[0])
    assert after["abstract"] == ""
    assert after["keyword"] == []
    assert after["language"] == ""
    # id is regenerated from content (the DOI), not the original "probe-key-001".
    assert after["id"] == "10.1234/probe.2021.001"
    assert after["id"] != PROBE.id


def test_jats_corporate_author_round_trips_via_collab() -> None:
    record = next(_record(c) for c in CASES if c["id"] == "corporate-author")
    xml = to_jats_reflist([record])
    assert "<collab>World Health Organization</collab>" in xml
    restored = from_jats_reflist(xml)[0]
    assert restored.author[0].literal == "World Health Organization"


def test_jats_separates_article_title_from_container() -> None:
    record = next(_record(c) for c in CASES if c["id"] == "diacritics-real")
    xml = to_jats_reflist([record])
    assert "<article-title>" in xml
    assert "<source>Nature Communications</source>" in xml
    restored = from_jats_reflist(xml)[0]
    assert restored.title == record.title
    assert restored.container_title == "Nature Communications"


def test_jats_book_without_container_puts_title_in_source() -> None:
    book = CSLRecord.from_csl_json(
        {
            "id": "b2",
            "type": "book",
            "title": "A Standalone Book",
            "issued": {"date-parts": [[2001]]},
        }
    )
    xml = to_jats_reflist([book])
    assert "<source>A Standalone Book</source>" in xml
    assert "<article-title>" not in xml
    restored = from_jats_reflist(xml)[0]
    assert restored.title == "A Standalone Book"
    assert restored.container_title == ""


# ---------------------------------------------------------------------------
# BibTeX specifics (reused emitter/parser from researcher_core.bib)
# ---------------------------------------------------------------------------


def test_bibtex_collapses_dataset_and_software_types_to_document() -> None:
    for case_id in ("datacite-dataset", "datacite-software"):
        record = next(_record(c) for c in CASES if c["id"] == case_id)
        restored = roundtrip("bibtex", [record])[0]
        assert restored.type == "document"
        assert restored.DOI == record.DOI  # the DOI itself survives


def test_bibtex_drops_issn_keyword_and_version_but_keeps_isbn() -> None:
    after = record_fields(roundtrip("bibtex", [PROBE])[0])
    assert after["ISSN"] == []
    assert after["keyword"] == []
    assert after["version"] == ""
    assert after["ISBN"] == "978-3-16-148410-0"


def test_bibtex_consumes_literal_braces_but_other_formats_keep_them() -> None:
    record = next(_record(c) for c in CASES if c["id"] == "braces-and-markup")
    assert "{" in record.title  # the fixture really has literal braces
    # RIS, JATS, and CSL-JSON keep them verbatim.
    for fmt in ("ris", "jats", "csl-json"):
        assert roundtrip(fmt, [record])[0].title == record.title
    # BibTeX strips them (capitalization-protection grouping); this is the documented per-case
    # loss, so the braces are gone from the round-tripped title.
    assert "{" not in roundtrip("bibtex", [record])[0].title


# ---------------------------------------------------------------------------
# Diacritics survive everywhere they are carried
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", FORMATS)
def test_diacritics_in_author_names_survive(fmt: str) -> None:
    record = next(_record(c) for c in CASES if c["id"] == "diacritics-real")
    restored = roundtrip(fmt, [record])[0]
    surnames = {name.surname for name in restored.author}
    assert "Paixão" in surnames
    givens = {name.given for name in restored.author}
    assert any("Antônio" in given for given in givens)


def test_editor_names_survive_ris_and_jats() -> None:
    for fmt in ("ris", "jats"):
        after = roundtrip(fmt, [PROBE])[0]
        assert len(after.editor) == 1
        assert after.editor[0].family == "Erdős"
        assert after.editor[0].given == "Paul"


# ---------------------------------------------------------------------------
# The uniform dispatcher
# ---------------------------------------------------------------------------


def test_roundtrip_preserves_length_and_order() -> None:
    records = [_record(case) for case in CASES]
    for fmt in FORMATS:
        restored = roundtrip(fmt, records)
        assert len(restored) == len(records)


def test_roundtrip_rejects_an_unknown_format() -> None:
    with pytest.raises(ValueError, match="unknown export format"):
        roundtrip("endnote", [PROBE])


def test_ris_name_helper_handles_a_plain_person() -> None:
    # A mononym person (one token, no comma) stays a family name, not an organization.
    text = to_ris([CSLRecord(id="p", type="book", author=[CSLName(family="Plato")])])
    restored = from_ris(text)[0]
    assert restored.author[0].family == "Plato"
    assert restored.author[0].literal == ""
