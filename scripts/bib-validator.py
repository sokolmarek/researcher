#!/usr/bin/env python3
"""Validate .bib entries: multi-source via researcher-core, CrossRef-only without it.

Usage:
    python bib-validator.py <path-to-library.bib>
    python bib-validator.py library.bib --check-doi --check-retracted --check-fields
    python bib-validator.py library.bib --check-duplicates
    python bib-validator.py library.bib --verbose

Checks (all enabled by default; pass one or more --check-* flags to run a subset):
    --check-doi         DOI presence, index resolution (a 404 and a network error are
                        reported differently), title similarity, first-author surname
                        match, year match
    --check-retracted   Retraction and other editorial notices
    --check-fields      Required fields per entry type
    --check-duplicates  Duplicate citation keys and duplicate DOIs

TWO ENGINES, ONE CLI. The flags above mean the same thing either way:

1. researcher-core (preferred). When `uv` and `core/` are both present, the network
   checks run through `python -m researcher_core verify-bib <file> --json`: several
   indexes (OpenAlex, Crossref, DataCite, ...) instead of CrossRef alone, the D9 axis
   (a) identity verdict (verified / mismatch / unresolvable / inconclusive), and the
   axis (b) publication status (current / corrected / retracted / expression-of-concern).
2. stdlib fallback. When uv or core is missing, unrunnable, or too old to know the
   command, the M1 CrossRef-only logic below runs unchanged. THE PLUGIN NEVER HARD-FAILS
   WITHOUT CORE (D3): a user who installed the plugin but not uv gets exactly the M1
   behavior, and every fallback path is exercised by scripts/tests/test_core_fallback.py.

Engine selection is environment-only, so the flags stay identical across both:
    RESEARCHER_CORE=off            force the stdlib fallback
    RESEARCHER_CORE_PROJECT=<dir>  where core/ lives (default: ${CLAUDE_PLUGIN_ROOT}/core,
                                   else the core/ next to this script). Naming a directory
                                   with no pyproject.toml means "core is absent", and that
                                   answer is final: no other core on the machine is used.
    RESEARCHER_CORE_CMD=<argv>     run core through this command instead of uv (JSON list
                                   or a shell-style string); the seam the tests use
    RESEARCHER_CORE_TIMEOUT=<secs> per-call budget (default 120)

Parsing: a brace-aware tokenizer, not a regex. Handles nested braces in values
({A {Nested} Title}), quoted values ("..."), bare numeric values, compact entries
whose closing brace sits on the last field line (...}}), string concatenation
with #, and skips @comment/@preamble/@string blocks. This parser is also what the
commit guard and the draft-integrity hook use, so all three agree on what an entry is.

Verdicts are NAMED per entry, so a pass is stated rather than inferred from silence.

Stdlib fallback (DOI VERDICTS block), tri-state resolution plus the two error states:
    confirmed          the DOI resolved against CrossRef
    no-doi             the entry carries no DOI, so nothing could be verified
    resolution-failed  the lookup could not complete (network error or timeout)
    not-found          CrossRef returned 404: the DOI does not exist (an ERROR)
    retracted          the DOI resolved but CrossRef flags a retraction (an ERROR)
    not-checked        no network check was requested for this run
A failed resolution is never laundered into a pass: resolution-failed is its own
verdict, distinct from confirmed.

Core engine (EVIDENCE VERDICTS block), the D9/D16 axes:
    axis (a) identity  verified | mismatch | unresolvable | inconclusive
    axis (b) status    current | corrected | retracted | expression-of-concern
Only `unresolvable` and `mismatch` are refusal-grade and count as errors; `inconclusive`
is NEVER refusal-grade (a source that timed out is not evidence of fabrication) and is
reported as a warning. A retracted entry is an error here, as it was in M1: this is a
validator a human runs on purpose, not the commit gate, which reports retractions
without blocking on them.

Exit code 1 when errors are found, 0 otherwise. Network problems never count as
entry errors; they are reported as warnings so offline runs stay useful.
"""

import argparse
import difflib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

TITLE_SIMILARITY_THRESHOLD = 0.70

# Per-entry DOI verdicts. Tri-state resolution (confirmed / no-doi /
# resolution-failed) plus the two states that are outright errors and the
# "you did not ask for a network check" state.
VERDICT_CONFIRMED = "confirmed"
VERDICT_NO_DOI = "no-doi"
VERDICT_RESOLUTION_FAILED = "resolution-failed"
VERDICT_NOT_FOUND = "not-found"
VERDICT_RETRACTED = "retracted"
VERDICT_NOT_CHECKED = "not-checked"

VERDICT_ORDER = [
    VERDICT_CONFIRMED,
    VERDICT_NO_DOI,
    VERDICT_RESOLUTION_FAILED,
    VERDICT_NOT_FOUND,
    VERDICT_RETRACTED,
    VERDICT_NOT_CHECKED,
]

# Axis (a) identity verdicts (D9). Only these two are refusal-grade.
REFUSAL_GRADE = ("unresolvable", "mismatch")
IDENTITY_ORDER = ["verified", "mismatch", "unresolvable", "inconclusive"]
STATUS_ORDER = ["current", "corrected", "retracted", "expression-of-concern"]

DEFAULT_CORE_TIMEOUT = 120.0


# ---------------------------------------------------------------------------
# The core bridge
#
# One resolver, one runner, shared by this script and by both hooks (they load it
# from here, so there is a single definition of "is core available and what does it
# say"). Every function here is total: it returns None rather than raising, because
# a missing, broken, or slow core must degrade to the stdlib path, never take the
# caller down with it (D3).
# ---------------------------------------------------------------------------

def core_disabled() -> bool:
    return os.environ.get("RESEARCHER_CORE", "").strip().lower() in {"off", "0", "no", "false"}


def core_project_dir() -> Path:
    """Where core/ lives. The env var wins, then the plugin root, then this checkout."""
    override = os.environ.get("RESEARCHER_CORE_PROJECT")
    if override:
        return Path(override)
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        return Path(plugin_root) / "core"
    return Path(__file__).resolve().parent.parent / "core"


def core_project_is_explicit() -> bool:
    return bool(os.environ.get("RESEARCHER_CORE_PROJECT"))


def core_timeout() -> float:
    try:
        return float(os.environ.get("RESEARCHER_CORE_TIMEOUT", DEFAULT_CORE_TIMEOUT))
    except ValueError:
        return DEFAULT_CORE_TIMEOUT


def core_command():
    """Argv prefix that runs the researcher_core CLI, or None when core is unavailable.

    Preference order: an explicit RESEARCHER_CORE_CMD, then `uv run --project <core>`
    (the documented invocation, D3), then a researcher_core already importable by this
    interpreter (the `pip install -e core/` path). None means "fall back", never "fail".
    """
    if core_disabled():
        return None

    explicit = os.environ.get("RESEARCHER_CORE_CMD")
    if explicit:
        try:
            parsed = json.loads(explicit)
        except (ValueError, TypeError):
            parsed = shlex.split(explicit)
        if isinstance(parsed, str):
            parsed = shlex.split(parsed)
        argv = [str(part) for part in parsed if str(part)]
        return argv or None

    project = core_project_dir()
    has_project = (project / "pyproject.toml").is_file()
    if has_project and shutil.which("uv"):
        return ["uv", "run", "--project", str(project), "python", "-m", "researcher_core"]
    if core_project_is_explicit() and not has_project:
        # The caller named a core and it is not there. That answer is authoritative:
        # do not quietly fall through to some other researcher_core on the machine.
        return None

    try:
        if importlib.util.find_spec("researcher_core") is not None:
            return [sys.executable, "-m", "researcher_core"]
    except (ImportError, ValueError):
        pass
    return None


def run_core(args, timeout=None):
    """Run one core command with --json and return the parsed object, or None.

    None covers every way core can fail to answer: uv absent, core absent, the
    installed core too old to know the subcommand, a crash, a timeout, output that is
    not JSON. The caller falls back; it never sees an exception.

    The return code is deliberately NOT the gate: a verification CLI may exit non-zero
    precisely BECAUSE it found refusal-grade entries, and that report is the answer we
    came for. A parsed JSON object on stdout is the contract; anything else is a miss.
    """
    command = core_command()
    if command is None:
        return None
    try:
        proc = subprocess.run(
            command + [str(a) for a in args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or core_timeout(),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    try:
        payload = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def core_verify_bib(bib_path, timeout=None):
    """The axis (a)/(b)/(d) report for a .bib file, or None when core cannot answer.

    Shape: core/schemas/verification-report.schema.json. A payload without an `entries`
    list is not that schema, so it is treated as a miss rather than trusted.
    """
    report = run_core(["verify-bib", str(bib_path), "--json"], timeout=timeout)
    if not report or not isinstance(report.get("entries"), list):
        return None
    return report


def core_findings(report):
    """Flatten a verification report into one plain dict per entry.

    Keys: key, doi, title, verdict (axis a), refusal_grade, reason, status (axis b),
    status_checked, accessibility (axis d). Missing pieces degrade to safe defaults so a
    caller never has to defend against a half-populated report.
    """
    findings = []
    for entry in report.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        reference = entry.get("reference") or {}
        status = entry.get("status") or {}
        accessibility = entry.get("accessibility") or {}
        verdict = entry.get("verdict") or "inconclusive"
        findings.append({
            "key": entry.get("key") or "?",
            "doi": (reference.get("doi") or "") if isinstance(reference, dict) else "",
            "title": (reference.get("title") or "") if isinstance(reference, dict) else "",
            "verdict": verdict,
            # Trust the flag when core sets it, but never let a missing flag turn a
            # refusal-grade verdict into a soft one.
            "refusal_grade": bool(entry.get("refusal_grade")) or verdict in REFUSAL_GRADE,
            "reason": entry.get("reason") or "",
            "status": status.get("verdict") or "current",
            "status_checked": status.get("checked", True),
            "accessibility": accessibility.get("verdict") or "",
        })
    return findings


# ---------------------------------------------------------------------------
# Parsing (brace-aware tokenizer)
# ---------------------------------------------------------------------------

SKIP_ENTRY_TYPES = {"comment", "preamble", "string"}


class _Cursor:
    def __init__(self, text):
        self.text = text
        self.pos = 0

    def eof(self):
        return self.pos >= len(self.text)

    def peek(self):
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def advance(self):
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def skip_ws(self):
        while not self.eof() and self.text[self.pos].isspace():
            self.pos += 1


def _read_balanced_braces(cur):
    """cur sits ON the opening '{'. Returns inner content; cur ends past the closing '}'."""
    assert cur.peek() == "{"
    cur.advance()
    depth = 1
    out = []
    while not cur.eof():
        ch = cur.advance()
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return "".join(out)
        out.append(ch)
    return "".join(out)  # unterminated; return what we have


def _read_quoted(cur):
    """cur sits ON the opening '"'. Braces may nest inside; the closing quote counts
    only at brace depth 0. Returns inner content; cur ends past the closing quote."""
    assert cur.peek() == '"'
    cur.advance()
    depth = 0
    out = []
    while not cur.eof():
        ch = cur.advance()
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == '"' and depth == 0:
            return "".join(out)
        out.append(ch)
    return "".join(out)


def _read_bare(cur):
    """Bare value (number or macro name) up to a top-level ',' '}' '#' or whitespace."""
    out = []
    while not cur.eof() and cur.peek() not in ",}#" and not cur.peek().isspace():
        out.append(cur.advance())
    return "".join(out)


def _read_value(cur):
    """Read one field value, honoring # concatenation."""
    parts = []
    while True:
        cur.skip_ws()
        ch = cur.peek()
        if ch == "{":
            parts.append(_read_balanced_braces(cur))
        elif ch == '"':
            parts.append(_read_quoted(cur))
        else:
            parts.append(_read_bare(cur))
        cur.skip_ws()
        if cur.peek() == "#":
            cur.advance()
            continue
        return "".join(parts)


def parse_bib(bib_path_or_text) -> list:
    """Parse BibTeX into a list of entry dicts: {type, key, <fields...>}."""
    if isinstance(bib_path_or_text, (str, Path)) and "\n" not in str(bib_path_or_text) and Path(str(bib_path_or_text)).exists():
        content = Path(bib_path_or_text).read_text(encoding="utf-8", errors="replace")
    else:
        content = str(bib_path_or_text)

    entries = []
    cur = _Cursor(content)
    while not cur.eof():
        if cur.advance() != "@":
            continue
        # entry type
        start = cur.pos
        while not cur.eof() and (cur.peek().isalnum() or cur.peek() == "_"):
            cur.advance()
        entry_type = cur.text[start:cur.pos].lower()
        cur.skip_ws()
        if cur.peek() != "{":
            continue
        if entry_type in SKIP_ENTRY_TYPES:
            _read_balanced_braces(cur)
            continue
        cur.advance()  # consume '{'

        # citation key: up to the first top-level ',' (or '}' for keyless entries)
        key_chars = []
        while not cur.eof() and cur.peek() not in ",}":
            key_chars.append(cur.advance())
        key = "".join(key_chars).strip()
        entry = {"type": entry_type, "key": key}

        if cur.peek() == ",":
            cur.advance()

        # fields
        while True:
            cur.skip_ws()
            if cur.eof():
                break
            if cur.peek() == "}":
                cur.advance()
                break
            if cur.peek() == ",":
                cur.advance()
                continue
            fstart = cur.pos
            while not cur.eof() and (cur.peek().isalnum() or cur.peek() in "_-"):
                cur.advance()
            field_name = cur.text[fstart:cur.pos].strip().lower()
            cur.skip_ws()
            if cur.peek() != "=":
                # malformed; skip to next separator to avoid an infinite loop
                while not cur.eof() and cur.peek() not in ",}":
                    cur.advance()
                continue
            cur.advance()  # '='
            value = _read_value(cur).strip()
            if field_name:
                entry[field_name] = value

        if key or len(entry) > 2:
            entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# CrossRef resolution and metadata comparison
# ---------------------------------------------------------------------------

def resolve_doi(doi: str):
    """Resolve a DOI via CrossRef. Returns (status, metadata) where status is
    'ok', 'not_found' (HTTP 404: the DOI does not exist in CrossRef), or
    'error' (network problem, timeout, or unexpected HTTP status)."""
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    headers = {
        "User-Agent": "Researcher-Plugin/0.2 (mailto:mareksokol98@gmail.com)",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return "ok", data.get("message", {})
    except urllib.error.HTTPError as err:
        return ("not_found", None) if err.code == 404 else ("error", None)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return "error", None


def normalize_title(title: str) -> str:
    title = re.sub(r"[{}]", "", title or "")
    title = re.sub(r"[^\w\s]", " ", title.lower())
    return re.sub(r"\s+", " ", title).strip()


def title_similarity(bib_title: str, crossref_titles) -> float:
    if not bib_title or not crossref_titles:
        return -1.0  # not comparable
    best = 0.0
    for cr_title in crossref_titles:
        ratio = difflib.SequenceMatcher(
            None, normalize_title(bib_title), normalize_title(cr_title)
        ).ratio()
        best = max(best, ratio)
    return best


def first_author_surname(author_field: str) -> str:
    """First author's surname from a BibTeX author field ('Last, First and ...'
    or 'First Last and ...')."""
    if not author_field:
        return ""
    first = re.split(r"\s+and\s+", author_field, flags=re.IGNORECASE)[0].strip()
    first = re.sub(r"[{}]", "", first).strip()
    if "," in first:
        return first.split(",", 1)[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


def crossref_first_author_family(metadata: dict) -> str:
    for author in metadata.get("author", []):
        if author.get("sequence") == "first" and author.get("family"):
            return author["family"]
    authors = metadata.get("author", [])
    if authors and authors[0].get("family"):
        return authors[0]["family"]
    return ""


def crossref_year(metadata: dict):
    for date_field in ("published-print", "published-online", "issued", "created"):
        parts = (metadata.get(date_field) or {}).get("date-parts", [[]])
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return None


def check_required_fields(entry: dict) -> list:
    required = {
        "article": ["author", "title", "journal", "year"],
        "inproceedings": ["author", "title", "booktitle", "year"],
        "book": ["author", "title", "publisher", "year"],
        "incollection": ["author", "title", "booktitle", "publisher", "year"],
        "phdthesis": ["author", "title", "school", "year"],
        "mastersthesis": ["author", "title", "school", "year"],
        "techreport": ["author", "title", "institution", "year"],
        "misc": ["author", "title", "year"],
    }
    warnings = []
    for field in required.get(entry.get("type", "misc"), ["author", "title", "year"]):
        if not entry.get(field):
            warnings.append(f"[{entry['key']}] Missing required field: {field}")
    return warnings


# ---------------------------------------------------------------------------
# Validation driver
# ---------------------------------------------------------------------------

def print_verdicts(verdicts):
    """Print the named per-entry DOI verdict block.

    Every entry appears here, so a resolved DOI is STATED as confirmed rather than
    passing silently, and a failed lookup is visibly resolution-failed rather than
    being mistaken for a pass.
    """
    if not verdicts:
        return
    width = max(len(v) for _, v, _ in verdicts)
    print("DOI VERDICTS (per entry; see ERRORS/WARNINGS above for detail):")
    for key, verdict, doi in verdicts:
        suffix = f" {doi}" if doi else ""
        print(f"  {verdict.ljust(width)}  [{key}]{suffix}")
    tally = Counter(v for _, v, _ in verdicts)
    summary = ", ".join(
        f"{tally[name]} {name}" for name in VERDICT_ORDER if tally.get(name)
    )
    print(f"  {summary}\n")


def validate(bib_path, check_doi=True, check_retracted=True, check_fields=True,
             check_duplicates=True, verbose=False) -> int:
    entries = parse_bib(bib_path)
    errors, warnings, verdicts = [], [], []

    if not entries:
        print(f"No entries found in {bib_path}")
        return 1

    print(f"Validating {len(entries)} entries in {bib_path}...\n")

    if check_duplicates:
        for key, count in Counter(e["key"] for e in entries).items():
            if count > 1:
                errors.append(f"Duplicate citation key: {key} (appears {count} times)")
        for doi, count in Counter(e["doi"] for e in entries if e.get("doi")).items():
            if count > 1:
                errors.append(f"Duplicate DOI: {doi} (appears {count} times)")

    need_network = check_doi or check_retracted
    for entry in entries:
        if check_fields:
            warnings.extend(check_required_fields(entry))

        if not need_network:
            verdicts.append((entry["key"], VERDICT_NOT_CHECKED, entry.get("doi", "")))
            continue
        if not entry.get("doi"):
            verdicts.append((entry["key"], VERDICT_NO_DOI, ""))
            if check_doi:
                warnings.append(f"[{entry['key']}] No DOI, cannot verify against CrossRef")
            continue

        if verbose:
            print(f"  Checking {entry['key']} (DOI: {entry['doi']})...")
        status, metadata = resolve_doi(entry["doi"])
        if status == "not_found":
            verdicts.append((entry["key"], VERDICT_NOT_FOUND, entry["doi"]))
            errors.append(f"[{entry['key']}] DOI does not resolve (404, not in CrossRef): {entry['doi']}")
            continue
        if status == "error":
            verdicts.append((entry["key"], VERDICT_RESOLUTION_FAILED, entry["doi"]))
            warnings.append(
                f"[{entry['key']}] DOI check could not complete (network error), "
                f"not counted against the entry: {entry['doi']}"
            )
            continue

        verdict = VERDICT_CONFIRMED
        if check_retracted:
            for update in metadata.get("update-to", []):
                if update.get("label", "").lower() == "retraction":
                    verdict = VERDICT_RETRACTED
                    errors.append(f"[{entry['key']}] RETRACTED: {entry.get('title', 'Unknown title')}")
        verdicts.append((entry["key"], verdict, entry["doi"]))

        if check_doi:
            similarity = title_similarity(entry.get("title", ""), metadata.get("title") or [])
            if 0 <= similarity < TITLE_SIMILARITY_THRESHOLD:
                warnings.append(
                    f"[{entry['key']}] Title similarity {similarity:.2f} below "
                    f"{TITLE_SIMILARITY_THRESHOLD:.2f} vs CrossRef: check this entry"
                )
            bib_surname = first_author_surname(entry.get("author", ""))
            cr_surname = crossref_first_author_family(metadata)
            if bib_surname and cr_surname and bib_surname.casefold() != cr_surname.casefold():
                warnings.append(
                    f"[{entry['key']}] First-author surname mismatch: "
                    f"bib={bib_surname}, CrossRef={cr_surname}"
                )
            cr_year = crossref_year(metadata)
            if cr_year and entry.get("year") and entry["year"] != cr_year:
                warnings.append(
                    f"[{entry['key']}] Year mismatch: bib={entry['year']}, CrossRef={cr_year}"
                )

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ERROR {e}")
        print()
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  WARN  {w}")
        print()

    print_verdicts(verdicts)

    if not errors and not warnings:
        print("All entries valid.")
    else:
        print(f"Found {len(errors)} error(s) and {len(warnings)} warning(s).")
    return len(errors)


def print_core_verdicts(findings):
    """The per-entry axis (a) + axis (b) block. Every entry is listed, pass included."""
    if not findings:
        return
    width = max(len(f["verdict"]) for f in findings)
    print("EVIDENCE VERDICTS (per entry; axis (a) identity, axis (b) status; via researcher-core):")
    for finding in findings:
        suffix = f" {finding['doi']}" if finding["doi"] else ""
        status = finding["status"]
        if not finding["status_checked"]:
            status = f"{status} (unchecked)"
        print(f"  {finding['verdict'].ljust(width)}  [{finding['key']}]{suffix}  status={status}")
    identity = Counter(f["verdict"] for f in findings)
    status_tally = Counter(f["status"] for f in findings)
    print("  identity: " + ", ".join(
        f"{identity[name]} {name}" for name in IDENTITY_ORDER if identity.get(name)
    ))
    print("  status:   " + ", ".join(
        f"{status_tally[name]} {name}" for name in STATUS_ORDER if status_tally.get(name)
    ) + "\n")


def validate_with_core(bib_path, check_doi=True, check_retracted=True, check_fields=True,
                       check_duplicates=True, verbose=False):
    """The core-backed run. Returns the error count, or None when core cannot answer.

    None is the signal to fall back: the caller runs validate() instead, so a machine
    without uv or without core still validates its bibliography.

    The local checks (required fields, duplicate keys and DOIs) stay stdlib either way:
    they need no index, and running them locally keeps the two engines' non-network
    behavior identical.
    """
    entries = parse_bib(bib_path)
    if not entries:
        print(f"No entries found in {bib_path}")
        return 1

    need_network = check_doi or check_retracted
    if not need_network:
        return None  # nothing core would add; the stdlib path is the whole answer

    if verbose:
        print(f"  Querying researcher-core: {' '.join(core_command() or [])} verify-bib ...")
    report = core_verify_bib(bib_path)
    if report is None:
        return None

    findings = core_findings(report)
    if not findings:
        return None

    print(f"Validating {len(entries)} entries in {bib_path} (engine: researcher-core)...\n")

    errors, warnings = [], []

    if check_duplicates:
        for key, count in Counter(e["key"] for e in entries).items():
            if count > 1:
                errors.append(f"Duplicate citation key: {key} (appears {count} times)")
        for doi, count in Counter(e["doi"] for e in entries if e.get("doi")).items():
            if count > 1:
                errors.append(f"Duplicate DOI: {doi} (appears {count} times)")

    if check_fields:
        for entry in entries:
            warnings.extend(check_required_fields(entry))

    for finding in findings:
        key, verdict = finding["key"], finding["verdict"]
        detail = f": {finding['reason']}" if finding["reason"] else ""
        if check_doi:
            if finding["refusal_grade"]:
                errors.append(f"[{key}] {verdict.upper()} (axis a, refusal-grade){detail}")
            elif verdict == "inconclusive":
                # Thin or dirty evidence. NEVER refusal-grade: a downed index is not
                # evidence of fabrication (D9).
                warnings.append(f"[{key}] inconclusive (axis a, not refusal-grade){detail}")
        if check_retracted:
            status = finding["status"]
            if status == "retracted":
                errors.append(f"[{key}] RETRACTED (axis b): {finding['title'] or 'Unknown title'}")
            elif status in ("corrected", "expression-of-concern"):
                warnings.append(f"[{key}] {status} (axis b): {finding['title'] or 'Unknown title'}")
            elif not finding["status_checked"]:
                warnings.append(
                    f"[{key}] publication status could not be checked; "
                    "an unchecked status is not a clean 'current'"
                )

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ERROR {e}")
        print()
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  WARN  {w}")
        print()

    print_core_verdicts(findings)

    if not errors and not warnings:
        print("All entries valid.")
    else:
        print(f"Found {len(errors)} error(s) and {len(warnings)} warning(s).")
    return len(errors)


def main():
    parser = argparse.ArgumentParser(description="Validate .bib entries against CrossRef")
    parser.add_argument("bib_file", help="Path to .bib file")
    parser.add_argument("--check-doi", action="store_true",
                        help="DOI resolution + title/author/year comparison")
    parser.add_argument("--check-retracted", action="store_true",
                        help="Retraction flags via CrossRef update-to")
    parser.add_argument("--check-fields", action="store_true",
                        help="Required fields per entry type")
    parser.add_argument("--check-duplicates", action="store_true",
                        help="Duplicate citation keys and duplicate DOIs")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show progress for each entry")
    args = parser.parse_args()

    if not Path(args.bib_file).exists():
        print(f"File not found: {args.bib_file}")
        sys.exit(1)

    # No --check-* flag means: run everything (back-compatible default).
    any_flag = (
        args.check_doi or args.check_retracted or args.check_fields or args.check_duplicates
    )
    selected = {
        "check_doi": args.check_doi or not any_flag,
        "check_retracted": args.check_retracted or not any_flag,
        "check_fields": args.check_fields or not any_flag,
        "check_duplicates": args.check_duplicates or not any_flag,
        "verbose": args.verbose,
    }

    # Prefer core; fall back on any miss. validate_with_core() returns None when core
    # cannot answer, and that is the only branch that decides which engine ran.
    error_count = validate_with_core(args.bib_file, **selected)
    if error_count is None:
        error_count = validate(args.bib_file, **selected)
    sys.exit(1 if error_count > 0 else 0)


if __name__ == "__main__":
    main()
