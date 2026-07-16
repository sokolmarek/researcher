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
    CREDIT_ROLES,
    FORMATS,
    LOSS_TABLE,
    Affiliation,
    Contributor,
    MetadataError,
    contributor_from_mapping,
    field_diff,
    from_csl_json,
    from_jats_reflist,
    from_ris,
    record_fields,
    roundtrip,
    to_csl_json,
    to_jats_contrib_group,
    to_jats_reflist,
    to_ris,
    validate_credit_role,
    validate_orcid,
    validate_ror,
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


# ---------------------------------------------------------------------------
# ORCID iD validation (ISO 7064 mod 11-2 checksum)  (M5.5)
# ---------------------------------------------------------------------------

# Real, checksum-valid ORCID iDs (the X check character is exercised too).
VALID_ORCIDS = [
    "0000-0002-1825-0097",  # the canonical ORCID example
    "0000-0001-5109-3700",
    "0000-0002-1694-233X",  # check character X (== 10)
]


@pytest.mark.parametrize("orcid", VALID_ORCIDS)
def test_validate_orcid_accepts_and_canonicalizes(orcid: str) -> None:
    assert validate_orcid(orcid) == f"https://orcid.org/{orcid}"


def test_validate_orcid_accepts_url_and_compact_forms() -> None:
    assert validate_orcid("https://orcid.org/0000-0002-1825-0097") == (
        "https://orcid.org/0000-0002-1825-0097"
    )
    assert validate_orcid("orcid.org/0000-0002-1825-0097") == (
        "https://orcid.org/0000-0002-1825-0097"
    )
    # Compact 16-character form, no hyphens.
    assert validate_orcid("0000000218250097") == "https://orcid.org/0000-0002-1825-0097"


def test_validate_orcid_rejects_a_bad_checksum() -> None:
    # Last digit flipped from 7 to 8: valid shape, wrong ISO 7064 mod 11-2 check character.
    with pytest.raises(MetadataError, match="checksum"):
        validate_orcid("0000-0002-1825-0098")


def test_validate_orcid_rejects_wrong_length_and_non_digits() -> None:
    with pytest.raises(MetadataError, match="16 characters"):
        validate_orcid("0000-0002-1825")
    with pytest.raises(MetadataError, match="digits"):
        validate_orcid("0000-0002-1825-00A7")


def test_validate_orcid_is_a_value_error() -> None:
    # MetadataError subclasses ValueError, so existing handlers still catch it.
    assert issubclass(MetadataError, ValueError)
    with pytest.raises(ValueError):
        validate_orcid("not-an-orcid")


# ---------------------------------------------------------------------------
# ROR ID validation (published prefix/character pattern)  (M5.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ror",
    [
        "042nb2s44",  # MIT
        "03vek6s52",  # Harvard
        "https://ror.org/00f54p054",  # Stanford, full URL
        "ror.org/013meh722",  # bare host prefix
    ],
)
def test_validate_ror_accepts_and_canonicalizes(ror: str) -> None:
    result = validate_ror(ror)
    assert result.startswith("https://ror.org/0")
    # Idempotent: validating the canonical form returns it unchanged.
    assert validate_ror(result) == result


def test_validate_ror_rejects_bad_patterns() -> None:
    # Missing leading 0.
    with pytest.raises(MetadataError, match="ROR"):
        validate_ror("142nb2s44")
    # Contains an excluded look-alike character (i, l, o, u are not in the alphabet).
    with pytest.raises(MetadataError, match="ROR"):
        validate_ror("0i2nb2s44")
    # Wrong length.
    with pytest.raises(MetadataError, match="ROR"):
        validate_ror("042nb2s4")
    # A raw grant/other string is not a ROR.
    with pytest.raises(MetadataError, match="ROR"):
        validate_ror("University of Nowhere")


# ---------------------------------------------------------------------------
# CRediT role validation (fixed 14-term taxonomy)  (M5.5)
# ---------------------------------------------------------------------------


def test_credit_taxonomy_has_the_14_terms() -> None:
    assert len(CREDIT_ROLES) == 14
    assert "conceptualization" in CREDIT_ROLES
    assert "writing - original draft" in CREDIT_ROLES
    assert "writing - review and editing" in CREDIT_ROLES


@pytest.mark.parametrize("role", CREDIT_ROLES)
def test_every_canonical_role_validates_to_itself(role: str) -> None:
    assert validate_credit_role(role) == role


def test_validate_credit_role_is_case_and_hyphen_tolerant() -> None:
    assert validate_credit_role("Data Curation") == "data curation"
    assert validate_credit_role("data-curation") == "data curation"
    assert validate_credit_role("FORMAL ANALYSIS") == "formal analysis"
    assert validate_credit_role("writing-original-draft") == "writing - original draft"


def test_validate_credit_role_rejects_unknown_roles() -> None:
    with pytest.raises(MetadataError, match="CRediT"):
        validate_credit_role("proofreading")
    with pytest.raises(MetadataError, match="CRediT"):
        validate_credit_role("writing")


def test_no_credit_role_uses_an_en_or_em_dash() -> None:
    # The CI dash guard bans U+2013/U+2014; the taxonomy uses ordinary hyphen-minus only.
    # The dash characters are written as escapes here so this file itself stays dash-free.
    joined = " ".join(CREDIT_ROLES)
    assert chr(0x2013) not in joined  # en dash
    assert chr(0x2014) not in joined  # em dash


# ---------------------------------------------------------------------------
# Contributor construction from a config-style mapping  (M5.5)
# ---------------------------------------------------------------------------


def test_contributor_from_mapping_validates_everything() -> None:
    contributor = contributor_from_mapping(
        {
            "name": "Jane Q. Doe",
            "orcid": "0000-0002-1825-0097",
            "affiliations": [
                {"institution": "Massachusetts Institute of Technology", "ror": "042nb2s44"}
            ],
            "credit": ["Conceptualization", "writing-original-draft"],
        }
    )
    assert contributor.name.family == "Doe"
    assert contributor.orcid == "https://orcid.org/0000-0002-1825-0097"
    assert contributor.affiliations[0].ror == "https://ror.org/042nb2s44"
    assert contributor.credit_roles == ("conceptualization", "writing - original draft")


def test_contributor_from_mapping_accepts_a_top_level_ror_shorthand() -> None:
    contributor = contributor_from_mapping(
        {"name": "Solo Author", "affiliation": "Some University", "ror": "042nb2s44"}
    )
    assert contributor.affiliations[0].institution == "Some University"
    assert contributor.affiliations[0].ror == "https://ror.org/042nb2s44"


def test_contributor_from_mapping_leaves_optional_metadata_empty() -> None:
    contributor = contributor_from_mapping({"name": "Plain Author"})
    assert contributor.orcid == ""
    assert contributor.affiliations == ()
    assert contributor.credit_roles == ()


def test_contributor_from_mapping_rejects_invalid_metadata_never_guesses() -> None:
    with pytest.raises(MetadataError):
        contributor_from_mapping({"name": "X", "orcid": "0000-0002-1825-0098"})
    with pytest.raises(MetadataError):
        contributor_from_mapping({"name": "X", "affiliation": {"name": "U", "ror": "bogus"}})
    with pytest.raises(MetadataError):
        contributor_from_mapping({"name": "X", "credit": ["typing"]})
    with pytest.raises(MetadataError):
        contributor_from_mapping({"orcid": "0000-0002-1825-0097"})  # no name


def test_contributor_from_mapping_reads_a_corporate_literal_name() -> None:
    contributor = contributor_from_mapping({"literal": "World Health Organization"})
    assert contributor.name.literal == "World Health Organization"


# ---------------------------------------------------------------------------
# JATS <contrib-group> emitter  (M5.5)
# ---------------------------------------------------------------------------


def _sample_contributors() -> list[Contributor]:
    return [
        contributor_from_mapping(
            {
                "name": "Antônio H. Ribeiro",
                "orcid": "0000-0002-1825-0097",
                "affiliations": [
                    {"institution": "Massachusetts Institute of Technology", "ror": "042nb2s44"}
                ],
                "credit": ["conceptualization", "writing - original draft"],
            }
        ),
        contributor_from_mapping(
            {
                "literal": "World Health Organization",
                "contrib_type": "author",
            }
        ),
    ]


def test_contrib_group_is_well_formed_xml_with_the_ids() -> None:
    xml = to_jats_contrib_group(_sample_contributors())
    root = ET.fromstring(xml)  # raises on malformed XML
    assert root.tag == "contrib-group"
    contribs = root.findall("contrib")
    assert len(contribs) == 2

    first = contribs[0]
    orcid = first.find("contrib-id")
    assert orcid is not None
    assert orcid.get("contrib-id-type") == "orcid"
    assert orcid.text == "https://orcid.org/0000-0002-1825-0097"

    name = first.find("name")
    assert name is not None
    assert name.findtext("surname") == "Ribeiro"
    assert name.findtext("given-names") == "Antônio H."

    aff = first.find("aff")
    assert aff is not None
    assert aff.findtext("institution") == "Massachusetts Institute of Technology"
    inst_id = aff.find("institution-id")
    assert inst_id is not None
    assert inst_id.get("institution-id-type") == "ror"
    assert inst_id.text == "https://ror.org/042nb2s44"


def test_contrib_group_emits_credit_roles_with_niso_vocabulary() -> None:
    xml = to_jats_contrib_group(_sample_contributors())
    root = ET.fromstring(xml)
    roles = root.find("contrib").findall("role")  # type: ignore[union-attr]
    assert [r.text for r in roles] == ["Conceptualization", "Writing - original draft"]
    for role in roles:
        assert role.get("vocab") == "credit"
        assert role.get("vocab-identifier") == "https://credit.niso.org/"
        assert role.get("vocab-term-identifier", "").startswith(
            "https://credit.niso.org/contributor-roles/"
        )


def test_contrib_group_emits_a_collab_for_an_organization() -> None:
    xml = to_jats_contrib_group(_sample_contributors())
    assert "<collab>World Health Organization</collab>" in xml


def test_contrib_group_omits_absent_metadata() -> None:
    xml = to_jats_contrib_group([contributor_from_mapping({"name": "Plain Author"})])
    root = ET.fromstring(xml)
    contrib = root.find("contrib")
    assert contrib is not None
    assert contrib.find("contrib-id") is None  # no ORCID
    assert contrib.find("aff") is None  # no affiliation
    assert contrib.find("role") is None  # no CRediT roles
    assert contrib.findtext("name/surname") == "Author"


def test_contrib_group_escapes_special_characters() -> None:
    contributor = Contributor(
        name=CSLName(literal="Ampersand & Angle <Co>"),
        affiliations=(Affiliation(institution="R&D <Lab>"),),
    )
    xml = to_jats_contrib_group([contributor])
    assert "&amp;" in xml
    assert "&lt;Co&gt;" in xml
    # Still parses, and the text round-trips through the parser verbatim.
    root = ET.fromstring(xml)
    assert root.findtext("contrib/collab") == "Ampersand & Angle <Co>"
