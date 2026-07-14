#!/usr/bin/env python3
"""A stand-in for `python -m researcher_core`, used only by scripts/tests.

The real core calls OpenAlex, Crossref, and friends. A commit-guard test suite may not
depend on the internet, and it may not depend on a milestone-in-progress CLI either, so
the wrappers are exercised against this fake, wired in through RESEARCHER_CORE_CMD.

What makes the fake worth anything: it emits the COMMITTED contract, that is
core/schemas/verification-report.schema.json, and test_core_fallback.py validates its
output against that schema (when jsonschema is installed). If the fake drifts from the
schema, that test fails, so the wrappers can never be tuned to a shape core never emits.

Verdicts are driven by the citation key, so a fixture bib chooses its own outcomes:

    *ghost*        -> unresolvable  (axis a, refusal-grade): no source resolved it
    *wrongdoi*     -> mismatch      (axis a, refusal-grade): resolved, metadata disagrees
    *inconclusive* -> inconclusive  (axis a, NEVER refusal-grade): a source errored
    *retracted*    -> verified, but axis (b) status retracted
    anything else  -> verified, axis (b) status current

Exit code 1 when anything refusal-grade was found, which is also how the fake proves the
wrappers read the REPORT rather than the exit code.
"""

import json
import os
import re
import sys
from pathlib import Path

ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s}]+)\s*,(.*?)(?=@\w+\s*\{|\Z)", re.DOTALL)
FIELD_RE = re.compile(r"(\w+)\s*=\s*\{([^{}]*)\}")


def parse(text):
    entries = []
    for entry_type, key, body in ENTRY_RE.findall(text):
        if entry_type.lower() in {"comment", "preamble", "string"}:
            continue
        fields = {name.lower(): value.strip() for name, value in FIELD_RE.findall(body)}
        fields["entry_type"] = entry_type.lower()
        fields["key"] = key.strip()
        entries.append(fields)
    return entries


def year_of(fields):
    raw = fields.get("year", "")
    return int(raw) if raw.isdigit() else None


def outcome(source, verdict, *, resolved=True):
    if verdict == "confirmed":
        return {
            "source": source,
            "outcome": "confirmed",
            "resolved": True,
            "title_similarity": 0.98,
            "year_delta": 0,
            "surname_overlap": True,
        }
    if verdict == "negative":
        return {"source": source, "outcome": "negative", "resolved": resolved}
    if verdict == "disagree":
        return {
            "source": source,
            "outcome": "negative",
            "resolved": True,
            "title_similarity": 0.21,
            "year_delta": 7,
            "surname_overlap": False,
            "mismatch_reasons": ["title_similarity", "year", "first_author_surname"],
        }
    return {
        "source": source,
        "outcome": "source_error",
        "resolved": False,
        "error": {"type": "timeout", "message": "index did not answer in time"},
    }


def judge(fields):
    key = fields["key"].lower()
    if "ghost" in key:
        outcomes = [outcome("openalex", "negative", resolved=False),
                    outcome("crossref", "negative", resolved=False)]
        return "unresolvable", "no queried source resolved this reference", outcomes, "current"
    if "wrongdoi" in key:
        outcomes = [outcome("openalex", "disagree"), outcome("crossref", "disagree")]
        return "mismatch", "the DOI resolves, but the metadata disagrees", outcomes, "current"
    if "inconclusive" in key:
        outcomes = [outcome("openalex", "confirmed"), outcome("crossref", "source_error")]
        return "inconclusive", "one confirmation and one source error", outcomes, "current"
    status = "retracted" if "retracted" in key else "current"
    outcomes = [outcome("openalex", "confirmed"), outcome("crossref", "confirmed")]
    return "verified", "two sources confirmed within thresholds", outcomes, status


def tally(outcomes):
    counts = {"confirmed": 0, "negative": 0, "source_error": 0}
    for item in outcomes:
        counts[item["outcome"]] += 1
    return counts


def build_report(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    entries = []
    for fields in parse(text):
        verdict, reason, outcomes, status = judge(fields)
        notices = []
        if status == "retracted":
            notices = [{
                "type": "retraction",
                "doi": "10.1234/retraction-notice",
                "label": "Retraction",
                "date": "2021-04-01",
                "source": "crossref",
            }]
        entries.append({
            "key": fields["key"],
            "reference": {
                "title": fields.get("title") or None,
                "doi": (fields.get("doi") or "").lower() or None,
                "year": year_of(fields),
                "authors": [fields["author"].split(",")[0]] if fields.get("author") else [],
                "entry_type": fields.get("entry_type"),
            },
            "verdict": verdict,
            "refusal_grade": verdict in ("unresolvable", "mismatch"),
            "reason": reason,
            "source_outcomes": outcomes,
            "tally": tally(outcomes),
            "status": {
                "verdict": status,
                "checked": True,
                "notices": notices,
                "sources": ["crossref", "openalex"],
            },
            "accessibility": {"verdict": "abstract-only", "oa_url": None, "content_type": None},
        })

    identity = {"verified": 0, "mismatch": 0, "unresolvable": 0, "inconclusive": 0}
    status_counts = {"current": 0, "corrected": 0, "retracted": 0, "expression-of-concern": 0}
    access = {"full-text": 0, "abstract-only": 0, "unavailable": 0}
    sources = {"confirmed": 0, "negative": 0, "source_error": 0}
    for entry in entries:
        identity[entry["verdict"]] += 1
        status_counts[entry["status"]["verdict"]] += 1
        access[entry["accessibility"]["verdict"]] += 1
        for name, count in entry["tally"].items():
            sources[name] += count

    return {
        "schema_version": "1.0.0",
        "protocol_version": "1.0.0",
        "versions": {"core": "0.1.0", "parser": "0.1.0"},
        "input": {"kind": "bib", "path": str(path)},
        "thresholds": {
            "title_similarity": 0.7,
            "year_tolerance": 1,
            "require_first_author_surname": True,
            "min_confirmations": 2,
        },
        "sources_queried": ["openalex", "crossref"],
        "entries": entries,
        "summary": {
            "total": len(entries),
            "identity": identity,
            "source_outcomes": sources,
            "status": status_counts,
            "accessibility": access,
            "refusal_grade": identity["unresolvable"] + identity["mismatch"],
        },
    }


def main(argv):
    if not argv or argv[0] != "verify-bib":
        # An installed core too old to know the command behaves exactly like this.
        print(f"fake-core: unknown command: {' '.join(argv) or '(none)'}", file=sys.stderr)
        return 2

    path = argv[1]
    marker = os.environ.get("FAKE_CORE_MARKER")
    if marker:
        Path(marker).write_text(
            json.dumps({
                "argv": argv,
                "bib_text": Path(path).read_text(encoding="utf-8", errors="replace"),
            }),
            encoding="utf-8",
        )

    report = build_report(path)
    json.dump(report, sys.stdout)
    return 1 if report["summary"]["refusal_grade"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
