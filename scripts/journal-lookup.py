#!/usr/bin/env python3
"""Look up journal formatting requirements in the local database.

Usage:
    python journal-lookup.py "Nature Machine Intelligence"
    python journal-lookup.py "IEEE Transactions on Neural Networks" --format json
    python journal-lookup.py --list

Reads references/journal-database.md. Journal profiles live either under an H3
heading (### Generic IEEE) or under a leaf H2 heading that directly carries
field bullets (## PLOS ONE); H2 headings that only group H3 children (## IEEE
Journals) are not profiles. Field bullets accept both bold-colon forms:
"- **Field:** value" and "- **Field**: value".

When a journal is not in the database, the script prints the closest matches
and a suggestion to consult the publisher's author guidelines; it performs no
web requests itself.
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


def search_journals(query: str, db: dict) -> list:
    query_lower = query.lower()
    results = []
    for key, info in db.items():
        if query_lower == key:
            results.insert(0, (key, info))
        elif query_lower in key or key in query_lower:
            results.append((key, info))
        else:
            if len(set(query_lower.split()) & set(key.split())) >= 2:
                results.append((key, info))
    return results


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

    results = search_journals(args.journal, db)
    if not results:
        print(f"Journal '{args.journal}' not found in the local database.")
        print(f"\nDatabase contains {len(db)} profiles. Run with --list to see all.")
        print("\nSuggestion: consult the journal's author guidelines on the publisher")
        print("website, or ask Claude to look the requirements up via web search.")
        sys.exit(1)

    if args.format == "json":
        import json
        print(json.dumps({name: info for name, info in results}, indent=2))
    else:
        for name, info in results:
            print(format_result(name, info))


if __name__ == "__main__":
    main()
