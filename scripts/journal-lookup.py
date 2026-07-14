#!/usr/bin/env python3
"""Look up journal formatting requirements in the local database.

Usage:
    python journal-lookup.py "PLOS ONE"
    python journal-lookup.py "IEEE Transactions" --format json
    python journal-lookup.py --list

Reads references/journal-database.md, which is the script's only data source: it
performs no web requests. Journal profiles live either under an H3 heading
(### Generic IEEE) or under a leaf H2 heading that directly carries field
bullets (## PLOS ONE); H2 headings that only group H3 children (## IEEE
Journals) are not profiles. Field bullets accept both bold-colon forms:
"- **Field:** value" and "- **Field**: value".

A query resolves into two disjoint groups:

  matches      the query equals a profile name, or one is a substring of the
               other. These are real database entries.
  suggestions  the query merely shares two or more words with a profile name.
               These are guesses, NOT the journal that was asked for, and are
               always printed under a "Closest matches (not exact database
               entries)" heading (text) or a separate "suggestions" key (JSON).

Exit status is 0 only when there is at least one match. A query with no match
exits 1, whether it produced suggestions or nothing at all, and points the user
at the publisher's author guidelines.
"""

import argparse
import re
import sys
from pathlib import Path

REFERENCES_DIR = Path(__file__).parent.parent / "references"
JOURNAL_DB = REFERENCES_DIR / "journal-database.md"

# Accepts "- **Key:** value" and "- **Key**: value" (and tolerates both colons).
FIELD_RE = re.compile(r"- \*\*(.+?):?\*\*:?\s*(.+)")


def load_journal_database(db_path=None) -> dict:
    """Parse journal-database.md into {lowercased name: {field: value}}."""
    db_path = Path(db_path) if db_path else JOURNAL_DB
    if not db_path.exists():
        return {}

    journals = {}
    current_name = None   # heading that owns the fields collected so far
    current_info = {}
    pending_h2 = None     # last H2 seen; becomes a profile only if bullets follow directly

    def flush():
        nonlocal current_name, current_info
        if current_name and len(current_info) > 1:
            journals[current_name.lower()] = current_info
        current_name, current_info = None, {}

    for line in db_path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("### "):
            flush()
            pending_h2 = None
            current_name = line[4:].strip()
            current_info = {"name": current_name}
        elif line.startswith("## "):
            flush()
            pending_h2 = line[3:].strip()
        elif line.startswith("- **"):
            if current_name is None and pending_h2:
                # Leaf H2: fields directly under the H2 heading make it a profile.
                current_name = pending_h2
                current_info = {"name": current_name}
                pending_h2 = None
            if current_name:
                match = FIELD_RE.match(line)
                if match:
                    key = match.group(1).strip().rstrip(":").lower().replace(" ", "_")
                    current_info[key] = match.group(2).strip()

    flush()
    return journals


def search_journals(query: str, db: dict) -> tuple:
    """Split the database into (matches, suggestions) for a query.

    matches      exact name, or query/name substring of the other: real hits.
    suggestions  two or more shared words only: guesses, never a real hit.

    Both lists hold (key, info) pairs. Exact matches sort ahead of substring
    matches so the best hit is always first.
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    exact, substring, suggestions = [], [], []
    for key, info in db.items():
        if query_lower == key:
            exact.append((key, info))
        elif query_lower in key or key in query_lower:
            substring.append((key, info))
        elif len(query_words & set(key.split())) >= 2:
            suggestions.append((key, info))
    return exact + substring, suggestions


FIELD_LABELS = {
    "class": "LaTeX Class",
    "citation": "Citation Style",
    "bibliography": "Bibliography Style",
    "word_limit": "Word Limit",
    "abstract": "Abstract",
    "figures": "Figures",
    "references": "Reference Limit",
    "required": "Required",
    "required_sections": "Required Sections",
    "format": "Format",
    "page_limit": "Page Limit",
    "methods": "Methods Section",
    "highlights": "Highlights",
    "supplementary": "Supplementary",
    "submission": "Submission",
    "latex": "LaTeX",
    "latex_template": "LaTeX Template",
    "biography": "Biography",
    "special": "Special",
}


def format_result(name: str, info: dict) -> str:
    """Format ALL parsed fields for display (known labels first, rest humanized)."""
    lines = [f"\n{'=' * 60}", f"  {info.get('name', name)}", f"{'=' * 60}"]
    shown = {"name"}
    for key, label in FIELD_LABELS.items():
        if key in info:
            lines.append(f"  {label}: {info[key]}")
            shown.add(key)
    for key, value in info.items():
        if key not in shown:
            lines.append(f"  {key.replace('_', ' ').title()}: {value}")
    return "\n".join(lines)


SUGGESTION_HEADING = "Closest matches (not exact database entries)"


def print_text(query: str, matches: list, suggestions: list, db_size: int) -> None:
    """Print matches as full profiles; print suggestions as a labeled name list."""
    for name, info in matches:
        print(format_result(name, info))

    if not matches:
        print(f"Journal '{query}' not found in the local database.")
        print(f"\nDatabase contains {db_size} profiles. Run with --list to see all.")

    if suggestions:
        print(f"\n{SUGGESTION_HEADING}:")
        for name, info in suggestions:
            print(f"  - {info.get('name', name)}")
        print("\nThese share words with the query but are different journals. Re-run with")
        print("the exact name above to see one of these profiles.")

    if not matches:
        print("\nSuggestion: consult the journal's author guidelines on the publisher")
        print("website, or ask Claude to look the requirements up via web search.")


def print_json(query: str, matches: list, suggestions: list) -> None:
    """Emit matches and suggestions under separate keys so they cannot be confused."""
    import json

    payload = {
        "query": query,
        "matches": {name: info for name, info in matches},
        "suggestions": {name: info for name, info in suggestions},
    }
    if not matches:
        payload["note"] = (
            f"'{query}' is not in the local database. Any entries under 'suggestions' "
            "are different journals that share words with the query, not this journal. "
            "Consult the publisher's author guidelines."
        )
    print(json.dumps(payload, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Look up journal formatting requirements")
    parser.add_argument("journal", nargs="?", help="Journal name to search for")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format")
    parser.add_argument("--list", action="store_true",
                        help="List all journals in the database")
    args = parser.parse_args()

    db = load_journal_database()

    if args.list:
        print(f"Journals in database ({len(db)}):\n")
        for key, info in sorted(db.items()):
            print(f"  - {info.get('name', key)}")
        return

    if not args.journal:
        parser.error("a journal name is required unless --list is given")

    matches, suggestions = search_journals(args.journal, db)

    if args.format == "json":
        print_json(args.journal, matches, suggestions)
    else:
        print_text(args.journal, matches, suggestions, len(db))

    if not matches:
        sys.exit(1)


if __name__ == "__main__":
    main()
