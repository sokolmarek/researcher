#!/usr/bin/env python3
"""Validate .bib entries against the CrossRef DOI API.

Usage:
    python bib-validator.py <path-to-library.bib>
    python bib-validator.py library.bib --check-doi --check-retracted --check-fields
    python bib-validator.py library.bib --verbose

Checks (all enabled by default; pass one or more --check-* flags to run a subset):
    --check-doi        DOI presence, CrossRef resolution (404 vs network errors are
                       reported differently), title similarity (difflib >= 0.70),
                       first-author surname match, year match
    --check-retracted  Retraction flags via CrossRef update-to metadata
    --check-fields     Required fields per entry type
    (always)           Duplicate citation keys and duplicate DOIs

Parsing: a brace-aware tokenizer, not a regex. Handles nested braces in values
({A {Nested} Title}), quoted values ("..."), bare numeric values, compact entries
whose closing brace sits on the last field line (...}}), string concatenation
with #, and skips @comment/@preamble/@string blocks.

Exit code 1 when errors are found, 0 otherwise. Network problems never count as
entry errors; they are reported as warnings so offline runs stay useful.
"""

import argparse
import difflib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

TITLE_SIMILARITY_THRESHOLD = 0.70


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

def validate(bib_path, check_doi=True, check_retracted=True, check_fields=True,
             verbose=False) -> int:
    entries = parse_bib(bib_path)
    errors, warnings = [], []

    if not entries:
        print(f"No entries found in {bib_path}")
        return 1

    print(f"Validating {len(entries)} entries in {bib_path}...\n")

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
            continue
        if not entry.get("doi"):
            if check_doi:
                warnings.append(f"[{entry['key']}] No DOI, cannot verify against CrossRef")
            continue

        if verbose:
            print(f"  Checking {entry['key']} (DOI: {entry['doi']})...")
        status, metadata = resolve_doi(entry["doi"])
        if status == "not_found":
            errors.append(f"[{entry['key']}] DOI does not resolve (404, not in CrossRef): {entry['doi']}")
            continue
        if status == "error":
            warnings.append(
                f"[{entry['key']}] DOI check could not complete (network error), "
                f"not counted against the entry: {entry['doi']}"
            )
            continue

        if check_retracted:
            for update in metadata.get("update-to", []):
                if update.get("label", "").lower() == "retraction":
                    errors.append(f"[{entry['key']}] RETRACTED: {entry.get('title', 'Unknown title')}")

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
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show progress for each entry")
    args = parser.parse_args()

    if not Path(args.bib_file).exists():
        print(f"File not found: {args.bib_file}")
        sys.exit(1)

    # No --check-* flag means: run everything (back-compatible default).
    any_flag = args.check_doi or args.check_retracted or args.check_fields
    error_count = validate(
        args.bib_file,
        check_doi=args.check_doi or not any_flag,
        check_retracted=args.check_retracted or not any_flag,
        check_fields=args.check_fields or not any_flag,
        verbose=args.verbose,
    )
    sys.exit(1 if error_count > 0 else 0)


if __name__ == "__main__":
    main()
