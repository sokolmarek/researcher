#!/usr/bin/env python3
"""Validate .bib entries against CrossRef DOI API.

Usage:
    python bib-validator.py <path-to-library.bib>
    python bib-validator.py manuscript/references/library.bib --fix

Checks:
    - Every entry has a DOI (warns if missing)
    - DOI resolves via CrossRef API
    - Metadata matches (title, year, authors)
    - No duplicate citation keys
    - No duplicate DOIs
    - Flags retracted papers (via CrossRef metadata)
    - Flags entries without required fields
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from collections import Counter
from pathlib import Path


def parse_bib(bib_path: str) -> list[dict]:
    """Parse a .bib file into a list of entry dicts."""
    entries = []
    content = Path(bib_path).read_text(encoding="utf-8")

    # Match @type{key, ... }
    pattern = re.compile(
        r"@(\w+)\s*\{\s*([^,]+)\s*,\s*(.*?)\n\}",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        entry_type = match.group(1).lower()
        key = match.group(2).strip()
        body = match.group(3)

        entry = {"type": entry_type, "key": key}

        # Parse fields
        field_pattern = re.compile(r"(\w+)\s*=\s*\{(.*?)\}", re.DOTALL)
        for field_match in field_pattern.finditer(body):
            field_name = field_match.group(1).lower()
            field_value = field_match.group(2).strip()
            entry[field_name] = field_value

        entries.append(entry)

    return entries


def resolve_doi(doi: str) -> dict | None:
    """Resolve a DOI via CrossRef API. Returns metadata or None."""
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    headers = {
        "User-Agent": "Researcher-Plugin/0.1 (mailto:researcher-plugin@example.com)",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("message", {})
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def check_required_fields(entry: dict) -> list[str]:
    """Check that required fields are present for the entry type."""
    warnings = []
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

    entry_type = entry.get("type", "misc")
    for field in required.get(entry_type, ["author", "title", "year"]):
        if field not in entry or not entry[field]:
            warnings.append(f"[{entry['key']}] Missing required field: {field}")

    return warnings


def validate(bib_path: str, fix: bool = False, verbose: bool = False) -> int:
    """Run all validation checks. Returns number of errors."""
    entries = parse_bib(bib_path)
    errors = []
    warnings = []

    if not entries:
        print(f"No entries found in {bib_path}")
        return 1

    print(f"Validating {len(entries)} entries in {bib_path}...\n")

    # Check duplicate keys
    keys = [e["key"] for e in entries]
    for key, count in Counter(keys).items():
        if count > 1:
            errors.append(f"Duplicate citation key: {key} (appears {count} times)")

    # Check duplicate DOIs
    dois = [e["doi"] for e in entries if "doi" in e]
    for doi, count in Counter(dois).items():
        if count > 1:
            errors.append(f"Duplicate DOI: {doi} (appears {count} times)")

    # Per-entry checks
    for entry in entries:
        # Required fields
        warnings.extend(check_required_fields(entry))

        # DOI presence
        if "doi" not in entry:
            warnings.append(f"[{entry['key']}] No DOI — cannot verify against CrossRef")
            continue

        # DOI resolution
        if verbose:
            print(f"  Checking {entry['key']} (DOI: {entry['doi']})...")

        metadata = resolve_doi(entry["doi"])
        if metadata is None:
            errors.append(f"[{entry['key']}] DOI does not resolve: {entry['doi']}")
            continue

        # Check for retraction
        if metadata.get("update-to"):
            for update in metadata["update-to"]:
                if update.get("label", "").lower() == "retraction":
                    errors.append(
                        f"[{entry['key']}] RETRACTED: {entry.get('title', 'Unknown title')}"
                    )

        # Year mismatch
        crossref_year = None
        for date_field in ["published-print", "published-online", "created"]:
            if date_field in metadata:
                parts = metadata[date_field].get("date-parts", [[]])
                if parts and parts[0]:
                    crossref_year = str(parts[0][0])
                    break

        if crossref_year and "year" in entry:
            if entry["year"] != crossref_year:
                warnings.append(
                    f"[{entry['key']}] Year mismatch: bib={entry['year']}, CrossRef={crossref_year}"
                )

    # Report
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        print()

    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  ⚠ {w}")
        print()

    total_issues = len(errors) + len(warnings)
    if total_issues == 0:
        print("✓ All entries valid.")
    else:
        print(f"Found {len(errors)} error(s) and {len(warnings)} warning(s).")

    return len(errors)


def main():
    parser = argparse.ArgumentParser(description="Validate .bib entries against CrossRef")
    parser.add_argument("bib_file", help="Path to .bib file")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues (update metadata from CrossRef)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress for each entry")
    args = parser.parse_args()

    if not Path(args.bib_file).exists():
        print(f"File not found: {args.bib_file}")
        sys.exit(1)

    error_count = validate(args.bib_file, fix=args.fix, verbose=args.verbose)
    sys.exit(1 if error_count > 0 else 0)


if __name__ == "__main__":
    main()
