"""The M5.3 no-export invariant: cached full text never leaves the cache.

M5.3 draws a hard line between two stores and two boundaries:

* Cached OA full text (the extracted body of a fetched paper) lives ONLY in the platformdirs
  user cache (``ResponseCache``, under the ``fulltext`` source). It is never committed, never
  copied into ``manuscript/``, and never exported.
* The two things a user hands onward carry the CITATION, not the article body. The research
  passport (:mod:`researcher_core.lineage.passport`) carries claim ids/hashes, source DOIs, and
  run manifests. The bibliographic exporters (:mod:`researcher_core.export`) carry CSL records.
  Neither path has any code that reads the cache, so neither can emit a cached PDF or its text.

These tests assert that separation MECHANICALLY. A distinctive full-text string is stored in the
cache and keyed to the same work a passport and an export describe; the tests then prove the
string (and the cache location, and the OA URL) is absent from every passport and every export
format, while the bibliographic content the caller expects IS present, so the check is not
vacuous.
"""

from __future__ import annotations

import base64
import json

from researcher_core.cache import (
    ResponseCache,
    default_cache_path,
    user_cache_root,
)
from researcher_core.export import (
    FORMATS,
    to_bibtex,
    to_csl_json,
    to_jats_reflist,
    to_ris,
)
from researcher_core.lineage.compile import compile_graph
from researcher_core.lineage.graph import EdgeRecord, LineageGraph
from researcher_core.lineage.model import (
    ArtifactHash,
    AxisVerdicts,
    EvidenceEdge,
    ExperimentManifest,
    make_claim_node,
)
from researcher_core.lineage.passport import to_prov_jsonld, to_ro_crate
from researcher_core.model import CSLDate, CSLName, CSLRecord

# A distinctive sentence that stands in for extracted OA full text. It is the fetched article's
# body, deliberately NOT any claim's own text, so finding it anywhere downstream is a real leak.
SECRET_FULLTEXT = (
    "Under hypoxic culture the engineered strain yielded 42.7 milligrams of product per litre, "
    "exceeding the wild-type control by a factor of three across all replicates."
)
SECRET_B64 = base64.b64encode(SECRET_FULLTEXT.encode("utf-8")).decode("ascii")

DOI = "10.1000/real"
SOURCE_DOI_REF = "https://doi.org/10.1000/real"
OA_URL = "https://example.org/oa/real-paper.pdf"
PASSAGE_ID = "0a1b2c3d4e5f60718293a4b5c6d7e8f9"

# The claim's own (manuscript-owned) words. These MAY appear in the passport; they are the
# author's text, not fetched content.
CLAIM_TEXT = "The engineered strain outperformed the wild-type control."


def cache_full_text(cache: ResponseCache) -> None:
    """Store the OA full text in the cache exactly as the full-text fetch path would: a base64
    document body under the ``fulltext`` source, keyed by the OA URL."""
    body = {
        "url": OA_URL,
        "content_type": "application/pdf",
        "encoding": "base64",
        "content_base64": SECRET_B64,
    }
    cache.set("fulltext", "document", {"url": OA_URL}, body)


def sample_graph() -> LineageGraph:
    """A graph whose external edge cites the same work whose full text is cached."""
    g = LineageGraph()
    claim_a = make_claim_node("results.tex", CLAIM_TEXT, 0, len(CLAIM_TEXT), "assertion")
    claim_b = make_claim_node("results.tex", "Yield reached 42.7 mg/L.", 40, 64, "number")
    g.claims[claim_a.claim_id] = claim_a
    g.claims[claim_b.claim_id] = claim_b

    manifest = ExperimentManifest(
        run_id="assay-1",
        code_commit="abc123",
        ts="2026-07-14T00:00:00Z",
        artifact_hashes=(ArtifactHash("results/yield.csv", "h1"),),
    )
    g.manifests[manifest.manifest_hash()] = manifest

    g.edges.append(
        EdgeRecord(
            edge=EvidenceEdge(
                claim_id=claim_a.claim_id,
                target_kind="external",
                passage_id=PASSAGE_ID,
                axis_verdicts=AxisVerdicts(identity="verified", faithfulness="supported"),
            ),
            source_doi=DOI,
        )
    )
    g.edges.append(
        EdgeRecord(
            edge=EvidenceEdge(
                claim_id=claim_b.claim_id,
                target_kind="internal",
                manifest_hash=manifest.manifest_hash(),
            )
        )
    )
    return g


def sample_record() -> CSLRecord:
    """A bibliographic record for the same DOI whose full text is cached."""
    return CSLRecord(
        id="smith2020",
        type="article-journal",
        title="Engineered strains under hypoxic culture",
        author=[CSLName(family="Smith", given="Jane"), CSLName(family="Doe", given="John")],
        issued=CSLDate(year=2020, month=6, day=1),
        container_title="Journal of Synthetic Biology",
        volume="12",
        issue="3",
        page="100-115",
        DOI=DOI,
        ISSN=["1234-5678"],
    )


# --- the cache is the platformdirs cache, and it holds the full text ------


def test_cached_full_text_lives_in_the_platformdirs_cache(cache: ResponseCache):
    cache_full_text(cache)

    # The cache genuinely holds the full text (decoding the stored body recovers it).
    stored = cache.get("fulltext", "document", {"url": OA_URL})
    assert stored is not None
    assert base64.b64decode(stored["content_base64"]).decode("utf-8") == SECRET_FULLTEXT

    # And it lives in the platformdirs user cache dir, not in a manuscript or passport tree.
    assert cache.path == default_cache_path()
    assert cache.path.parent == user_cache_root()
    assert cache.path.is_file()
    assert "manuscript" not in cache.path.parts
    assert "passport" not in cache.path.parts


# --- the passport never carries cached full text --------------------------


def test_passport_never_contains_cached_full_text(cache: ResponseCache):
    cache_full_text(cache)
    graph = sample_graph()
    report = compile_graph(graph)

    crate_json = json.dumps(to_ro_crate(graph, name="Manuscript"))
    prov_json = json.dumps(to_prov_jsonld(graph, report))

    # Not vacuous: the passport DOES carry the citation (source DOI) and the claim's own text.
    assert SOURCE_DOI_REF in crate_json
    assert SOURCE_DOI_REF in prov_json
    assert CLAIM_TEXT in crate_json

    # The invariant: no cached article body, no base64 of it, and no OA PDF location leak in.
    for blob in (crate_json, prov_json):
        assert SECRET_FULLTEXT not in blob
        assert SECRET_B64 not in blob
        assert OA_URL not in blob
        assert str(cache.path) not in blob


def test_evidence_edge_references_a_passage_by_id_not_by_text():
    # The lineage layer points at a passage by its stable id (D21), never by embedding the
    # fetched passage text. This is what lets the passport carry ids and hashes, not full text.
    edge = sample_graph().edges[0].edge
    assert edge.passage_id == PASSAGE_ID
    assert SECRET_FULLTEXT not in json.dumps(edge.to_json_dict())


# --- exports emit bibliographic records, not cached PDFs -------------------


def test_exports_emit_bibliographic_records_not_cached_full_text(cache: ResponseCache):
    cache_full_text(cache)
    records = [sample_record()]

    outputs = {
        "csl-json": to_csl_json(records),
        "ris": to_ris(records),
        "jats": to_jats_reflist(records),
        "bibtex": to_bibtex(records),
    }
    # Guard against a format silently dropping out of the suite.
    assert set(outputs) == set(FORMATS)

    for fmt, out in outputs.items():
        # Not vacuous: the bibliographic record really is emitted.
        assert "Engineered strains under hypoxic culture" in out, fmt
        assert DOI in out, fmt
        # The invariant: an export carries the citation, never the cached full text, its base64,
        # the OA PDF location, or the cache path on disk.
        assert SECRET_FULLTEXT not in out, fmt
        assert SECRET_B64 not in out, fmt
        assert OA_URL not in out, fmt
        assert str(cache.path) not in out, fmt
