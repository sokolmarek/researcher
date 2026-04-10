#!/usr/bin/env python3
"""Look up journal formatting requirements.

Usage:
    python journal-lookup.py "Nature Machine Intelligence"
    python journal-lookup.py "IEEE Transactions on Neural Networks" --format json

Checks the local journal-database.md first, then offers web search suggestions
for journals not in the database.
"""

import argparse
import re
import sys
from pathlib import Path


REFERENCES_DIR = Path(__file__).parent.parent / "references"
JOURNAL_DB = REFERENCES_DIR / "journal-database.md"


def load_journal_database() -> dict[str, dict]:
    """Parse journal-database.md into structured data."""
    if not JOURNAL_DB.exists():
        return {}

    content = JOURNAL_DB.read_text(encoding="utf-8")
    journals = {}
    current_journal = None
    current_info = {}

    for line in content.split("\n"):
        # H3 = journal name
        if line.startswith("### "):
            if current_journal:
                journals[current_journal.lower()] = current_info
            current_journal = line[4:].strip()
            current_info = {"name": current_journal}
        elif line.startswith("- **") and current_journal:
            match = re.match(r"- \*\*(.+?)\*\*:\s*(.+)", line)
            if match:
                key = match.group(1).lower().replace(" ", "_")
                value = match.group(2).strip()
                current_info[key] = value

    # Don't forget the last entry
    if current_journal:
        journals[current_journal.lower()] = current_info

    return journals


def search_journals(query: str, db: dict) -> list[tuple[str, dict]]:
    """Search for journals matching query."""
    query_lower = query.lower()
    results = []

    for key, info in db.items():
        # Exact match
        if query_lower == key:
            results.insert(0, (key, info))
        # Partial match
        elif query_lower in key or key in query_lower:
            results.append((key, info))
        # Word overlap
        else:
            query_words = set(query_lower.split())
            key_words = set(key.split())
            if len(query_words & key_words) >= 2:
                results.append((key, info))

    return results


def format_result(name: str, info: dict) -> str:
    """Format journal info for display."""
    lines = [f"\n{'='*60}", f"  {info.get('name', name)}", f"{'='*60}"]

    field_labels = {
        "class": "LaTeX Class",
        "citation": "Citation Style",
        "word_limit": "Word Limit",
        "abstract": "Abstract Limit",
        "figures": "Figure Format",
        "references": "Reference Limit",
        "required": "Required Sections",
        "format": "Format",
        "page_limit": "Page Limit",
        "methods": "Methods Section",
    }

    for key, label in field_labels.items():
        if key in info:
            lines.append(f"  {label}: {info[key]}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Look up journal formatting requirements")
    parser.add_argument("journal", help="Journal name to search for")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format")
    parser.add_argument("--list", action="store_true",
                        help="List all journals in database")
    args = parser.parse_args()

    db = load_journal_database()

    if args.list:
        print(f"Journals in database ({len(db)}):\n")
        for key, info in sorted(db.items()):
            print(f"  - {info.get('name', key)}")
        return

    results = search_journals(args.journal, db)

    if not results:
        print(f"Journal '{args.journal}' not found in local database.")
        print(f"\nDatabase contains {len(db)} journals. Run with --list to see all.")
        print(f"\nSuggestion: Search the journal's website for author guidelines,")
        print(f"or ask Claude to look up requirements via web search.")
        sys.exit(1)

    if args.format == "json":
        import json
        output = {name: info for name, info in results}
        print(json.dumps(output, indent=2))
    else:
        for name, info in results:
            print(format_result(name, info))


if __name__ == "__main__":
    main()
