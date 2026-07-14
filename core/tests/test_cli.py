"""The CLI, and the schemas it is contractually bound to (M2.11).

Every test here runs OFFLINE. The API responses come from ``core/tests/snapshots/`` and
``core/tests/snapshots/verify-gold/``, recorded from the live OpenAlex, Crossref, DataCite,
Semantic Scholar, PubMed, Unpaywall, arXiv, and OpenCitations APIs, so every table and every
JSON document asserted below was produced from a real payload. Document bodies (the HTML a
full-text extraction reads) are recorded into a temporary snapshot store exactly as
``test_fulltext.py`` does: a fetched PDF or HTML page is a snapshot like any other.

**The acceptance criterion of this file is the schema check.** Every ``--json`` output is
validated against its ``core/schemas/*.json`` with ``jsonschema``, which is a DEV dependency:
the runtime never imports it, and ``test_the_runtime_never_imports_jsonschema`` holds that
line. A command whose JSON drifts from the contract fails here, loudly, rather than reaching
a skill.

The other three properties this file exists to pin:

* invalid arguments exit 2 with usage text, and an operational failure exits 1, because a
  skill has to be able to tell "I called it wrong" from "the world did not cooperate";
* two replays of one snapshot set produce byte-identical output (D15);
* a document with no reachable full text yields zero passages and an ``insufficient-passage``
  verdict that is never clean (D11), through the CLI, not just in the library.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from researcher_core import cli
from researcher_core.model import CSLRecord
from researcher_core.snapshots import SnapshotStore

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
SNAPSHOTS = TESTS / "snapshots"
GOLD = SNAPSHOTS / "verify-gold"
SCHEMAS = CORE / "schemas"


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def run(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    """Invoke the CLI in-process. Returns (exit code, stdout, stderr).

    An argparse failure raises SystemExit; it is caught here and reported as its exit code,
    so a test can assert on the 2 rather than on the exception.
    """
    try:
        code = cli.main(argv)
    except SystemExit as exc:  # argparse: invalid arguments
        code = int(exc.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def run_json(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, Any]:
    code, out, err = run(argv, capsys)
    assert out.strip(), f"no JSON on stdout (exit {code}); stderr: {err}"
    return code, json.loads(out)


def validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def assert_valid(name: str, payload: Any, label: str = "") -> None:
    errors = sorted(validator(name).iter_errors(payload), key=str)
    assert not errors, f"{label or name}: {[e.message for e in errors]}"


def assert_each_valid(name: str, payloads: Any, label: str = "") -> None:
    assert payloads, f"{label or name}: nothing to validate"
    for index, payload in enumerate(payloads):
        assert_valid(name, payload, f"{label or name}[{index}]")


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Point the CLI at the recorded connector snapshots, in replay mode."""
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(SNAPSHOTS))
    monkeypatch.setenv("RESEARCHER_CORE_NO_CACHE", "1")
    return SNAPSHOTS


@pytest.fixture()
def gold(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Point the CLI at the axis (a) and axis (b) gold snapshots, in replay mode."""
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(GOLD))
    monkeypatch.setenv("RESEARCHER_CORE_NO_CACHE", "1")
    return GOLD


# ---------------------------------------------------------------------------
# Document fixtures: the bytes a full-text extraction actually reads
# ---------------------------------------------------------------------------

PEERJ_DOI = "10.7717/peerj.4375"
PEERJ_OA_URL = "https://doi.org/10.7717/peerj.4375"
EMPTY_URL = "https://example.org/paywalled-landing-page"

ARTICLE_HTML = """
<html><body>
<h1>Abstract</h1>
<p>We evaluate a self-supervised model on twelve-lead ECG recordings collected from
4200 patients across two hospitals.</p>
<h1>Methods</h1>
<p>Recordings were resampled to 100 Hz and split by patient into training, validation,
and test partitions with no patient appearing in more than one partition.</p>
<h1>Results</h1>
<p>The self-supervised model reached a macro AUROC of 0.94 on the held-out test set,
outperforming the fully supervised baseline by four points.</p>
<h1>Discussion</h1>
<p>Pretraining on unlabeled recordings closes most of the gap to a fully supervised
model trained on the complete labeled set.</p>
</body></html>
"""

# A landing page with no article text: real papers behind a paywall look like this. It is the
# case that must degrade to abstract-only, never to an invented body.
EMPTY_HTML = "<html><head><title>Access options</title></head><body></body></html>"


def document_body(url: str, html: str) -> dict[str, Any]:
    """The snapshot body of a fetched document: base64, so it is JSON and content-addressed."""
    return {
        "url": url,
        "content_type": "text/html; charset=utf-8",
        "encoding": "base64",
        "content_base64": base64.b64encode(html.encode("utf-8")).decode("ascii"),
    }


@pytest.fixture()
def documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A snapshot store carrying the real Unpaywall answer for PeerJ plus two document bodies.

    The Unpaywall response is the one recorded from the live API (copied, not invented), so
    the OA cascade the CLI walks is the real one. The document bodies are fixtures, exactly as
    in ``test_fulltext.py``: a fetched page is a snapshot, and building one here is what keeps
    the extraction path offline.
    """
    root = tmp_path / "docstore"
    target = SnapshotStore(root)
    source = SnapshotStore(SNAPSHOTS)
    target.write(source.load("unpaywall", f"v2/{PEERJ_DOI}", {}))
    for url, html in ((PEERJ_OA_URL, ARTICLE_HTML), (EMPTY_URL, EMPTY_HTML)):
        target.record("fulltext", "document", {"url": url}, document_body(url, html))
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(root))
    monkeypatch.setenv("RESEARCHER_CORE_NO_CACHE", "1")
    return root


@pytest.fixture()
def db(tmp_path: Path) -> str:
    return str(tmp_path / "passages.sqlite3")


@pytest.fixture()
def ledger(tmp_path: Path) -> str:
    return str(tmp_path / "provenance.sqlite3")


# The two entries the gold set was built to separate: one real paper that two indexes hold,
# and one that does not exist anywhere. Both are verbatim from verify-gold/cases.json.
BIB = """
@article{piwowar2007sharing,
  title = {Sharing Detailed Research Data Is Associated with Increased Citation Rate},
  author = {Piwowar, Heather A. and Day, Roger S. and Fridsma, Douglas B.},
  journal = {PLoS ONE},
  year = {2007},
  doi = {10.1371/journal.pone.0000308}
}

@article{kessler2021cmae,
  title = {Contrastive masked autoencoders for single-lead ECG anomaly detection},
  author = {Kessler, Anna and Vogel, Martin},
  journal = {IEEE Transactions on Biomedical Engineering},
  year = {2021},
  doi = {10.1109/TBME.2021.3098765}
}
"""


@pytest.fixture()
def bib_path(tmp_path: Path) -> str:
    path = tmp_path / "library.bib"
    path.write_text(BIB, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# The runtime does not import jsonschema
# ---------------------------------------------------------------------------


def test_the_runtime_never_imports_jsonschema() -> None:
    """D3: the base install is httpx, rapidfuzz, platformdirs. Validation is a test concern.

    Grepped rather than trusted, because an innocent-looking `import jsonschema` in any
    module would silently make the documented base install a lie.
    """
    offenders = [
        path.name
        for path in sorted((CORE / "researcher_core").rglob("*.py"))
        if "jsonschema" in path.read_text(encoding="utf-8")
    ]
    assert offenders == ["cli.py"], offenders
    # ...and cli.py only NAMES it, in prose. It does not import it.
    text = (CORE / "researcher_core" / "cli.py").read_text(encoding="utf-8")
    assert "import jsonschema" not in text


# ---------------------------------------------------------------------------
# Argument handling: 2 is "you called it wrong", 1 is "the world did not cooperate"
# ---------------------------------------------------------------------------


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run([], capsys)
    assert code == 0
    assert "usage: researcher-core" in out


def test_help_lists_every_command_in_the_surface_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out, _ = run(["--help"], capsys)
    assert code == 0
    for command in cli.COMMANDS:
        assert command in out, command


@pytest.mark.parametrize(
    "argv",
    [
        ["not-a-command"],
        ["search"],  # missing the query
        ["search", "x", "--sources", "nope"],
        ["search", "x", "--limit", "0"],
        ["citations", "10.1/x", "--depth", "3"],  # MAX_DEPTH is 2
        ["faithfulness", "a claim"],  # --doc is required
        ["status", "not-a-doi-and-not-a-file"],
        ["oa-pdf", "definitely-not-a-doi"],
        ["passages"],  # a command group with no subcommand
        ["snapshot"],
        ["provenance"],
        ["snapshot", "replay", "openalex"],  # source without endpoint
        ["snapshot", "record", "openalex", "works", "-p", "bad-param"],
        ["snapshot", "diff", "--live-from", "x.json"],  # nothing to diff against
    ],
)
def test_invalid_arguments_exit_2_with_usage(
    argv: list[str], capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, _, err = run(argv, capsys)
    assert code == 2, f"{argv} exited {code}"
    assert "usage:" in err


def test_version_reports_core_parser_and_protocol(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["--version"], capsys)
    assert code == 0
    assert "researcher-core" in out
    assert "parser" in out and "protocol" in out


def test_a_missing_snapshot_exits_1_and_never_goes_live(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    """Replay never falls through to a live call. The failure is loud, and it is a 1, not a 2:
    the invocation was fine, the fixture set is not."""
    code, _, err = run(["search", "no snapshot for this query", "--sources", "openalex"], capsys)
    assert code == 1
    assert "No snapshot" in err
    assert "never falls through to a live call" in err


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


SEARCH_ARGV = [
    "search",
    "self-supervised ECG",
    "--sources",
    "openalex,arxiv",
    "--limit",
    "5",
]


def test_search_json_records_validate_against_record_schema(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, payload = run_json([*SEARCH_ARGV, "--json"], capsys)
    assert code == 0
    assert_each_valid("record.schema.json", payload["records"], "search record")
    assert payload["counts"]["retrieved"] == 10
    assert payload["counts"]["deduplicated"] == len(payload["records"]) == 8
    assert payload["counts"]["duplicates_removed"] == 2
    assert payload["warnings"] == []
    assert [s["source"] for s in payload["sources"]] == ["openalex", "arxiv"]


def test_search_merges_the_same_paper_across_two_sources(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    _, payload = run_json([*SEARCH_ARGV, "--json"], capsys)
    merged = [
        record
        for record in payload["records"]
        if len(record.get("custom", {}).get("sources", [])) > 1
    ]
    assert merged, "the planted cross-source duplicates did not collapse"
    assert all(sorted(r["custom"]["sources"]) == ["arxiv", "openalex"] for r in merged)


def test_search_human_output_is_a_table_not_json(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, out, _ = run(SEARCH_ARGV, capsys)
    assert code == 0
    assert out.lstrip()[0] != "{"
    assert "TITLE" in out and "SOURCES" in out
    assert "10 retrieved, 8 after dedupe (2 duplicates removed)" in out


def test_two_replays_produce_byte_identical_json(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    """D15, stated as a test: same snapshot, same configuration, same parser version, same
    bytes. Nothing in the CLI generates a timestamp, and this is what proves it."""
    _, first, _ = run([*SEARCH_ARGV, "--json"], capsys)
    _, second, _ = run([*SEARCH_ARGV, "--json"], capsys)
    assert first == second
    assert first.encode("utf-8") == second.encode("utf-8")


def test_issn_and_keywords_never_reach_the_csl_namespace(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    """The record schema types ISSN and keyword as string-or-number (as upstream CSL does),
    while the model holds lists. The emitter carries both under `custom`, losslessly, which is
    the same resolution bib.py reached. Asserted on a record that really does carry two ISSNs.
    """
    _, payload = run_json([*SEARCH_ARGV, "--json"], capsys)
    carrying_issn = [r for r in payload["records"] if r.get("custom", {}).get("issn")]
    assert carrying_issn, "no snapshot record in this query carries an ISSN"
    for record in payload["records"]:
        assert "ISSN" not in record
        assert "keyword" not in record
    assert carrying_issn[0]["custom"]["issn"] == ["1949-3045", "2371-9850"]


def test_since_filters_to_a_different_snapshot(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, payload = run_json(
        ["search", "self-supervised ECG", "--sources", "openalex", "--limit", "5",
         "--since", "2023", "--json"],
        capsys,
    )
    assert code == 0
    assert payload["records"]
    assert all(r["issued"]["date-parts"][0][0] >= 2023 for r in payload["records"])


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_returns_one_validated_record(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, payload = run_json(["get", PEERJ_DOI, "--sources", "openalex", "--json"], capsys)
    assert code == 0
    assert payload["found"] is True
    assert_valid("record.schema.json", payload["record"], "get record")
    assert payload["record"]["DOI"] == PEERJ_DOI
    assert payload["record"]["title"].startswith("The state of OA")


def test_get_of_a_nonexistent_doi_is_a_clean_negative_and_exits_1(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    """Not found is a real answer, reported as one, with a non-zero exit so a shell notices."""
    code, payload = run_json(
        ["get", "10.9999/definitely-not-a-real-doi-xyz", "--sources", "openalex", "--json"],
        capsys,
    )
    assert code == 1
    assert payload["found"] is False
    assert payload["record"] is None
    assert payload["warnings"] == []  # a clean negative, NOT a source error
    assert payload["sources"] == [{"source": "openalex", "status": "ok", "record_count": 0}]


# ---------------------------------------------------------------------------
# verify-bib and verify-ref: axes (a), (b), (d) in one report
# ---------------------------------------------------------------------------


VERIFY_SOURCES = ["--sources", "openalex,crossref,datacite"]


def test_verify_bib_carries_all_three_axes_and_validates(
    capsys: pytest.CaptureFixture[str], gold: Path, bib_path: str
) -> None:
    code, payload = run_json(["verify-bib", bib_path, *VERIFY_SOURCES, "--json"], capsys)
    assert code == 0
    assert_valid("verification-report.schema.json", payload, "verify-bib")

    by_key = {entry["key"]: entry for entry in payload["entries"]}
    real = by_key["piwowar2007sharing"]
    invented = by_key["kessler2021cmae"]

    # Axis (a).
    assert real["verdict"] == "verified"
    assert real["refusal_grade"] is False
    assert invented["verdict"] == "unresolvable"
    assert invented["refusal_grade"] is True

    # Axis (b) and axis (d), per entry, side by side with axis (a) and never folded into it.
    assert real["status"]["verdict"] == "current"
    assert real["status"]["checked"] is True
    assert real["accessibility"]["verdict"] in {"full-text", "abstract-only", "unavailable"}
    assert invented["accessibility"]["verdict"] == "unavailable"

    # Per-source outcomes are retained, not just the aggregate.
    assert {o["source"] for o in real["source_outcomes"]} == {"openalex", "crossref", "datacite"}
    assert all(o["outcome"] == "negative" for o in invented["source_outcomes"])
    assert payload["summary"]["refusal_grade"] == 1


def test_verify_bib_human_output_names_the_refusal_grade_entry(
    capsys: pytest.CaptureFixture[str], gold: Path, bib_path: str
) -> None:
    code, out, _ = run(["verify-bib", bib_path, *VERIFY_SOURCES], capsys)
    assert code == 0
    assert "IDENTITY" in out and "REFUSAL" in out and "STATUS" in out and "ACCESS" in out
    assert "refusal-grade: 1" in out
    assert "inconclusive never is" in out
    assert "kessler2021cmae: all 3 queried sources returned a clean negative" in out


def test_verify_ref_of_a_doi_validates_and_verifies(
    capsys: pytest.CaptureFixture[str], gold: Path
) -> None:
    code, payload = run_json(
        ["verify-ref", "10.1371/journal.pone.0000308", *VERIFY_SOURCES, "--json"], capsys
    )
    assert code == 0
    assert_valid("verification-report.schema.json", payload, "verify-ref")
    assert payload["input"] == {
        "kind": "reference",
        "reference": "10.1371/journal.pone.0000308",
    }
    entry = payload["entries"][0]
    assert entry["verdict"] == "verified"
    assert entry["tally"]["confirmed"] >= 2


def test_verify_bib_on_a_missing_file_exits_1(
    capsys: pytest.CaptureFixture[str], gold: Path, tmp_path: Path
) -> None:
    code, _, err = run(["verify-bib", str(tmp_path / "nope.bib"), *VERIFY_SOURCES], capsys)
    assert code == 1
    assert "No such file" in err


# ---------------------------------------------------------------------------
# status: axis (b)
# ---------------------------------------------------------------------------


def test_status_of_a_retracted_doi(capsys: pytest.CaptureFixture[str], gold: Path) -> None:
    code, payload = run_json(
        ["status", "10.1016/s0140-6736(20)31180-6", "--json"], capsys
    )
    assert code == 0
    assert_valid("status-report.schema.json", payload, "status")
    entry = payload["entries"][0]
    assert entry["verdict"] == "retracted"
    assert entry["checked"] is True
    assert entry["notices"]
    assert payload["summary"]["status"]["retracted"] == 1


def test_status_of_the_retraction_notice_itself_is_current(
    capsys: pytest.CaptureFixture[str], gold: Path
) -> None:
    """The trap this axis exists to survive: a retraction NOTICE is a current document that
    carries a Crossref update-to of type retraction in both directions."""
    code, payload = run_json(["status", "10.1016/s0140-6736(20)31324-6", "--json"], capsys)
    assert code == 0
    assert payload["entries"][0]["verdict"] == "current"


def test_status_over_a_bib_checks_every_doi(
    capsys: pytest.CaptureFixture[str], gold: Path, bib_path: str
) -> None:
    code, payload = run_json(["status", bib_path, "--json"], capsys)
    assert code == 0
    assert_valid("status-report.schema.json", payload, "status over a bib")
    assert payload["input"] == {"kind": "bib", "path": bib_path}
    assert payload["summary"]["total"] == 2


def test_status_human_output_reports_the_verdict(
    capsys: pytest.CaptureFixture[str], gold: Path
) -> None:
    code, out, _ = run(["status", "10.1016/s0140-6736(20)31180-6"], capsys)
    assert code == 0
    assert "retracted" in out
    assert "1 checked: 0 current" in out


# ---------------------------------------------------------------------------
# citations and references
# ---------------------------------------------------------------------------


def test_citations_nodes_validate_as_records(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, payload = run_json(
        ["citations", PEERJ_DOI, "--sources", "openalex", "--limit", "5", "--json"], capsys
    )
    assert code == 0
    assert_each_valid("record.schema.json", payload["nodes"], "citation node")
    assert payload["direction"] == "forward"
    assert payload["depth"] == 1
    assert payload["counts"]["nodes"] == 5
    assert all(edge["cited"] for edge in payload["edges"])


def test_references_nodes_validate_as_records(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, payload = run_json(
        ["references", PEERJ_DOI, "--sources", "opencitations", "--limit", "5", "--json"],
        capsys,
    )
    assert code == 0
    assert_each_valid("record.schema.json", payload["nodes"], "reference node")
    assert payload["direction"] == "backward"
    assert payload["counts"]["nodes"] == 5


# ---------------------------------------------------------------------------
# oa-pdf: the axis (d) cascade
# ---------------------------------------------------------------------------


def test_oa_pdf_resolves_through_unpaywall(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, payload = run_json(["oa-pdf", PEERJ_DOI, "--json"], capsys)
    assert code == 0
    assert payload["verdict"] == "full-text"
    assert payload["location"]["source"] == "unpaywall"
    assert payload["location"]["url"] == PEERJ_OA_URL
    assert payload["sources_tried"] == ["unpaywall"]  # the cascade stops at the first hit
    assert payload["errors"] == []


def test_oa_pdf_human_output(capsys: pytest.CaptureFixture[str], store: Path) -> None:
    code, out, _ = run(["oa-pdf", PEERJ_DOI], capsys)
    assert code == 0
    assert f"{PEERJ_DOI}: full-text" in out
    assert "license: cc-by" in out


# ---------------------------------------------------------------------------
# fulltext
# ---------------------------------------------------------------------------


def test_fulltext_extracts_sections_with_monotonic_offsets(
    capsys: pytest.CaptureFixture[str], documents: Path
) -> None:
    code, payload = run_json(["fulltext", PEERJ_DOI, "--json"], capsys)
    assert code == 0
    assert payload["accessibility"] == "full-text"
    assert payload["doc_id"] == PEERJ_DOI
    assert payload["section_count"] == 4

    # The shape the plan's CLI surface table promises: {section, text, char_offsets,
    # page_coords}. HTML has no pagination, so page_coords is null and is never invented.
    sections = payload["sections"]
    assert [s["section"] for s in sections] == ["Abstract", "Methods", "Results", "Discussion"]
    assert all(set(s) >= {"section", "text", "char_offsets", "page_coords"} for s in sections)
    offsets = [tuple(s["char_offsets"]) for s in sections]
    assert all(start < end for start, end in offsets)
    assert offsets == sorted(offsets)
    assert all(s["page_coords"] is None for s in sections)


def test_fulltext_sections_flag_renders_the_section_table(
    capsys: pytest.CaptureFixture[str], documents: Path
) -> None:
    code, out, _ = run(["fulltext", PEERJ_DOI, "--sections"], capsys)
    assert code == 0
    assert "SECTION" in out and "START" in out and "END" in out
    assert "Results" in out


def test_fulltext_of_a_page_with_no_text_degrades_to_abstract_only(
    capsys: pytest.CaptureFixture[str], documents: Path
) -> None:
    """The fabrication fence: an OA link that yields no text is NOT full text, and no segment
    may exist without extracted bytes behind it."""
    code, payload = run_json(["fulltext", EMPTY_URL, "--json"], capsys)
    assert code == 0
    assert payload["accessibility"] == "abstract-only"
    assert payload["sections"] == []
    assert payload["char_count"] == 0
    assert "no extractable text" in payload["reason"]


# ---------------------------------------------------------------------------
# passages: the D21 index
# ---------------------------------------------------------------------------


def test_passages_index_emits_schema_valid_passages(
    capsys: pytest.CaptureFixture[str], documents: Path, db: str
) -> None:
    code, payload = run_json(["passages", "index", PEERJ_DOI, "--db", db, "--json"], capsys)
    assert code == 0
    assert_each_valid("passage.schema.json", payload["passages"], "indexed passage")
    assert payload["document"]["doc_id"] == PEERJ_DOI
    assert payload["document"]["accessibility"] == "full-text"
    assert payload["document"]["passage_count"] == len(payload["passages"]) == 4


def test_passage_ids_are_stable_across_reindexing(
    capsys: pytest.CaptureFixture[str], documents: Path, db: str
) -> None:
    """The D21 guarantee, through the CLI: same bytes, same parser version, same IDs."""
    _, first = run_json(["passages", "index", PEERJ_DOI, "--db", db, "--json"], capsys)
    _, second = run_json(["passages", "index", PEERJ_DOI, "--db", db, "--json"], capsys)
    assert [p["passage_id"] for p in first["passages"]] == [
        p["passage_id"] for p in second["passages"]
    ]


def test_passages_search_returns_bm25_ranked_passages(
    capsys: pytest.CaptureFixture[str], documents: Path, db: str
) -> None:
    run_json(["passages", "index", PEERJ_DOI, "--db", db, "--json"], capsys)
    code, payload = run_json(
        ["passages", "search", "macro AUROC held-out test set", "--doc", PEERJ_DOI,
         "--db", db, "--json"],
        capsys,
    )
    assert code == 0
    assert_each_valid("passage.schema.json", payload["passages"], "searched passage")
    top = payload["passages"][0]
    assert top["section_path"] == "Results"
    assert top["bm25_score"] is not None
    assert "macro AUROC of 0.94" in top["text"]


def test_passages_index_of_an_unextractable_document_indexes_zero_passages(
    capsys: pytest.CaptureFixture[str], documents: Path, db: str
) -> None:
    code, payload = run_json(["passages", "index", EMPTY_URL, "--db", db, "--json"], capsys)
    assert code == 0
    assert payload["passages"] == []
    assert payload["document"]["accessibility"] == "abstract-only"
    assert payload["document"]["passage_count"] == 0


# ---------------------------------------------------------------------------
# faithfulness: axis (c)
# ---------------------------------------------------------------------------


CLAIM = "The self-supervised model reached a macro AUROC of 0.94 on the held-out test set."


def test_faithfulness_anchors_a_supported_claim_on_a_passage(
    capsys: pytest.CaptureFixture[str], documents: Path, db: str
) -> None:
    run_json(["passages", "index", PEERJ_DOI, "--db", db, "--json"], capsys)
    code, payload = run_json(
        ["faithfulness", CLAIM, "--doc", PEERJ_DOI, "--db", db, "--json"], capsys
    )
    assert code == 0
    assert_valid("faithfulness-report.schema.json", payload, "faithfulness")
    claim = payload["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["clean"] is True
    assert claim["evidence"], "a non-abstaining verdict must be anchored on a passage"
    assert claim["evidence"][0]["section_path"] == "Results"
    assert payload["summary"]["abstention_rate"] == 0.0


def test_a_claim_over_a_document_with_no_full_text_is_never_clean(
    capsys: pytest.CaptureFixture[str], documents: Path, db: str
) -> None:
    """D11, through the CLI. An abstract-only document abstains: `insufficient-passage`, no
    anchors, and `clean: false`. It must never be emitted as a checked claim."""
    run_json(["passages", "index", EMPTY_URL, "--db", db, "--json"], capsys)
    code, payload = run_json(
        ["faithfulness", CLAIM, "--doc", EMPTY_URL, "--db", db, "--json"], capsys
    )
    assert code == 0
    assert_valid("faithfulness-report.schema.json", payload, "faithfulness abstention")
    claim = payload["claims"][0]
    assert claim["verdict"] == "insufficient-passage"
    assert claim["clean"] is False
    assert claim["evidence"] == []
    assert payload["summary"]["coverage"] == 0.0
    assert "unverified_no_fulltext" not in json.dumps(payload)


def test_faithfulness_against_an_unindexed_document_exits_1(
    capsys: pytest.CaptureFixture[str], documents: Path, db: str
) -> None:
    code, _, err = run(
        ["faithfulness", CLAIM, "--doc", "10.9999/never-indexed", "--db", db], capsys
    )
    assert code == 1
    assert "not in the passage index" in err


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------


def test_snapshot_replay_of_one_request_validates(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, payload = run_json(
        ["snapshot", "replay", "crossref", "works/10.1109/cvpr.2016.90", "--json"], capsys
    )
    assert code == 0
    assert_valid("snapshot.schema.json", payload, "snapshot replay")
    assert payload["source"] == "crossref"
    assert payload["response_hash"]


def test_snapshot_replay_of_the_whole_request_set_verifies_every_hash(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "snaps"
    target = SnapshotStore(root)
    source = SnapshotStore(SNAPSHOTS)
    for endpoint in ("works/10.1109/cvpr.2016.90", "works/10.1371/journal.pone.0000308"):
        target.write(source.load("crossref", endpoint, {}))
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(root))

    code, payload = run_json(["snapshot", "replay", "--json"], capsys)
    assert code == 0
    assert_each_valid("snapshot.schema.json", payload, "stored snapshot")
    assert len(payload) == 2


def test_snapshot_replay_of_a_missing_request_exits_1(
    capsys: pytest.CaptureFixture[str], store: Path
) -> None:
    code, _, err = run(["snapshot", "replay", "crossref", "works/10.0000/nope"], capsys)
    assert code == 1
    assert "No snapshot" in err


def test_snapshot_diff_reports_field_level_drift_offline(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The drift report, without the network: a stored snapshot against a live-SHAPED body.

    This is the shape the scheduled canary produces. A retraction appearing on a work is
    exactly the kind of drift a snapshot set must not be allowed to hide.
    """
    root = tmp_path / "snaps"
    target = SnapshotStore(root)
    source = SnapshotStore(SNAPSHOTS)
    stored = source.load("crossref", "works/10.1109/cvpr.2016.90", {})
    target.write(stored)
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(root))

    live = json.loads(json.dumps(stored.response_body))
    live["message"]["title"] = ["Deep Residual Learning for Image Recognition (corrected)"]
    live["message"]["is-referenced-by-count"] = 999999
    live_file = tmp_path / "live.json"
    live_file.write_text(json.dumps(live), encoding="utf-8")

    code, payload = run_json(
        [
            "snapshot", "diff", "crossref", "works/10.1109/cvpr.2016.90",
            "--live-from", str(live_file), "--json",
        ],
        capsys,
    )
    assert code == 0
    assert payload["compared"] == 1
    assert payload["changed"] == 1
    diff = payload["diffs"][0]
    assert diff["changed"] is True
    assert diff["stored_hash"] != diff["live_hash"]
    paths = {field["path"] for field in diff["fields"]}
    assert "message.title[0]" in paths
    assert "message.is-referenced-by-count" in paths


def test_snapshot_diff_of_an_unchanged_body_reports_no_drift(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "snaps"
    target = SnapshotStore(root)
    stored = SnapshotStore(SNAPSHOTS).load("crossref", "works/10.1109/cvpr.2016.90", {})
    target.write(stored)
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_DIR", str(root))
    live_file = tmp_path / "live.json"
    live_file.write_text(json.dumps(stored.response_body), encoding="utf-8")

    code, payload = run_json(
        [
            "snapshot", "diff", "crossref", "works/10.1109/cvpr.2016.90",
            "--live-from", str(live_file), "--json",
        ],
        capsys,
    )
    assert code == 0
    assert payload["changed"] == 0
    assert payload["diffs"][0]["fields"] == []


@pytest.mark.live
def test_snapshot_record_captures_a_live_response(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one command that cannot be tested offline, because recording IS the live call."""
    monkeypatch.setenv("RESEARCHER_CORE_SNAPSHOT_MODE", "live")
    root = tmp_path / "snaps"
    code, payload = run_json(
        [
            "snapshot", "record", "crossref", "works/10.7717/peerj.4375",
            "--store", str(root), "--retrieved-at", "2026-07-14T12:00:00Z", "--json",
        ],
        capsys,
    )
    assert code == 0
    assert_valid("snapshot.schema.json", payload, "recorded snapshot")
    assert payload["retrieved_at"] == "2026-07-14T12:00:00Z"
    assert SnapshotStore(root).count("crossref") == 1


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------


def event(run_id: str, kind: str, ts: str, payload: dict[str, Any]) -> str:
    return json.dumps({"run_id": run_id, "type": kind, "ts": ts, "payload": payload})


def test_provenance_append_emits_a_schema_valid_event(
    capsys: pytest.CaptureFixture[str], ledger: str
) -> None:
    code, payload = run_json(
        [
            "provenance", "append",
            event("run-1", "retrieval", "2026-07-14T12:00:00Z",
                  {"source": "openalex", "query": "self-supervised ECG", "record_count": 5}),
            "--ledger", ledger, "--json",
        ],
        capsys,
    )
    assert code == 0
    assert_valid("provenance-event.schema.json", payload, "appended event")
    # The kernel fills in everything with exactly one correct value; ts stays caller-supplied.
    assert payload["ts"] == "2026-07-14T12:00:00Z"
    assert payload["run_id"] == "run-1"
    assert payload["versions"]["core"] and payload["versions"]["parser"]
    assert payload["protocol_version"]
    assert len(payload["event_id"]) == 64


def test_provenance_append_rejects_an_event_with_no_ts(
    capsys: pytest.CaptureFixture[str], ledger: str
) -> None:
    """ts is caller-supplied on purpose (D15). Generating one here would make two replays of
    the same run produce two different ledgers."""
    code, _, err = run(
        [
            "provenance", "append",
            json.dumps({"run_id": "run-1", "type": "retrieval", "payload": {}}),
            "--ledger", ledger,
        ],
        capsys,
    )
    assert code == 1
    assert "missing required field(s) ts" in err


def test_provenance_append_rejects_an_unknown_event_type(
    capsys: pytest.CaptureFixture[str], ledger: str
) -> None:
    code, _, err = run(
        [
            "provenance", "append",
            event("run-1", "not-an-event", "2026-07-14T12:00:00Z", {}),
            "--ledger", ledger,
        ],
        capsys,
    )
    assert code == 1
    assert "vocabulary is closed" in err


def test_provenance_append_is_append_only(
    capsys: pytest.CaptureFixture[str], ledger: str
) -> None:
    payload = event("run-1", "retrieval", "2026-07-14T12:00:00Z", {"source": "openalex"})
    assert run(["provenance", "append", payload, "--ledger", ledger], capsys)[0] == 0
    code, _, err = run(["provenance", "append", payload, "--ledger", ledger], capsys)
    assert code == 1
    assert "append-only" in err


def _seed_ledger(ledger: str, capsys: pytest.CaptureFixture[str]) -> None:
    events = [
        event("run-1", "retrieval", "2026-07-14T12:00:00Z",
              {"source": "openalex", "query": "ecg", "record_ids": ["a", "b", "c", "d", "e"]}),
        event("run-1", "retrieval", "2026-07-14T12:00:01Z",
              {"source": "crossref", "query": "ecg", "record_ids": ["a", "f", "g"]}),
        event("run-1", "dedup_decision", "2026-07-14T12:00:02Z",
              {"winner": "a", "losers": ["a-dup"], "reason": "doi_exact"}),
    ]
    for item in events:
        assert run(["provenance", "append", item, "--ledger", ledger], capsys)[0] == 0


def test_provenance_prisma_derives_counts_by_aggregation(
    capsys: pytest.CaptureFixture[str], ledger: str
) -> None:
    _seed_ledger(ledger, capsys)
    code, payload = run_json(
        ["provenance", "prisma", "--run-id", "run-1", "--ledger", ledger, "--json"], capsys
    )
    assert code == 0
    assert payload["identified"] == 8
    assert payload["identified_by_source"] == {"crossref": 3, "openalex": 5}
    assert payload["duplicates_removed"] == 1
    assert payload["deduplicated"] == 7
    assert payload["event_counts"] == {"dedup_decision": 1, "retrieval": 2}


def test_provenance_export_is_jsonl_and_round_trips(
    capsys: pytest.CaptureFixture[str], ledger: str
) -> None:
    _seed_ledger(ledger, capsys)
    code, out, _ = run(["provenance", "export", "--run-id", "run-1", "--ledger", ledger], capsys)
    assert code == 0
    lines = out.strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        assert_valid("provenance-event.schema.json", json.loads(line), "exported event")

    code, payload = run_json(
        ["provenance", "export", "--run-id", "run-1", "--ledger", ledger, "--json"], capsys
    )
    assert code == 0
    assert_each_valid("provenance-event.schema.json", payload, "exported event")
    assert [json.loads(line)["event_id"] for line in lines] == [e["event_id"] for e in payload]


def test_provenance_export_writes_a_file(
    capsys: pytest.CaptureFixture[str], ledger: str, tmp_path: Path
) -> None:
    _seed_ledger(ledger, capsys)
    out_path = tmp_path / "export" / "ledger.jsonl"
    code, out, _ = run(
        ["provenance", "export", "--ledger", ledger, "--out", str(out_path)], capsys
    )
    assert code == 0
    assert "exported 3 events" in out
    assert len(out_path.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_provenance_append_reads_stdin_and_a_file(
    capsys: pytest.CaptureFixture[str], ledger: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "event.json"
    path.write_text(
        event("run-2", "record_lineage", "2026-07-14T12:00:00Z",
              {"artifact_id": "10.1/x", "artifact_hash": "0" * 64, "inputs": []}),
        encoding="utf-8",
    )
    assert run(["provenance", "append", str(path), "--ledger", ledger], capsys)[0] == 0

    import io

    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(event("run-2", "retrieval", "2026-07-14T12:00:01Z", {"source": "arxiv"})),
    )
    code, payload = run_json(["provenance", "append", "-", "--ledger", ledger, "--json"], capsys)
    assert code == 0
    assert payload["run_id"] == "run-2"


# ---------------------------------------------------------------------------
# The record projection, unit-tested where the edge cases live
# ---------------------------------------------------------------------------


def test_record_json_moves_lists_out_of_the_csl_namespace() -> None:
    record = CSLRecord(
        id="10.1234/x",
        title="A Title",
        DOI="10.1234/x",
        ISSN=["1949-3045", "2371-9850"],
        keyword=["ecg", "self-supervised"],
    )
    data = cli.record_json(record)
    assert "ISSN" not in data and "keyword" not in data
    assert data["custom"]["issn"] == ["1949-3045", "2371-9850"]
    assert data["custom"]["keywords"] == ["ecg", "self-supervised"]
    assert_valid("record.schema.json", data, "projected record")


def test_record_json_leaves_a_record_without_lists_alone() -> None:
    record = CSLRecord(id="10.1234/x", title="A Title", DOI="10.1234/x")
    data = cli.record_json(record)
    assert data["DOI"] == "10.1234/x"
    assert_valid("record.schema.json", data, "plain record")
