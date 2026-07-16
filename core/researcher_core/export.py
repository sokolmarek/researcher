"""Bibliographic export emitters and round-trip fidelity accounting (M5.4, D4).

CSL-JSON is the canonical record format (D4). Everything else in this module is a
*boundary*: it writes a :class:`~researcher_core.model.CSLRecord` out as RIS, JATS
``<ref-list>``, or canonical CSL-JSON, and it reads those formats back into records.
BibTeX is not re-implemented here; it already has a full parser and emitter in
:mod:`researcher_core.bib`, and this module simply re-exports thin wrappers over it so a
caller can treat all four formats uniformly.

Round-trip contract
-------------------
For each format the guarantee is: ``CSL -> emitter -> re-import -> CSL`` is LOSSLESS for the
fields that format can carry, and every field it CANNOT carry is written down in
:data:`LOSS_TABLE` rather than dropped silently. The table is not documentation that drifts
from the code; it is the same object the eval (`evals/run_roundtrip.py`) and the tests assert
against, so a new silent loss fails a test and a padded entry that never actually drops shows
up as an over-broad ``carried`` set.

Why each format loses what it loses (short version; the long version is in each
:class:`FormatLoss`):

* **CSL-JSON** loses nothing. The round-trip is the identity, because CSL-JSON is the model.
* **RIS** has no field for a software version or a report number, and its single ``SN`` tag
  cannot hold an ISSN and an ISBN at once.
* **JATS** ``<element-citation>`` has no element for an abstract, keywords, or a language, and
  its ``<ref>`` ``id`` is an XML NCName that cannot carry an arbitrary CSL id such as a DOI.
* **BibTeX** does not map ``issn``/``keywords`` back into CSL variables (a schema constraint,
  see :mod:`researcher_core.bib`), has no version field and no day-of-month, and collapses
  non-native CSL types (``dataset``, ``software``, ``webpage``) to ``document``.

The comparison surface (:data:`COMPARABLE_FIELDS`, :func:`record_fields`, :func:`field_diff`)
is deliberately shared so "lossless" means the same thing in every test and in the eval.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .bib import emit_bib, parse_bib
from .model import CSLDate, CSLName, CSLRecord, canonical_json, normalize_doi, parse_name

__all__ = [
    "COMPARABLE_FIELDS",
    "CREDIT_ROLES",
    "FORMATS",
    "LOSS_TABLE",
    "Affiliation",
    "Contributor",
    "FormatLoss",
    "contributor_from_mapping",
    "field_diff",
    "from_bibtex",
    "from_csl_json",
    "from_jats_reflist",
    "from_ris",
    "record_fields",
    "roundtrip",
    "to_bibtex",
    "to_csl_json",
    "to_jats_contrib_group",
    "to_jats_reflist",
    "to_ris",
    "validate_credit_role",
    "validate_orcid",
    "validate_ror",
]


# ---------------------------------------------------------------------------
# Shared comparison surface
# ---------------------------------------------------------------------------

#: The bibliographic fields a round-trip is scored on, by :class:`CSLRecord` attribute name.
#: Extension/custom fields are out of scope: they carry provenance, not the citation, and no
#: interchange format is expected to preserve them.
COMPARABLE_FIELDS: tuple[str, ...] = (
    "type",
    "title",
    "author",
    "editor",
    "issued",
    "container_title",
    "publisher",
    "volume",
    "issue",
    "page",
    "number",
    "version",
    "abstract",
    "DOI",
    "URL",
    "ISSN",
    "ISBN",
    "language",
    "note",
    "keyword",
    "id",
)


def record_fields(record: CSLRecord) -> dict[str, Any]:
    """Project a record onto the comparable-field dict used to score a round-trip.

    Names and dates are reduced to their canonical CSL-JSON sub-dicts, so two records compare
    equal exactly when their bibliographic content is equal, independent of object identity.
    """
    issued = record.issued
    return {
        "type": record.type,
        "title": record.title,
        "author": [name.to_csl_json() for name in record.author],
        "editor": [name.to_csl_json() for name in record.editor],
        "issued": issued.to_csl_json() if (issued is not None and not issued.is_empty()) else None,
        "container_title": record.container_title,
        "publisher": record.publisher,
        "volume": record.volume,
        "issue": record.issue,
        "page": record.page,
        "number": record.number,
        "version": record.version,
        "abstract": record.abstract,
        "DOI": record.DOI,
        "URL": record.URL,
        "ISSN": list(record.ISSN),
        "ISBN": record.ISBN,
        "language": record.language,
        "note": record.note,
        "keyword": list(record.keyword),
        "id": record.id,
    }


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def field_diff(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    """The set of fields that were present (non-empty) in ``before`` and changed in ``after``.

    An empty ``before`` value is not scored: an emitter omits empty fields, so their absence on
    re-import is not a loss. This is the primitive both the eval and the tests build on.
    """
    changed: set[str] = set()
    for field_name in COMPARABLE_FIELDS:
        original = before.get(field_name)
        if _is_empty(original):
            continue
        if original != after.get(field_name):
            changed.add(field_name)
    return changed


@dataclass(frozen=True)
class FormatLoss:
    """The documented round-trip loss profile of one export format.

    ``lost`` names the comparable fields the format cannot carry losslessly; ``carried`` is the
    complement and is the set a round-trip must preserve byte for byte. ``notes`` explain the
    mechanism so the table reads as an account, not a bare list.
    """

    fmt: str
    lost: tuple[str, ...]
    notes: tuple[str, ...]

    @property
    def carried(self) -> tuple[str, ...]:
        return tuple(name for name in COMPARABLE_FIELDS if name not in self.lost)


#: The per-format loss table. Single source of truth for the eval and the tests, and the thing
#: published in ``evals/fixtures/roundtrip/README.md``.
LOSS_TABLE: dict[str, FormatLoss] = {
    "csl-json": FormatLoss(
        fmt="csl-json",
        lost=(),
        notes=("The canonical format (D4); the round-trip is the identity and loses nothing.",),
    ),
    "ris": FormatLoss(
        fmt="ris",
        lost=("version", "number", "ISBN"),
        notes=(
            "RIS has no tag for a software/version string or a generic report number.",
            "The single SN tag holds the ISSN for serials; a record's ISBN is carried only "
            "when no ISSN is present (book-like items), so ISSN and ISBN cannot coexist.",
            "Corporate authors round-trip through the AU tag via a no-comma-multiword "
            "heuristic; a one-word organization and a mononym person are indistinguishable.",
        ),
    ),
    "jats": FormatLoss(
        fmt="jats",
        lost=("abstract", "keyword", "language", "id", "number"),
        notes=(
            "JATS <element-citation> has no element for an abstract, for keywords, or for a "
            "language, so those three are dropped.",
            "The <ref> id attribute is an XML NCName and cannot carry an arbitrary CSL id "
            "(for example a DOI), so id is regenerated from record content on import.",
            "No <element-citation> child carries a generic report number.",
        ),
    ),
    "bibtex": FormatLoss(
        fmt="bibtex",
        lost=("ISSN", "keyword", "version", "number", "id", "type", "issued"),
        notes=(
            "entry_to_record does not map issn or keywords back into CSL variables (a "
            "schema constraint, see researcher_core.bib); they survive only under "
            "custom.bibtex.",
            "BibTeX has no version field and no day-of-month: year and month are preserved, "
            "the day is dropped, so 'issued' is only partially carried.",
            "Non-BibTeX-native CSL types (dataset, software, webpage) collapse to 'document' "
            "on re-import, and a DOI-shaped id is replaced by a generated citation key.",
            "Literal brace characters in a title are consumed by BibTeX's "
            "capitalization-protection grouping; titles without literal braces round-trip.",
        ),
    ),
}

#: Export formats this module round-trips, in report order.
FORMATS: tuple[str, ...] = ("csl-json", "ris", "jats", "bibtex")


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def _as_records(records: Iterable[CSLRecord]) -> list[CSLRecord]:
    return list(records)


def _split_page(page: str) -> tuple[str, str]:
    """Split a CSL ``page`` into (first, last). ``"1541-1554"`` -> ``("1541", "1554")``."""
    text = (page or "").strip()
    if not text:
        return "", ""
    if "-" in text:
        first, _, last = text.partition("-")
        return first.strip(), last.strip()
    return text, ""


def _join_page(first: str, last: str) -> str:
    first = (first or "").strip()
    last = (last or "").strip()
    if first and last:
        return f"{first}-{last}"
    return first or last


# ---------------------------------------------------------------------------
# CSL-JSON (canonical, in and out)
# ---------------------------------------------------------------------------


def to_csl_json(records: Iterable[CSLRecord], *, indent: int | None = None) -> str:
    """Emit records as CSL-JSON text.

    With ``indent=None`` (the default) the output is the deterministic *canonical* form
    (:func:`~researcher_core.model.canonical_json`): sorted keys, compact separators, and
    byte-stable, so it is safe to hash and to diff. Pass an integer ``indent`` for a
    human-readable pretty-print (no longer canonical, but still valid CSL-JSON).
    """
    payload = [record.to_csl_json() for record in records]
    if indent is None:
        return canonical_json(payload)
    import json

    return json.dumps(payload, indent=indent, sort_keys=True, ensure_ascii=False, allow_nan=False)


def from_csl_json(text: str) -> list[CSLRecord]:
    """Parse CSL-JSON text (a single object or an array of them) into records."""
    import json

    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("CSL-JSON must be an object or an array of objects")
    return [CSLRecord.from_csl_json(item) for item in data]


# ---------------------------------------------------------------------------
# RIS
# ---------------------------------------------------------------------------

#: CSL item type -> RIS type code. Types not listed fall back to GEN on emission.
_CSL_TO_RIS: dict[str, str] = {
    "article": "JOUR",
    "article-journal": "JOUR",
    "article-magazine": "MGZN",
    "article-newspaper": "NEWS",
    "book": "BOOK",
    "chapter": "CHAP",
    "dataset": "DATA",
    "document": "GEN",
    "manuscript": "UNPB",
    "paper-conference": "CPAPER",
    "patent": "PAT",
    "report": "RPRT",
    "review": "JOUR",
    "software": "COMP",
    "standard": "STAND",
    "thesis": "THES",
    "webpage": "ELEC",
}

#: RIS type code -> CSL item type. The inverse of :data:`_CSL_TO_RIS` where that map is
#: many-to-one, with the conventional CSL type chosen.
_RIS_TO_CSL: dict[str, str] = {
    "BOOK": "book",
    "CHAP": "chapter",
    "COMP": "software",
    "CONF": "paper-conference",
    "CPAPER": "paper-conference",
    "DATA": "dataset",
    "ELEC": "webpage",
    "GEN": "document",
    "JOUR": "article-journal",
    "MGZN": "article-magazine",
    "NEWS": "article-newspaper",
    "PAT": "patent",
    "RPRT": "report",
    "STAND": "standard",
    "THES": "thesis",
    "UNPB": "manuscript",
}

#: RIS types whose SN tag conventionally carries an ISBN rather than an ISSN.
_RIS_ISBN_TYPES = frozenset({"book", "chapter", "pamphlet"})


def _ris_name(name: CSLName) -> str:
    """A CSL name as an RIS ``AU``/``A2`` value: ``"Family, Given, Suffix"`` or a literal."""
    if name.literal and not name.family:
        return name.literal
    family = " ".join(part for part in (name.non_dropping_particle, name.family) if part).strip()
    given = " ".join(part for part in (name.dropping_particle, name.given) if part).strip()
    parts = [family]
    if given:
        parts.append(given)
    if name.suffix:
        parts.append(name.suffix)
    return ", ".join(part for part in parts if part)


def _parse_ris_name(value: str) -> CSLName:
    """Parse an RIS ``AU``/``A2`` value back into a :class:`CSLName`.

    A comma splits ``Family, Given, Suffix``. A comma-less multiword value is read as a
    corporate/organization literal (the documented RIS heuristic); a comma-less single token is
    a mononym person, kept as the family name.
    """
    text = value.strip()
    if "," not in text:
        if " " in text:
            return CSLName(literal=text)
        return CSLName(family=text)
    parts = [part.strip() for part in text.split(",")]
    family = parts[0]
    given = parts[1] if len(parts) > 1 else ""
    suffix = parts[2] if len(parts) > 2 else ""
    return CSLName(family=family, given=given, suffix=suffix)


def _ris_date(issued: CSLDate | None) -> str:
    """The RIS ``DA`` value (``YYYY/MM`` or ``YYYY/MM/DD``), or "" when there is no month."""
    if issued is None or issued.year is None or issued.month is None:
        return ""
    parts = [f"{issued.year:04d}", f"{issued.month:02d}"]
    if issued.day is not None:
        parts.append(f"{issued.day:02d}")
    return "/".join(parts)


def to_ris(records: Iterable[CSLRecord]) -> str:
    """Emit records as RIS. One ``TY``..``ER`` block per record, blank-line separated."""
    blocks: list[str] = []
    for record in records:
        lines: list[tuple[str, str]] = [("TY", _CSL_TO_RIS.get(record.type, "GEN"))]
        if record.id:
            lines.append(("ID", record.id))
        lines.extend(("AU", _ris_name(name)) for name in record.author)
        lines.extend(("A2", _ris_name(name)) for name in record.editor)
        if record.title:
            lines.append(("TI", record.title))
        if record.container_title:
            lines.append(("T2", record.container_title))
        if record.publisher:
            lines.append(("PB", record.publisher))
        if record.volume:
            lines.append(("VL", record.volume))
        if record.issue:
            lines.append(("IS", record.issue))
        first, last = _split_page(record.page)
        if first:
            lines.append(("SP", first))
        if last:
            lines.append(("EP", last))
        if record.year is not None:
            lines.append(("PY", str(record.year)))
        date = _ris_date(record.issued)
        if date:
            lines.append(("DA", date))
        if record.DOI:
            lines.append(("DO", record.DOI))
        if record.URL:
            lines.append(("UR", record.URL))
        # SN holds the ISSN for serials; the ISBN only when no ISSN competes for the tag.
        lines.extend(("SN", issn) for issn in record.ISSN)
        if record.ISBN and not record.ISSN:
            lines.append(("SN", record.ISBN))
        if record.language:
            lines.append(("LA", record.language))
        if record.abstract:
            lines.append(("AB", record.abstract))
        lines.extend(("KW", keyword) for keyword in record.keyword)
        if record.note:
            lines.append(("N1", record.note))
        lines.append(("ER", ""))
        blocks.append("\n".join(f"{tag}  - {value}" for tag, value in lines))
    return ("\n\n".join(blocks) + "\n") if blocks else ""


def from_ris(text: str) -> list[CSLRecord]:
    """Parse RIS text into records. Tolerant of wrapped continuation lines."""
    records: list[CSLRecord] = []
    current: list[tuple[str, str]] | None = None
    last_tag: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if len(line) >= 6 and line[2:6] == "  - " and line[:2].strip().isalnum():
            tag = line[:2]
            value = line[6:].strip()
            if tag == "TY":
                current = [(tag, value)]
                last_tag = tag
                continue
            if current is None:
                continue
            if tag == "ER":
                records.append(_ris_record(current))
                current = None
                last_tag = None
                continue
            current.append((tag, value))
            last_tag = tag
        elif current is not None and last_tag is not None and line.strip():
            # A wrapped continuation of the previous tag's value.
            tag, value = current[-1]
            current[-1] = (tag, f"{value} {line.strip()}".strip())
    if current is not None:
        records.append(_ris_record(current))
    return records


def _ris_record(pairs: Sequence[tuple[str, str]]) -> CSLRecord:
    fields: dict[str, list[str]] = {}
    for tag, value in pairs:
        fields.setdefault(tag, []).append(value)

    def first(*tags: str) -> str:
        for tag in tags:
            values = fields.get(tag)
            if values:
                return values[0]
        return ""

    ris_type = first("TY")
    csl_type = _RIS_TO_CSL.get(ris_type, "document")
    authors = [_parse_ris_name(value) for value in fields.get("AU", [])]
    editors = [_parse_ris_name(value) for value in fields.get("A2", []) + fields.get("ED", [])]

    issued: CSLDate | None = None
    date_text = first("DA")
    if date_text:
        parts = [segment for segment in date_text.replace("-", "/").split("/") if segment.strip()]
        numbers = [int(segment) for segment in parts[:3] if segment.strip().isdigit()]
        if numbers:
            issued = CSLDate(
                year=numbers[0],
                month=numbers[1] if len(numbers) > 1 else None,
                day=numbers[2] if len(numbers) > 2 else None,
            )
    if issued is None:
        year_text = first("PY", "Y1")
        if year_text.strip()[:4].isdigit():
            issued = CSLDate(year=int(year_text.strip()[:4]))

    sn_values = fields.get("SN", [])
    issn: list[str] = []
    isbn = ""
    if sn_values:
        if csl_type in _RIS_ISBN_TYPES:
            isbn = sn_values[0]
        else:
            issn = list(sn_values)

    return CSLRecord(
        id=first("ID"),
        type=csl_type,
        title=first("TI", "T1"),
        author=authors,
        editor=editors,
        issued=issued,
        container_title=first("T2", "JO", "JF"),
        publisher=first("PB"),
        volume=first("VL"),
        issue=first("IS"),
        page=_join_page(first("SP"), first("EP")),
        abstract=first("AB", "N2"),
        DOI=normalize_doi(first("DO")),
        URL=first("UR"),
        ISSN=issn,
        ISBN=isbn,
        language=first("LA"),
        note=first("N1"),
        keyword=list(fields.get("KW", [])),
    )


# ---------------------------------------------------------------------------
# JATS <ref-list>  (JATS 1.3, <element-citation>)
# ---------------------------------------------------------------------------

#: CSL item type -> JATS publication-type attribute value.
_CSL_TO_JATS: dict[str, str] = {
    "article": "journal",
    "article-journal": "journal",
    "article-magazine": "magazine",
    "article-newspaper": "newspaper",
    "book": "book",
    "chapter": "chapter",
    "dataset": "data",
    "document": "other",
    "manuscript": "other",
    "paper-conference": "confproc",
    "patent": "patent",
    "report": "report",
    "review": "journal",
    "software": "software",
    "standard": "standard",
    "thesis": "thesis",
    "webpage": "web",
}

#: JATS publication-type -> CSL item type (inverse, conventional choice).
_JATS_TO_CSL: dict[str, str] = {
    "book": "book",
    "chapter": "chapter",
    "confproc": "paper-conference",
    "data": "dataset",
    "journal": "article-journal",
    "magazine": "article-magazine",
    "newspaper": "article-newspaper",
    "other": "document",
    "patent": "patent",
    "report": "report",
    "software": "software",
    "standard": "standard",
    "thesis": "thesis",
    "web": "webpage",
}


def _text_el(parent: ET.Element, tag: str, text: str) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = text
    return element


def _iso_date(issued: CSLDate) -> str:
    parts = [f"{issued.year:04d}"]
    if issued.month is not None:
        parts.append(f"{issued.month:02d}")
        if issued.day is not None:
            parts.append(f"{issued.day:02d}")
    return "-".join(parts)


def _person_group(parent: ET.Element, role: str, names: Sequence[CSLName]) -> None:
    group = ET.SubElement(parent, "person-group")
    group.set("person-group-type", role)
    for name in names:
        if name.literal and not name.family:
            _text_el(group, "collab", name.literal)
            continue
        name_el = ET.SubElement(group, "name")
        surname = " ".join(
            part for part in (name.non_dropping_particle, name.family) if part
        ).strip()
        _text_el(name_el, "surname", surname)
        given = " ".join(part for part in (name.dropping_particle, name.given) if part).strip()
        if given:
            _text_el(name_el, "given-names", given)
        if name.suffix:
            _text_el(name_el, "suffix", name.suffix)


def to_jats_reflist(records: Iterable[CSLRecord]) -> str:
    """Emit records as a JATS 1.3 ``<ref-list>`` of ``<element-citation>`` entries.

    The ``<ref>`` id attribute is a synthetic, XML-valid anchor (``ref-1``, ``ref-2``, ...); the
    CSL id is intentionally not encoded there (see :data:`LOSS_TABLE`). The title of a work with
    a container goes in ``<article-title>`` and the container in ``<source>``; a work with no
    container puts its title directly in ``<source>``, which is what :func:`from_jats_reflist`
    reverses.
    """
    root = ET.Element("ref-list")
    for index, record in enumerate(records, start=1):
        ref = ET.SubElement(root, "ref")
        ref.set("id", f"ref-{index}")
        citation = ET.SubElement(ref, "element-citation")
        citation.set("publication-type", _CSL_TO_JATS.get(record.type, "other"))
        if record.author:
            _person_group(citation, "author", record.author)
        if record.editor:
            _person_group(citation, "editor", record.editor)
        if record.container_title:
            if record.title:
                _text_el(citation, "article-title", record.title)
            _text_el(citation, "source", record.container_title)
        elif record.title:
            _text_el(citation, "source", record.title)
        if record.publisher:
            _text_el(citation, "publisher-name", record.publisher)
        if record.volume:
            _text_el(citation, "volume", record.volume)
        if record.issue:
            _text_el(citation, "issue", record.issue)
        first, last = _split_page(record.page)
        if first:
            _text_el(citation, "fpage", first)
        if last:
            _text_el(citation, "lpage", last)
        issued = record.issued
        if issued is not None and issued.year is not None:
            year_el = _text_el(citation, "year", str(issued.year))
            year_el.set("iso-8601-date", _iso_date(issued))
            if issued.month is not None:
                _text_el(citation, "month", f"{issued.month:02d}")
                if issued.day is not None:
                    _text_el(citation, "day", f"{issued.day:02d}")
        if record.DOI:
            pub_id = _text_el(citation, "pub-id", record.DOI)
            pub_id.set("pub-id-type", "doi")
        if record.URL:
            _text_el(citation, "uri", record.URL)
        for issn in record.ISSN:
            _text_el(citation, "issn", issn)
        if record.ISBN:
            _text_el(citation, "isbn", record.ISBN)
        if record.version:
            _text_el(citation, "version", record.version)
        if record.note:
            _text_el(citation, "comment", record.note)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n"


def _names_from_group(group: ET.Element) -> list[CSLName]:
    names: list[CSLName] = []
    for child in group:
        if child.tag == "collab":
            names.append(CSLName(literal=(child.text or "").strip()))
        elif child.tag == "name":
            names.append(
                CSLName(
                    family=(child.findtext("surname") or "").strip(),
                    given=(child.findtext("given-names") or "").strip(),
                    suffix=(child.findtext("suffix") or "").strip(),
                )
            )
    return names


def from_jats_reflist(text: str) -> list[CSLRecord]:
    """Parse a JATS ``<ref-list>`` back into records. Inverse of :func:`to_jats_reflist`."""
    root = ET.fromstring(text)
    refs = root.findall("ref") if root.tag == "ref-list" else list(root.iter("ref"))
    records: list[CSLRecord] = []
    for ref in refs:
        citation = ref.find("element-citation")
        if citation is None:
            citation = ref.find("mixed-citation")
        if citation is None:
            continue
        records.append(_jats_record(citation))
    return records


def _jats_record(citation: ET.Element) -> CSLRecord:
    pub_type = citation.get("publication-type", "other")
    csl_type = _JATS_TO_CSL.get(pub_type, "document")

    authors: list[CSLName] = []
    editors: list[CSLName] = []
    for group in citation.findall("person-group"):
        role = group.get("person-group-type", "author")
        names = _names_from_group(group)
        if role == "editor":
            editors.extend(names)
        else:
            authors.extend(names)

    article_title = (citation.findtext("article-title") or "").strip()
    source = (citation.findtext("source") or "").strip()
    if article_title and source:
        title, container = article_title, source
    elif source:
        title, container = source, ""
    else:
        title, container = article_title, ""

    issued: CSLDate | None = None
    year_text = (citation.findtext("year") or "").strip()
    if year_text[:4].isdigit():
        month_text = (citation.findtext("month") or "").strip()
        day_text = (citation.findtext("day") or "").strip()
        issued = CSLDate(
            year=int(year_text[:4]),
            month=int(month_text) if month_text.isdigit() else None,
            day=int(day_text) if day_text.isdigit() else None,
        )

    doi = ""
    for pub_id in citation.findall("pub-id"):
        if pub_id.get("pub-id-type") == "doi":
            doi = (pub_id.text or "").strip()

    issn = [(el.text or "").strip() for el in citation.findall("issn") if (el.text or "").strip()]

    return CSLRecord(
        type=csl_type,
        title=title,
        author=authors,
        editor=editors,
        issued=issued,
        container_title=container,
        publisher=(citation.findtext("publisher-name") or "").strip(),
        volume=(citation.findtext("volume") or "").strip(),
        issue=(citation.findtext("issue") or "").strip(),
        page=_join_page(
            (citation.findtext("fpage") or "").strip(),
            (citation.findtext("lpage") or "").strip(),
        ),
        version=(citation.findtext("version") or "").strip(),
        DOI=normalize_doi(doi),
        URL=(citation.findtext("uri") or "").strip(),
        ISSN=issn,
        ISBN=(citation.findtext("isbn") or "").strip(),
        note=(citation.findtext("comment") or "").strip(),
    )


# ---------------------------------------------------------------------------
# BibTeX (thin re-export of researcher_core.bib)
# ---------------------------------------------------------------------------


def to_bibtex(records: Iterable[CSLRecord]) -> str:
    """Emit records as BibTeX. A thin wrapper over :func:`researcher_core.bib.emit_bib`."""
    return emit_bib(_as_records(records))


def from_bibtex(text: str) -> list[CSLRecord]:
    """Parse BibTeX text into records. A thin wrapper over :mod:`researcher_core.bib`.

    ``keep_source=False`` so the returned records carry the CSL projection only, without the
    verbatim ``custom.bibtex`` stash, matching what the other importers here return.
    """
    return parse_bib(text).records(keep_source=False)


# ---------------------------------------------------------------------------
# Uniform dispatch
# ---------------------------------------------------------------------------

_EMITTERS = {
    "csl-json": to_csl_json,
    "ris": to_ris,
    "jats": to_jats_reflist,
    "bibtex": to_bibtex,
}

_IMPORTERS = {
    "csl-json": from_csl_json,
    "ris": from_ris,
    "jats": from_jats_reflist,
    "bibtex": from_bibtex,
}


def roundtrip(fmt: str, records: Iterable[CSLRecord]) -> list[CSLRecord]:
    """Emit ``records`` to ``fmt`` and re-import them: the ``CSL -> format -> CSL`` round-trip.

    The list length and order are preserved for every format, so callers can zip the result
    against the input and compare field by field.
    """
    if fmt not in _EMITTERS:
        raise ValueError(f"unknown export format {fmt!r}; known formats are {sorted(_EMITTERS)}")
    return _IMPORTERS[fmt](_EMITTERS[fmt](_as_records(records)))


# ---------------------------------------------------------------------------
# Contributor metadata: ORCID, ROR, CRediT (M5.5)
# ---------------------------------------------------------------------------
#
# Three OPTIONAL identifiers/vocabularies attach to a contributor: an ORCID iD (the person),
# a ROR ID (their institution), and one or more CRediT roles (what they did). All three are
# NEVER fabricated. An unknown or malformed value is REJECTED here with an actionable message
# so the caller can fix or drop it; the kernel never guesses a plausible-looking identifier.
# ORCID is checksum-verified (ISO 7064 mod 11-2), ROR is verified against its published
# character/prefix pattern, and a CRediT role must be one of the fixed 14-term taxonomy.


class MetadataError(ValueError):
    """A supplied contributor identifier or role is malformed or not in the taxonomy.

    A subclass of :class:`ValueError`, so existing ``except ValueError`` handlers still catch
    it, but distinct enough that a caller can single out "bad metadata the user supplied" from
    other value errors when it wants to.
    """


# --- ORCID iD -------------------------------------------------------------

_ORCID_PREFIXES = (
    "https://orcid.org/",
    "http://orcid.org/",
    "orcid.org/",
    "orcid:",
)


def _orcid_check_digit(first_15: str) -> str:
    """The ISO 7064 mod 11-2 check character for the first 15 digits of an ORCID.

    The last character of a valid ORCID is this digit, or ``X`` when it works out to 10.
    """
    total = 0
    for char in first_15:
        total = (total + int(char)) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    return "X" if result == 10 else str(result)


def validate_orcid(value: str) -> str:
    """Validate an ORCID iD and return it in canonical ``https://orcid.org/XXXX-...`` form.

    Accepts a bare ``0000-0002-1825-0097``, the compact 16-character form, or any
    ``orcid.org`` URL. The 16 characters are 15 digits plus an ISO 7064 mod 11-2 check
    character (a digit or ``X``); a value that fails the checksum is rejected, never
    "corrected" to a nearby valid iD. Raises :class:`MetadataError` on any malformed input.
    """
    raw = str(value).strip()
    lowered = raw.lower()
    for prefix in _ORCID_PREFIXES:
        if lowered.startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break
    compact = raw.replace("-", "").replace(" ", "").upper()
    if len(compact) != 16:
        raise MetadataError(
            f"invalid ORCID {value!r}: an ORCID has 16 characters (got {len(compact)}), "
            "written as four groups of four, for example 0000-0002-1825-0097"
        )
    body, check = compact[:15], compact[15]
    if not body.isdigit():
        raise MetadataError(
            f"invalid ORCID {value!r}: the first 15 characters must all be digits"
        )
    if check not in "0123456789X":
        raise MetadataError(
            f"invalid ORCID {value!r}: the check character must be a digit or X, got {check!r}"
        )
    expected = _orcid_check_digit(body)
    if check != expected:
        raise MetadataError(
            f"invalid ORCID {value!r}: fails the ISO 7064 mod 11-2 checksum "
            f"(check character should be {expected!r}, not {check!r})"
        )
    formatted = "-".join(compact[i : i + 4] for i in range(0, 16, 4))
    return f"https://orcid.org/{formatted}"


# --- ROR ID ---------------------------------------------------------------

_ROR_PREFIXES = (
    "https://ror.org/",
    "http://ror.org/",
    "ror.org/",
)

# A ROR ID is the string that follows ror.org/: a leading 0, then six Crockford base32
# characters (the alphabet 0-9 a-z with i, l, o, and u removed to avoid look-alikes), then a
# two-digit checksum. This is ROR's published identifier pattern.
_ROR_RE = re.compile(r"^0[0-9a-hj-km-np-tv-z]{6}[0-9]{2}$")


def validate_ror(value: str) -> str:
    """Validate a ROR ID and return it in canonical ``https://ror.org/0...`` form.

    Accepts a bare ``042nb2s44`` or any ``ror.org`` URL. The identifier must match ROR's
    published pattern (a leading ``0``, six base32 characters, two check digits); anything else
    is rejected, never guessed. Raises :class:`MetadataError` on malformed input.
    """
    raw = str(value).strip()
    lowered = raw.lower()
    for prefix in _ROR_PREFIXES:
        if lowered.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    ident = raw.strip("/").lower()
    if not _ROR_RE.match(ident):
        raise MetadataError(
            f"invalid ROR ID {value!r}: expected https://ror.org/ followed by a 0, six base32 "
            "characters, and two check digits, for example https://ror.org/042nb2s44"
        )
    return f"https://ror.org/{ident}"


# --- CRediT roles ---------------------------------------------------------

#: The CRediT (Contributor Roles Taxonomy) 14 terms, in the canonical spelling. Hyphens here
#: are ordinary hyphen-minus characters, never en/em dashes.
CREDIT_ROLES: tuple[str, ...] = (
    "conceptualization",
    "data curation",
    "formal analysis",
    "funding acquisition",
    "investigation",
    "methodology",
    "project administration",
    "resources",
    "software",
    "supervision",
    "validation",
    "visualization",
    "writing - original draft",
    "writing - review and editing",
)

#: canonical role -> (display term, NISO contributor-role slug). The slug builds the
#: ``vocab-term-identifier`` URI (https://credit.niso.org/contributor-roles/<slug>/).
_CREDIT_META: dict[str, tuple[str, str]] = {
    "conceptualization": ("Conceptualization", "conceptualization"),
    "data curation": ("Data curation", "data-curation"),
    "formal analysis": ("Formal analysis", "formal-analysis"),
    "funding acquisition": ("Funding acquisition", "funding-acquisition"),
    "investigation": ("Investigation", "investigation"),
    "methodology": ("Methodology", "methodology"),
    "project administration": ("Project administration", "project-administration"),
    "resources": ("Resources", "resources"),
    "software": ("Software", "software"),
    "supervision": ("Supervision", "supervision"),
    "validation": ("Validation", "validation"),
    "visualization": ("Visualization", "visualization"),
    "writing - original draft": ("Writing - original draft", "writing-original-draft"),
    "writing - review and editing": ("Writing - review and editing", "writing-review-editing"),
}


def _credit_key(value: str) -> str:
    """Normalize a role string for matching: lowercase, hyphens to spaces, whitespace collapsed.

    This makes ``"Data Curation"``, ``"data-curation"``, and ``"data curation"`` all match, so a
    caller is not forced to reproduce the exact canonical spacing.
    """
    text = str(value).strip().lower().replace("-", " ")
    return " ".join(text.split())


#: normalized form -> canonical role. Includes the slug spellings so both
#: ``"writing - original draft"`` and ``"writing-original-draft"`` resolve.
_CREDIT_LOOKUP: dict[str, str] = {}
for _canonical, (_display, _slug) in _CREDIT_META.items():
    _CREDIT_LOOKUP[_credit_key(_canonical)] = _canonical
    _CREDIT_LOOKUP[_credit_key(_slug)] = _canonical


def validate_credit_role(value: str) -> str:
    """Validate a CRediT role and return its canonical spelling (one of :data:`CREDIT_ROLES`).

    Matching is case-insensitive and tolerant of hyphen-vs-space, so ``"Formal Analysis"`` and
    ``"formal-analysis"`` both resolve to ``"formal analysis"``. A role outside the 14-term
    taxonomy is rejected, never approximated. Raises :class:`MetadataError` on an unknown role.
    """
    canonical = _CREDIT_LOOKUP.get(_credit_key(value))
    if canonical is None:
        raise MetadataError(
            f"unknown CRediT role {value!r}: not one of the 14 CRediT terms "
            f"({', '.join(CREDIT_ROLES)})"
        )
    return canonical


# --- Contributor model ----------------------------------------------------


@dataclass(frozen=True)
class Affiliation:
    """A contributor's institutional affiliation, optionally carrying a validated ROR ID.

    ``ror`` is either the empty string or a canonical ``https://ror.org/0...`` URI; the
    constructors in this module never store an unvalidated one.
    """

    institution: str = ""
    ror: str = ""


@dataclass(frozen=True)
class Contributor:
    """An author (or other contributor) plus the optional ORCID/ROR/CRediT metadata.

    ``orcid`` is either "" or a canonical ORCID URI, ``credit_roles`` holds canonical CRediT
    terms, and each affiliation's ROR is canonical or empty. :func:`contributor_from_mapping`
    is the validating constructor; building one directly assumes the values are already clean.
    """

    name: CSLName
    contrib_type: str = "author"
    orcid: str = ""
    affiliations: tuple[Affiliation, ...] = ()
    credit_roles: tuple[str, ...] = ()


def _name_from_value(value: Any) -> CSLName:
    if isinstance(value, CSLName):
        return value
    if isinstance(value, Mapping):
        return CSLName.from_csl_json(value)
    return parse_name(str(value or ""))


def contributor_from_mapping(data: Mapping[str, Any]) -> Contributor:
    """Build a validated :class:`Contributor` from a config-style mapping.

    Recognized keys (all except the name are optional):

    * ``name`` (a string like ``"Jane Q. Doe"``) or the CSL name parts ``family``/``given``/
      ``literal``; ``contrib_type`` (defaults to ``"author"``);
    * ``orcid`` (validated by :func:`validate_orcid`);
    * ``affiliation``/``affiliations`` (a string, a mapping with ``institution``/``name`` and
      ``ror``, or a list of those); a top-level ``ror`` shorthand attaches to a lone affiliation;
    * ``credit``/``credit_roles``/``contributions``/``roles`` (a role string or a list of them,
      each validated by :func:`validate_credit_role`).

    Every identifier is validated and canonicalized; an invalid one raises
    :class:`MetadataError` rather than being silently dropped or guessed.
    """
    if "name" in data:
        name = _name_from_value(data.get("name"))
    else:
        name = CSLName.from_csl_json(data)
    if name.is_empty():
        raise MetadataError("a contributor needs a name (a 'name' string or CSL name parts)")

    contrib_type = str(data.get("contrib_type") or data.get("contrib-type") or "author")

    orcid_raw = data.get("orcid") or data.get("ORCID")
    orcid = validate_orcid(str(orcid_raw)) if orcid_raw else ""

    top_ror = data.get("ror") or data.get("ROR")
    raw_affs = data.get("affiliations")
    if raw_affs is None:
        raw_affs = data.get("affiliation")
    affiliations: list[Affiliation] = []
    for entry in _as_sequence(raw_affs):
        if isinstance(entry, Mapping):
            institution = str(entry.get("institution") or entry.get("name") or "").strip()
            ror_raw = entry.get("ror") or entry.get("ROR")
        else:
            institution = str(entry).strip()
            ror_raw = None
        ror = validate_ror(str(ror_raw)) if ror_raw else ""
        if institution or ror:
            affiliations.append(Affiliation(institution=institution, ror=ror))
    if top_ror:
        canonical_ror = validate_ror(str(top_ror))
        if len(affiliations) == 1 and not affiliations[0].ror:
            affiliations[0] = Affiliation(
                institution=affiliations[0].institution, ror=canonical_ror
            )
        elif not affiliations:
            affiliations.append(Affiliation(ror=canonical_ror))
        else:
            raise MetadataError(
                "a top-level 'ror' is ambiguous with multiple affiliations; put the ror inside "
                "the affiliation it belongs to"
            )

    roles_raw = (
        data.get("credit_roles")
        or data.get("credit-roles")
        or data.get("credit")
        or data.get("contributions")
        or data.get("roles")
    )
    credit_roles = tuple(validate_credit_role(str(role)) for role in _as_sequence(roles_raw))

    return Contributor(
        name=name,
        contrib_type=contrib_type,
        orcid=orcid,
        affiliations=tuple(affiliations),
        credit_roles=credit_roles,
    )


def _as_sequence(value: Any) -> list[Any]:
    """Coerce ``None``/scalar/list into a list, so single and multiple values are handled alike."""
    if value is None:
        return []
    if isinstance(value, (str, Mapping)):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    return [value]


# --- JATS <contrib-group> emitter -----------------------------------------


def _credit_role_el(parent: ET.Element, canonical: str) -> None:
    display, slug = _CREDIT_META[canonical]
    role_el = _text_el(parent, "role", display)
    role_el.set("vocab", "credit")
    role_el.set("vocab-identifier", "https://credit.niso.org/")
    role_el.set("vocab-term", display)
    role_el.set("vocab-term-identifier", f"https://credit.niso.org/contributor-roles/{slug}/")


def to_jats_contrib_group(contributors: Iterable[Contributor]) -> str:
    """Emit contributors as a JATS 1.3 ``<contrib-group>``.

    Each contributor becomes a ``<contrib>`` carrying, when present: a ``<contrib-id
    contrib-id-type="orcid">`` with the ORCID URI, a ``<name>`` (or ``<collab>`` for an
    organization), one CRediT ``<role>`` per role tagged with the NISO vocabulary attributes,
    and an ``<aff>`` per affiliation whose ROR (when set) is written as ``<institution-id
    institution-id-type="ror">``. The output is well-formed XML: :func:`to_jats_contrib_group`
    escapes text and every element is closed, so ``xml.etree.ElementTree.fromstring`` reparses
    it without error.
    """
    group = ET.Element("contrib-group")
    for contributor in contributors:
        contrib = ET.SubElement(group, "contrib")
        contrib.set("contrib-type", contributor.contrib_type or "author")
        if contributor.orcid:
            contrib_id = _text_el(contrib, "contrib-id", contributor.orcid)
            contrib_id.set("contrib-id-type", "orcid")
        name = contributor.name
        if name.literal and not name.family:
            _text_el(contrib, "collab", name.literal)
        else:
            name_el = ET.SubElement(contrib, "name")
            surname = " ".join(
                part for part in (name.non_dropping_particle, name.family) if part
            ).strip()
            _text_el(name_el, "surname", surname)
            given = " ".join(part for part in (name.dropping_particle, name.given) if part).strip()
            if given:
                _text_el(name_el, "given-names", given)
            if name.suffix:
                _text_el(name_el, "suffix", name.suffix)
        for role in contributor.credit_roles:
            _credit_role_el(contrib, role)
        for aff in contributor.affiliations:
            aff_el = ET.SubElement(contrib, "aff")
            if aff.institution:
                _text_el(aff_el, "institution", aff.institution)
            if aff.ror:
                institution_id = _text_el(aff_el, "institution-id", aff.ror)
                institution_id.set("institution-id-type", "ror")
    ET.indent(group, space="  ")
    return ET.tostring(group, encoding="unicode") + "\n"
