"""Malformed free-text queries must not become source errors.

The bug this file pins down was found by the M2 identity benchmark, on one real gold item:
the LOOP-study title, truncated by a citation manager to end in an orphan "(" .

    "Implantable loop recorder detection of atrial fibrillation to prevent stroke (The LOOP Stu"

Sent raw, DataCite answers HTTP 400 (a Lucene ``parse_exception``), which the kernel raises
as a SourceError. Nothing unsafe follows from that: verify.py maps ``source_error`` to
``inconclusive``, so per D9 the reference is never refused. But it is the kernel blaming
DataCite for a query the kernel itself malformed, and the user is never told the real
reason their citation could not be confirmed. Titles arrive truncated, brace-mangled, and
colon-laden from every citation manager in existence; this is ordinary input, not an edge
case.

Two failure modes are under test, and the second is the dangerous one:

* **Loud:** a SourceError where there should have been an answer (DataCite 400 on an
  unbalanced bracket / quote / backslash / dangling AND; arXiv 400 on a trailing
  backslash).
* **Quiet:** HTTP 200 with zero hits, where the query never parsed at all (DataCite for a
  colon, arXiv for an unbalanced brace). This one is worse, because a zero-hit answer is a
  CLEAN NEGATIVE, and a clean negative is the only outcome D9 permits to build toward a
  refusal-grade verdict. A broken query must never be able to manufacture one.

The regression that matters most is neither of those: it is
``test_a_clean_title_is_passed_through_untouched``. The sanitizer runs on EVERY query, so
mangling the 99% clean case to rescue the 1% broken one would be a far worse bug than the
one being fixed.

Everything here runs offline through httpx.MockTransport, which captures the outgoing
request so the test can assert on the exact query string that would have gone over the
wire. The handful of tests marked ``live`` hit the real APIs and are deselected by default
(``addopts = -m 'not live'`` in core/pyproject.toml).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from researcher_core.cache import ResponseCache
from researcher_core.connectors import get_connector_class
from researcher_core.connectors.base import BaseConnector, escape_lucene, sanitize_query
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore

#: Where the throwaway snapshot store lives for the current test. Every session below is
#: LIVE, so nothing is ever written there; the store still needs somewhere to point.
_STORE_ROOT: Path | None = None


@pytest.fixture(autouse=True)
def _snapshot_root(tmp_path: Path) -> Iterator[None]:
    """Give the module-level helpers a per-test store root under tmp_path."""
    global _STORE_ROOT
    _STORE_ROOT = tmp_path / "snapshots"
    yield
    _STORE_ROOT = None


def live_mode_session() -> SnapshotSession:
    """A LIVE session with caching off, so every call really re-asks the transport."""
    assert _STORE_ROOT is not None, "the _snapshot_root fixture did not run"
    return SnapshotSession(
        SnapshotStore(_STORE_ROOT), SnapshotMode.LIVE, cache=ResponseCache.disabled()
    )

# The gold item that exposed the bug, and the paper it must still find.
TRUNCATED_LOOP_TITLE = (
    "Implantable loop recorder detection of atrial fibrillation to prevent stroke "
    "(The LOOP Stu"
)
LOOP_DOI = "10.1016/s0140-6736(21)01698-6"

#: Every source whose search() takes free text. OpenCitations and Unpaywall are absent on
#: purpose: both declare search unsupported and raise rather than query anything.
SEARCH_SOURCES = ("openalex", "crossref", "datacite", "semantic_scholar", "arxiv", "pubmed")

#: One malformed title per class of breakage, each a plausible .bib field.
MALFORMED_TITLES: dict[str, str] = {
    "truncated_open_paren": TRUNCATED_LOOP_TITLE,
    "unbalanced_close_paren": "Deep residual learning for image recognition)",
    "unbalanced_quote": 'Attention is all you "need',
    "unbalanced_brace": "Attention is all you need}",
    "unbalanced_bracket": "Attention is all you need [",
    "trailing_backslash": "Attention is all you need \\",
    "bare_and": "Attention is all you need AND",
    "bare_or": "OR gates in DNA strand displacement",
    "bare_not": "NOT gates in DNA strand displacement",
    "colon": "Attention: is all you need",
    "slash": "CRISPR/Cas9 genome editing",
    "everything_at_once": 'A survey of {LLM} agents: "planning AND tools\\ (part',
}

#: Titles with nothing wrong with them. These must come out byte-for-byte identical.
CLEAN_TITLES: tuple[str, ...] = (
    "Attention is all you need",
    "Deep residual learning for image recognition",
    # Punctuation that is ordinary in a real title and must survive: balanced parens and
    # quotes, a colon, a slash, a hyphen, an apostrophe, an ampersand, unicode, and a
    # lowercase "and" that is a word and not an operator.
    "Implantable loop recorder detection of atrial fibrillation (The LOOP Study)",
    "Attention: a survey of transformer architectures",
    "CRISPR/Cas9 and its off-target effects",
    'The "hard problem" of consciousness',
    "Schrodinger's cat and Bell's theorem",
    "Alzheimer's disease: amyloid-beta and tau",
    "Ubiquitous naive Bayes [extended abstract] (2nd edition)",
    "Signal & noise in fMRI at 3T",
)


def run(coro: Any) -> Any:
    """Drive one coroutine to completion on a fresh event loop."""
    return asyncio.run(coro)


def datacite_expected(title: str) -> str:
    """What DataCite should end up sending for ``title``: slash to space, then escaped."""
    return escape_lucene(" ".join(sanitize_query(title).replace("/", " ").split()))


class QueryRecorder:
    """A mock transport that records every outgoing request and replies with an empty page.

    The bodies below are the empty-result shape of each API, so ``search`` parses them into
    a clean negative. What the tests actually assert on is :attr:`requests`: the exact URL
    the connector WOULD have sent. A query that never leaves the process cannot 400.
    """

    EMPTY_BODIES: dict[str, Any] = {
        "openalex": {"meta": {"count": 0}, "results": []},
        "crossref": {"status": "ok", "message": {"items": []}},
        "datacite": {"data": [], "meta": {"total": 0}},
        "semantic_scholar": {"total": 0, "data": []},
        "pubmed": {"esearchresult": {"count": "0", "idlist": []}},
    }
    ARXIV_EMPTY_FEED = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<opensearch:totalResults "
        'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:totalResults>'
        "</feed>"
    )

    def __init__(self, source: str) -> None:
        self.source = source
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.source == "arxiv":
            return httpx.Response(
                200,
                text=self.ARXIV_EMPTY_FEED,
                headers={"Content-Type": "application/atom+xml"},
            )
        return httpx.Response(200, json=self.EMPTY_BODIES[self.source])

    # -- what the connector asked the API ----------------------------------

    @property
    def sent(self) -> httpx.Request:
        assert self.requests, "the connector sent no request at all"
        return self.requests[0]

    def param(self, name: str) -> str:
        """One query parameter off the recorded URL, url-decoded."""
        values = parse_qs(urlsplit(str(self.sent.url)).query).get(name, [])
        return values[0] if values else ""

    def free_text(self) -> str:
        """The parameter each source carries the user's free text in."""
        return self.param(
            {
                "openalex": "search",
                "crossref": "query.bibliographic",
                "datacite": "query",
                "semantic_scholar": "query",
                "arxiv": "search_query",
                "pubmed": "term",
            }[self.source]
        )


def connector_with(source: str, recorder: QueryRecorder) -> BaseConnector:
    """A LIVE-mode connector wired to a mock transport. Never reaches the network."""
    connector = get_connector_class(source)(
        snapshots=live_mode_session(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(recorder)),
    )
    connector.max_retries = 0
    connector.rate_limit_interval = 0.0
    return connector


def search_capturing(source: str, query: str, **kwargs: Any) -> QueryRecorder:
    """Run ``search`` against a mock transport and hand back what it sent."""
    recorder = QueryRecorder(source)

    async def drive() -> None:
        async with connector_with(source, recorder) as connector:
            await connector.search(query, **kwargs)

    run(drive())
    return recorder


# ---------------------------------------------------------------------------
# The regression that matters: a clean title is not touched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("title", CLEAN_TITLES)
def test_a_clean_title_is_passed_through_untouched(title: str) -> None:
    """Nothing to fix means nothing is changed. Not "roughly preserved": identical.

    This is the whole safety case for running a sanitizer on every query. Balanced parens,
    balanced quotes, a colon, a slash, a hyphen, an apostrophe, an ampersand: all ordinary
    title punctuation, all left alone. If this test ever fails, the sanitizer has started
    degrading the common case in order to rescue the rare one, and that is a worse bug than
    the one it was written to fix.
    """
    assert sanitize_query(title) == title


@pytest.mark.parametrize("source", SEARCH_SOURCES)
@pytest.mark.parametrize("title", CLEAN_TITLES)
def test_a_clean_title_reaches_every_source_intact(source: str, title: str) -> None:
    """And it survives the trip through each connector's own query construction.

    Each source wraps the text differently (arXiv in ``all:"..."``, DataCite in Lucene
    escapes), so the assertion is containment of the meaningful words rather than equality,
    except for the sources that pass free text straight through, which must be exact.
    """
    sent = search_capturing(source, title).free_text()
    if source in ("openalex", "crossref", "semantic_scholar", "pubmed"):
        assert sent == title
    elif source == "datacite":
        # Escaped, but losslessly: dropping the escapes gives back the original, modulo the
        # slash, which DataCite substitutes with a space (Elasticsearch rejects "\/").
        assert sent == datacite_expected(title)
        assert sent.replace("\\", "") == title.replace("/", " ")
    else:  # arxiv wraps in all:"...", stripping the quotes it would otherwise break on
        assert 'all:"' in sent
        assert title.replace('"', " ").strip().split()[0] in sent


def test_the_sanitizer_is_idempotent() -> None:
    """Sanitizing twice equals sanitizing once, for clean and broken input alike."""
    for title in (*CLEAN_TITLES, *MALFORMED_TITLES.values()):
        once = sanitize_query(title)
        assert sanitize_query(once) == once


# ---------------------------------------------------------------------------
# The reported bug: the truncated LOOP title
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", SEARCH_SOURCES)
def test_the_truncated_loop_title_no_longer_raises_on_any_source(source: str) -> None:
    """The exact gold item that skipped the identity benchmark. No source may raise."""
    recorder = search_capturing(source, TRUNCATED_LOOP_TITLE)
    assert recorder.requests, f"{source} sent no request"


def test_the_truncated_loop_title_keeps_every_word_it_had() -> None:
    """The orphan "(" is dropped. Nothing else is: the title is still a good search string.

    Over-sanitizing would "fix" the bug by destroying the query, which is the failure mode
    the fix must not have. Every word survives; only the unmatched bracket goes.
    """
    cleaned = sanitize_query(TRUNCATED_LOOP_TITLE)
    assert "(" not in cleaned
    assert cleaned == (
        "Implantable loop recorder detection of atrial fibrillation to prevent stroke "
        "The LOOP Stu"
    )
    assert cleaned.split() == [w for w in TRUNCATED_LOOP_TITLE.replace("(", "").split()]


# ---------------------------------------------------------------------------
# Every class of malformed title, on every source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", SEARCH_SOURCES)
@pytest.mark.parametrize("label", sorted(MALFORMED_TITLES))
def test_malformed_titles_produce_a_request_not_an_exception(source: str, label: str) -> None:
    """An unbalanced ')', '"', '}', a trailing '\\', a bare AND/OR/NOT, a ':' and a '/'.

    Each one goes out as a well-formed request. None of them raises, on any source.
    """
    recorder = search_capturing(source, MALFORMED_TITLES[label])
    assert recorder.requests, f"{source} sent no request for {label}"


@pytest.mark.parametrize("label", sorted(MALFORMED_TITLES))
def test_no_malformed_title_leaves_an_unbalanced_delimiter(label: str) -> None:
    """The invariant the query parsers actually care about, asserted on the sanitizer."""
    cleaned = sanitize_query(MALFORMED_TITLES[label])
    assert cleaned.count('"') % 2 == 0, "an unpaired quote survived"
    assert "\\" not in cleaned, "a backslash survived"
    for opener, closer in (("(", ")"), ("[", "]"), ("{", "}")):
        assert cleaned.count(opener) == cleaned.count(closer), f"unbalanced {opener}{closer}"


@pytest.mark.parametrize("source", SEARCH_SOURCES)
def test_a_trailing_backslash_never_reaches_a_source_unescaped(source: str) -> None:
    """arXiv answers HTTP 400 to this one: the backslash escapes its own closing quote.

    DataCite answers 400 too (``token_mgr_error``). The only backslashes allowed in an
    outgoing query are the ones DataCite's own Lucene escaper deliberately put there.
    """
    sent = search_capturing(source, "Attention is all you need \\").free_text()
    if source == "datacite":
        assert "\\\\" not in sent  # no escaped literal backslash, i.e. the input's is gone
    else:
        assert "\\" not in sent


def test_bare_boolean_operators_are_defused_but_the_words_survive() -> None:
    """Lowercased, not deleted.

    Uppercase is what makes AND / OR / NOT operators in Lucene, in Entrez, and in the arXiv
    API; lowercase is a plain term to all three. So lowercasing removes the operator and
    keeps the token, which matters for a title like "NOT gates in DNA strand displacement",
    where the word is the subject of the paper. Every index lowercases at analysis time
    anyway, so the search is unchanged.
    """
    assert sanitize_query("NOT gates in DNA strand displacement") == (
        "not gates in DNA strand displacement"
    )
    assert sanitize_query("Attention is all you need AND") == "Attention is all you need and"
    assert sanitize_query("R AND D") == "R and D"
    # Only whole uppercase words. Real words that merely contain them are untouched.
    for safe in ("Android malware detection", "Nothing but a NOR gate", "Ordinary least squares"):
        assert sanitize_query(safe) == safe


def test_only_the_unbalanced_bracket_is_dropped() -> None:
    """Surgical, not scorched-earth: a balanced pair inside a broken string still survives."""
    assert sanitize_query("A study (2nd ed.) of things (part") == "A study (2nd ed.) of things part"
    assert sanitize_query("Effects [n=40] on cells]") == "Effects [n=40] on cells"
    # Mismatched nesting: both halves are orphans, both go, the words stay.
    assert sanitize_query("A study (of things]") == "A study of things"


def test_only_the_unpaired_quote_is_dropped() -> None:
    """A quoted phrase keeps its quotes; the one stray quote is the one that goes."""
    assert sanitize_query('The "hard problem" of "consciousness') == (
        'The "hard problem" of consciousness'
    )


# ---------------------------------------------------------------------------
# The empty query: a clean negative, never a request and never a SourceError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", SEARCH_SOURCES)
@pytest.mark.parametrize("junk", ["", "   ", "\\", "(((", ")))", '"', "{}[]()", "\\\\\\", "\n\t"])
def test_a_query_that_sanitizes_to_nothing_is_a_clean_negative(source: str, junk: str) -> None:
    """Empty after sanitization means [], with NO request sent and NO SourceError raised.

    Firing a request with an empty ``q`` would be the worst of both worlds: it burns the
    source's rate limit and it invites a 400. And raising SourceError for it would be a lie
    (nothing failed). The query simply asked nothing, so the answer is nothing.
    """
    recorder = QueryRecorder(source)

    async def drive() -> list[Any]:
        async with connector_with(source, recorder) as connector:
            return await connector.search(junk)

    assert run(drive()) == []
    assert recorder.requests == [], f"{source} sent a request for an empty query"


def test_empty_sanitizes_to_empty() -> None:
    for junk in ("", "   ", "\\", "(((", '"""', "{}[]()", "\n\t\r"):
        assert sanitize_query(junk) == ""


# ---------------------------------------------------------------------------
# Per-source escaping, where the grammars genuinely differ
# ---------------------------------------------------------------------------


def test_datacite_escapes_lucene_syntax_and_the_others_do_not() -> None:
    """DataCite's ``query`` IS a Lucene expression. The rest take plain relevance text.

    Escaping the plain-text sources would be its own bug: a backslash sent to Semantic
    Scholar or Crossref is a character they try to match on, not an escape.
    """
    title = "Attention: is all you need (2017)"
    assert search_capturing("datacite", title).free_text() == (
        "Attention\\: is all you need \\(2017\\)"
    )
    for plain in ("openalex", "crossref", "semantic_scholar", "pubmed"):
        sent = search_capturing(plain, title).free_text()
        assert sent == title
        assert "\\" not in sent


def test_datacite_substitutes_the_slash_instead_of_escaping_it() -> None:
    """Escaping this one would have been the obvious move, and it is a 400.

    Elasticsearch's lexer rejects ``\\/`` outright (``token_mgr_error``), so a "correct"
    Lucene escape of "CRISPR/Cas9" would break the very ordinary titles it was meant to
    protect. A bare slash cannot simply be left alone either: a second one pairs with it
    into a Lucene regex (``/pattern/``) and the query quietly stops meaning what it says.
    Substituting a space settles it. DataCite tokenizes on the slash anyway, so it is the
    same query, and no regex delimiter is left to pair up.
    """
    sent = search_capturing("datacite", "CRISPR/Cas9 genome editing").free_text()
    assert sent == "CRISPR Cas9 genome editing"
    assert "\\/" not in sent
    assert "/" not in sent
    # Two slashes: neither survives, so no regex can form.
    assert "/" not in search_capturing("datacite", "CRISPR/Cas9 and TALEN/ZFN").free_text()
    # The other sources are happy with a raw slash and must keep it verbatim.
    for plain in ("openalex", "crossref", "semantic_scholar", "pubmed"):
        assert "CRISPR/Cas9" in search_capturing(plain, "CRISPR/Cas9 genome editing").free_text()


def test_datacite_escapes_the_colon_that_silently_returned_zero_hits() -> None:
    """The quiet failure. DataCite reads "Attention:" as a field name and matches nothing.

    Unescaped, ``query=Attention: Is All You Need`` is HTTP 200 with total=0, which the
    kernel would record as a CLEAN NEGATIVE and D9 would let count toward a refusal.
    Escaped, the same title returns the 2371 records it should.
    """
    sent = search_capturing("datacite", "Attention: Is All You Need").free_text()
    assert sent == "Attention\\: Is All You Need"


def test_datacite_does_not_escape_its_own_since_clause() -> None:
    """The user's text is escaped; the operators WE wrap around it must not be.

    ``(<escaped text>) AND publicationYear:[2020 TO *]`` is Lucene we wrote on purpose. If
    the escaper ran over the finished expression, our own parens, colon, and brackets would
    become literals and the year filter would silently stop filtering.
    """
    sent = search_capturing("datacite", "Attention (2017", since=2020).free_text()
    assert sent == "(Attention 2017) AND publicationYear:[2020 TO *]"
    assert sent.startswith("(")
    assert sent.endswith("]")


def test_escape_lucene_covers_every_reserved_character() -> None:
    for char in '+-=&|><!(){}[]^"~*?:\\':
        assert escape_lucene(f"a{char}b") == f"a\\{char}b"
    # The slash is reserved by Lucene but its ESCAPE is rejected by Elasticsearch, so it is
    # deliberately not in the set. Escaping it is how DataCite got a 400 for "CRISPR/Cas9".
    assert escape_lucene("CRISPR/Cas9") == "CRISPR/Cas9"
    # Ordinary characters are never escaped.
    for char in "abc XYZ 123 .,;'%$#@":
        assert escape_lucene(char) == char


def test_arxiv_still_builds_a_terminated_phrase_query() -> None:
    """The trailing backslash that made arXiv answer 400 is gone before it builds all:"..."."""
    sent = search_capturing("arxiv", "Attention is all you need \\").free_text()
    assert sent == 'all:"Attention is all you need"'
    assert sent.count('"') % 2 == 0


# ---------------------------------------------------------------------------
# Live: the fix has to work against the real APIs, not just a mock
# ---------------------------------------------------------------------------


@pytest.fixture()
def live_session() -> SnapshotSession:
    """A real LIVE session. Only the ``live``-marked tests below use it."""
    return live_mode_session()


def live_search(source: str, session: SnapshotSession, query: str) -> list[Any]:
    async def drive() -> list[Any]:
        async with get_connector_class(source)(snapshots=session) as connector:
            return await connector.search(query, limit=5)

    return run(drive())


@pytest.mark.live
def test_live_truncated_loop_title_still_finds_the_real_paper(
    live_session: SnapshotSession,
) -> None:
    """The point of the whole exercise: sanitized, the broken title STILL finds the paper.

    Semantic Scholar is the assertion source because it indexes the LOOP study and its
    search endpoint takes plain relevance text. DataCite is not asserted on: it does not
    index this Lancet DOI at all (Crossref registered it), so its honest answer is and
    always was zero.
    """
    records = live_search("semantic_scholar", live_session, TRUNCATED_LOOP_TITLE)
    dois = [(record.DOI or "").lower() for record in records]
    assert LOOP_DOI in dois


@pytest.mark.live
@pytest.mark.parametrize("source", SEARCH_SOURCES)
def test_live_no_source_errors_on_the_truncated_title(
    source: str, live_session: SnapshotSession
) -> None:
    """Against the real APIs, not a mock: the title that 400'd DataCite now goes through."""
    live_search(source, live_session, TRUNCATED_LOOP_TITLE)  # must not raise


@pytest.mark.live
def test_live_datacite_colon_no_longer_silently_returns_nothing(
    live_session: SnapshotSession,
) -> None:
    """The quiet failure, against the live index: escaped, the colon title finds records."""
    assert live_search("datacite", live_session, "Attention: Is All You Need")


@pytest.mark.live
@pytest.mark.parametrize("label", sorted(MALFORMED_TITLES))
def test_live_datacite_accepts_every_malformed_title(
    label: str, live_session: SnapshotSession
) -> None:
    """DataCite 400'd on most of these. Every one is now a well-formed Lucene query."""
    live_search("datacite", live_session, MALFORMED_TITLES[label])  # must not raise


@pytest.mark.live
@pytest.mark.parametrize("label", sorted(MALFORMED_TITLES))
def test_live_arxiv_accepts_every_malformed_title(
    label: str, live_session: SnapshotSession
) -> None:
    """arXiv 400'd on the trailing backslash. It no longer sees one."""
    live_search("arxiv", live_session, MALFORMED_TITLES[label])  # must not raise


@pytest.mark.live
@pytest.mark.parametrize("title", CLEAN_TITLES)
def test_live_datacite_accepts_every_clean_title(
    title: str, live_session: SnapshotSession
) -> None:
    """The sanitizer must not break what already worked, and this is checked against the
    real index rather than a mock, because a mock cannot tell you that Elasticsearch
    rejects an escape sequence.

    It is not a hypothetical. The first version of the DataCite escaper did the textbook
    thing and escaped ``/`` along with the rest of Lucene's reserved set, and this test is
    what caught it: "CRISPR/Cas9 and its off-target effects" is a perfectly clean title, and
    the "fix" turned it into an HTTP 400 that the raw title never produced. A sanitizer that
    breaks clean input is worse than the bug it set out to repair.
    """
    live_search("datacite", live_session, title)  # must not raise
