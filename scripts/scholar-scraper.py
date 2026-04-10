#!/usr/bin/env python3
"""Fetch author publication data for writing style analysis.

Usage:
    python scholar-scraper.py --author "John Smith" --output style-corpus/
    python scholar-scraper.py --url "https://scholar.google.com/citations?user=XXXXX" --output style-corpus/

Retrieves metadata (title, year, journal, citation count) for an author's publications.
For full-text analysis, papers must be available in author-papers/ as PDFs or text files.

Note: Google Scholar does not have an official API. This script uses Semantic Scholar
as the primary source (which has a free API) and falls back to web search hints.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path


def search_semantic_scholar(author_name: str, limit: int = 50) -> list[dict]:
    """Search Semantic Scholar for author's papers."""
    # First, find the author
    query = urllib.parse.quote(author_name)
    url = f"https://api.semanticscholar.org/graph/v1/author/search?query={query}&limit=5"
    headers = {"Accept": "application/json"}

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"Error searching for author: {e}")
        return []

    authors = data.get("data", [])
    if not authors:
        print(f"No author found matching '{author_name}'")
        return []

    # Use first match
    author = authors[0]
    author_id = author["authorId"]
    print(f"Found author: {author.get('name', 'Unknown')} (ID: {author_id})")

    # Fetch their papers
    fields = "title,year,abstract,venue,citationCount,externalIds,publicationTypes"
    url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers?fields={fields}&limit={limit}"
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"Error fetching papers: {e}")
        return []

    papers = data.get("data", [])
    print(f"Retrieved {len(papers)} papers")
    return papers


def save_corpus_metadata(papers: list[dict], output_dir: str):
    """Save paper metadata for style analysis."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    metadata = []
    for paper in papers:
        doi = None
        ext_ids = paper.get("externalIds", {})
        if ext_ids:
            doi = ext_ids.get("DOI")

        metadata.append({
            "title": paper.get("title", ""),
            "year": paper.get("year"),
            "venue": paper.get("venue", ""),
            "citation_count": paper.get("citationCount", 0),
            "doi": doi,
            "abstract": paper.get("abstract", ""),
            "types": paper.get("publicationTypes", []),
        })

    # Sort by year descending
    metadata.sort(key=lambda x: x.get("year") or 0, reverse=True)

    output_file = output_path / "author-publications.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nSaved metadata to {output_file}")
    print(f"Total papers: {len(metadata)}")

    # Summary
    years = [p["year"] for p in metadata if p["year"]]
    if years:
        print(f"Year range: {min(years)}-{max(years)}")
    total_citations = sum(p["citation_count"] for p in metadata)
    print(f"Total citations: {total_citations}")

    # Also save abstracts for basic style analysis
    abstracts_file = output_path / "abstracts.txt"
    with open(abstracts_file, "w", encoding="utf-8") as f:
        for p in metadata:
            if p["abstract"]:
                f.write(f"--- {p['title']} ({p['year']}) ---\n")
                f.write(p["abstract"])
                f.write("\n\n")

    print(f"Saved abstracts to {abstracts_file}")
    print("\nFor full style analysis, place full-text PDFs or .txt files in author-papers/")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch author publications for writing style analysis"
    )
    parser.add_argument("--author", help="Author name to search for")
    parser.add_argument("--url", help="Google Scholar profile URL (extracts name)")
    parser.add_argument(
        "--output", default="style-corpus", help="Output directory (default: style-corpus/)"
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Max papers to retrieve (default: 50)"
    )
    args = parser.parse_args()

    if not args.author and not args.url:
        print("Error: Provide --author or --url")
        sys.exit(1)

    author_name = args.author
    if args.url and not author_name:
        # Try to extract from URL (limited without scraping)
        print("Note: Cannot extract name from URL without scraping. Please provide --author.")
        sys.exit(1)

    papers = search_semantic_scholar(author_name, limit=args.limit)
    if papers:
        save_corpus_metadata(papers, args.output)


if __name__ == "__main__":
    main()
